"""JiraService service layer ."""

import uuid
from uuid import UUID

import httpx
from httpx import HTTPError
from sqlalchemy.orm import Session

from app.components.duplicate_checker.TestCaseDuplicateChecker import (
    validate_and_register_test_case,
)
from app.constants import ACTION_SKIP, DEFAULT_TIMEOUT, MAX_RESULTS
from app.core.config import get_settings
from app.core.crypto import decrypt_token
from app.core.exceptions import (
    DatabaseOperationException,
    JiraAuthException,
    JiraCredentialsInvalidException,
    JiraFetchException,
    JiraInstanceNotConfiguredException,
    JiraNotConfiguredException,
)
from app.core.logging import logger
from app.database.crud_jira_import import (
    apply_refresh_changes,
    get_existing_story_statuses,
    refresh_stories_from_jira,
)
from app.database.crud_test_cases import update_jira_key
from app.database.projects_db import (
    get_configured_jira_urls_for_user,
    get_project_by_id,
    update_project_jira_config,
)
from app.database.users_db import get_user_by_id, update_user_jira_credentials
from app.schemas.JiraSchemas import (
    JiraConfigRequest,
    JiraConfigResponse,
    JiraCredentialsRequest,
    JiraCredentialsResponse,
    JiraTestConnectionResponse,
    PushedTestCase,
    PushToJiraResponse,
    RequestModel,
)
from app.services.internal import build_description
from app.utils.jira_parser import extract_acceptanceCriteria, extract_description
from app.utils.signatures import normalize_text
from app.utils.url_validation import validate_jira_url

settings = get_settings()


def _jira_auth(jira_email: str, api_token: str) -> tuple[str, str]:
    """Build the Jira basic-auth pair, refusing a blank half.

    Jira answers a missing email with an opaque 401, so fail here instead —
    the helpers default jira_email to "" for their callers' convenience.
    """

    if not jira_email or not api_token:
        raise JiraNotConfiguredException()
    return jira_email, api_token


def _clean(value: str | None) -> str | None:
    """Strip a payload field while preserving None (omitted) versus "" (cleared)."""

    return value if value is None else value.strip()


def _unique_jira_urls(jira_urls: list[str]) -> list[str]:
    """Drop blanks and duplicates that differ only by trailing slash or case,
    which SQL DISTINCT keeps as separate rows but are the same tenant."""

    seen = set()
    unique = []
    for url in jira_urls:
        cleaned = (url or "").strip().rstrip("/")
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return unique


class JiraService:
    """Service for Jira integration (push side)."""

    def __init__(self, db: Session):
        self.db = db

    def get_project_jira_credentials(self, project_id, user_id) -> tuple[str, str, str, str]:
        """Resolve the Jira URL / Project Key (from the project) and the
        calling user's own Jira email / API token (from their Profile).

        Raises JiraNotConfiguredException if either half is missing, so
        callers can surface a helpful error instead of silently falling back
        to nothing.
        """
        project = get_project_by_id(self.db, project_id)
        if project is None:
            raise DatabaseOperationException(f"Project {project_id} not found")

        user = get_user_by_id(self.db, user_id)

        jira_url = (project.jira_url or "").strip()
        project_key = (project.jira_project_key or "").strip()
        jira_email = (user.jira_email or "").strip() if user else ""
        api_token = (
            decrypt_token(user.jira_api_token).strip() if user and user.jira_api_token else ""
        )

        if not jira_url or not project_key or not jira_email or not api_token:
            raise JiraNotConfiguredException()

        return jira_url, project_key, jira_email, api_token

    async def push_bulk_to_jira(
        self,
        testcases,
        format_type,
        user_story_id: str,
        jira_url: str,
        project_key: str,
        api_token: str,
        jira_email: str = "",
    ):
        auth = _jira_auth(jira_email, api_token)
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        issues = []
        for test_case in testcases:
            issues.append(
                {
                    "fields": {
                        "project": {"key": project_key},
                        "summary": f"{test_case['id']} - {test_case['title']}",
                        "description": build_description(test_case, format_type),
                        "issuetype": {"id": settings.jira_test_case_issue_type_id},
                        "priority": {"name": test_case["priority"]},
                        "labels": [
                            tag.lower().replace(" ", "_") for tag in (test_case.get("tags") or [])
                        ],
                    }
                }
            )
        try:
            async with httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT,
            ) as client:
                response = await client.post(
                    f"{jira_url}/rest/api/3/issue/bulk",
                    json={"issueUpdates": issues},
                    headers=headers,
                    auth=auth,
                )
                response.raise_for_status()
                data = response.json()
        except HTTPError as error:
            logger.error("Jira bulk API failed: %s", str(error))
            return [], [
                {
                    "tc_id": tc["id"],
                    "error": "Jira API/network failure",
                }
                for tc in testcases
            ]
        success = []
        failed = []
        for index, issue in enumerate(data.get("issues", [])):
            tc = testcases[index]
            success.append(
                {
                    "tc": tc,
                    "tc_id": tc.get("id") or tc.get("tc_id"),
                    "jira_key": issue["key"],
                }
            )
        for error in data.get("errors", []):
            index = error.get("failedElementNumber", 0)
            failed.append(
                {
                    "tc_id": testcases[index]["id"],
                    "error": error.get("elementErrors"),
                }
            )
        return success, failed

    async def fetch_jira_duplicates(
        self,
        test_cases,
        jira_url: str,
        project_key: str,
        api_token: str,
        jira_email: str = "",
    ):
        """Look up existing Jira issues that match the given test cases by id or
        title, returning the sets of matching normalized ids and titles."""
        jira_ids = set()
        jira_titles = set()

        try:
            jira_search_conditions = []

            for test_case in test_cases:
                test_case_id = test_case.get("id", "").strip()
                title = test_case.get("title", "").strip()
                if test_case_id:
                    jira_search_conditions.append(f'summary ~ "{test_case_id}"')
                if title:
                    jira_search_conditions.append(f'summary ~ "{title}"')

            if not jira_search_conditions:
                return set(), set()

            safe_project_key = project_key.replace('"', '\\"')
            jql = f'project = "{safe_project_key}" ' f"AND ({' OR '.join(jira_search_conditions)})"

            auth = _jira_auth(jira_email, api_token)
            headers = {"Accept": "application/json", "Content-Type": "application/json"}

            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    f"{jira_url}/rest/api/3/search/jql",
                    params={
                        "jql": jql,
                        "fields": "summary",
                        "maxResults": MAX_RESULTS,
                    },
                    headers=headers,
                    auth=auth,
                )

            response.raise_for_status()
            data = response.json()

            for issue in data.get("issues", []):
                jira_storyTitle = issue["fields"].get("summary", "").strip()
                jira_storyTitle_parts = jira_storyTitle.split(" - ", 1)
                if len(jira_storyTitle_parts) == 2:
                    test_case_id = jira_storyTitle_parts[0].strip()
                    title = jira_storyTitle_parts[1].strip()
                    jira_ids.add(normalize_text(test_case_id))
                    jira_titles.add(normalize_text(title))

        except HTTPError as error:
            logger.error("Jira duplicate fetch failed: %s", str(error))
            return set(), set()

        return jira_ids, jira_titles

    async def push_to_jira(
        self,
        request: RequestModel,
        user_id,
    ) -> PushToJiraResponse:
        jira_url, project_key, jira_email, api_token = self.get_project_jira_credentials(
            request.projectId, user_id
        )

        existing_rows = []
        seen_contents = set()
        normalized_test_cases = [tc.normalize().model_dump() for tc in request.test_cases]
        jira_ids, jira_titles = await self.fetch_jira_duplicates(
            normalized_test_cases,
            jira_url,
            project_key,
            api_token,
            jira_email=jira_email,
        )
        success, failed, duplicates, to_create, db_records = [], [], [], [], []
        db_saved_count = 0
        db_skipped = []
        db_failed = []

        for test_case in normalized_test_cases:
            action = validate_and_register_test_case(test_case, existing_rows, seen_contents)
            if action == ACTION_SKIP:
                duplicates.append(test_case["id"])
                continue
            if (
                normalize_text(test_case["id"]) in jira_ids
                or normalize_text(test_case["title"]) in jira_titles
            ):
                duplicates.append(test_case["id"])
                continue
            to_create.append(test_case)

        bulk_success, bulk_failed = await self.push_bulk_to_jira(
            to_create,
            request.format,
            user_story_id=request.userStoryId,
            jira_url=jira_url,
            project_key=project_key,
            api_token=api_token,
            jira_email=jira_email,
        )
        # Update jira_key on already-saved rows — match on title since tc_id
        # inside test_data may have been renamed during the initial bulk save.
        for item in bulk_success:
            update_jira_key(
                db=self.db,
                user_story_id=request.userStoryId,
                tc_title=item["tc"]["title"],
                jira_key=item["jira_key"],
            )
        self.db.commit()

        for item in bulk_success:
            success.append(item["jira_key"])
            db_records.append(
                {
                    "tc": item["tc"],
                    "format": request.format,
                    "user_story_id": request.userStoryId,
                    "status": "SUCCESS",
                    "jira_key": item["jira_key"],
                }
            )
        for failed_item in bulk_failed:
            failed.append(failed_item)
        pushed_items = []

        for item in bulk_success:
            pushed_items.append(
                PushedTestCase(
                    tc_id=item["tc"]["id"],
                    jira_key=item["jira_key"],
                    status="pushed",
                )
            )
        return PushToJiraResponse(
            total=len(request.test_cases),
            pushed_count=len(pushed_items),
            duplicate_count=len(duplicates),
            failed_count=len(failed),
            db_saved_count=db_saved_count,
            pushed=pushed_items,
            duplicates=duplicates,
            failed=failed,
            db_skipped=db_skipped,
            db_failed=db_failed,
        )

    # ── Fetch (import side) ────────────────────────────────────────────────────

    @staticmethod
    def build_fetch_response(all_issues: list) -> list:
        epics = {}
        stories = []

        for issue in all_issues:
            fields = issue.get("fields", {})
            issue_type = fields.get("issuetype", {}).get("name", "").strip().lower()

            if issue_type == "epic":
                epics[issue["key"]] = {
                    "epicId": issue["key"],
                    "epicTitle": fields.get("summary", "No Summary"),
                    "user_stories": [],
                }
            elif issue_type in ["story", "user story"]:
                parent = fields.get("parent") or {}
                parent_key = parent.get("key") if isinstance(parent, dict) else None

                if not parent_key:
                    epic_field = fields.get("epic")
                    if isinstance(epic_field, dict):
                        parent_key = epic_field.get("key")
                    elif isinstance(epic_field, str):
                        parent_key = epic_field

                if not parent_key:
                    for k, v in fields.items():
                        if "customfield_" in k:
                            if isinstance(v, str) and "-" in v and not v.startswith("http"):
                                parts = v.split("-")
                                if len(parts) == 2 and parts[0].isalpha() and parts[1].isdigit():
                                    parent_key = v
                                    break
                            elif isinstance(v, dict) and "key" in v:
                                parent_key = v.get("key")
                                break

                priority_field = fields.get("priority") or {}
                jira_priority = (
                    priority_field.get("name") if isinstance(priority_field, dict) else None
                )

                stories.append(
                    {
                        "storyId": issue["key"],
                        "storyTitle": fields.get("summary", "No Story Title"),
                        "description": extract_description(fields.get("description")),
                        "acceptanceCriteria": extract_acceptanceCriteria(fields),
                        "issue_type": issue_type,
                        "priority": jira_priority,
                        "parent_key": parent_key,
                        "already_exists": False,
                        "status": "pending",
                    }
                )

        for story in stories:
            parent_key = story.pop("parent_key", None)
            if parent_key and parent_key in epics:
                epics[parent_key]["user_stories"].append(story)

        ungrouped = [s for s in stories if not any(s in e["user_stories"] for e in epics.values())]
        if ungrouped:
            epics["UNGROUPED"] = {
                "epicId": "UNGROUPED",
                "epicTitle": "Imported Stories",
                "user_stories": ungrouped,
            }

        return list(epics.values())

    @staticmethod
    def _build_jql(project_key: str, statuses: list[str] | None) -> str:
        """Build the search JQL for a project, optionally restricting stories to
        the given statuses. Epics are always included so story-to-epic grouping
        and epic titles survive the filter."""
        safe_project_key = project_key.replace('"', '\\"')
        base = f'project = "{safe_project_key}"'
        cleaned = [s.strip() for s in (statuses or []) if s and s.strip()]
        if cleaned:
            quoted = ", ".join(f'"{s.replace(chr(34), chr(92) + chr(34))}"' for s in cleaned)
            base += (
                " AND (issuetype = Epic OR "
                f'(issuetype in (Story, "User Story") AND status in ({quoted})))'
            )
        return f"{base} ORDER BY created DESC"

    @staticmethod
    def enrich_story_statuses(
        epics_payload: list[dict],
        project_id: UUID | None = None,
        db: Session | None = None,
    ) -> list[dict]:
        """Annotate Jira stories with existing DB status metadata for the UI,
        scoped to the specified project."""
        if not epics_payload:
            return epics_payload

        story_keys = [
            story.get("storyId")
            for epic in epics_payload
            for story in epic.get("user_stories", [])
            if story.get("storyId")
        ]
        if not story_keys:
            return epics_payload

        if db is None or project_id is None:
            for epic in epics_payload:
                for story in epic.get("user_stories", []):
                    story.setdefault("already_exists", False)
                    story.setdefault("status", "pending")
            return epics_payload

        existing_story_statuses = get_existing_story_statuses(db, story_keys, project_id)
        for epic in epics_payload:
            for story in epic.get("user_stories", []):
                story_key = story.get("storyId")
                if story_key in existing_story_statuses:
                    story.update(existing_story_statuses[story_key])
                else:
                    story["already_exists"] = False
                    story["status"] = "pending"

        return epics_payload

    @staticmethod
    async def fetch_jira_data(
        jira_url: str,
        project_key: str,
        api_token: str,
        project_id: UUID | None = None,
        statuses: list[str] | None = None,
        last_sync=None,
        db: Session | None = None,
        jira_email: str = "",
    ) -> list:
        all_issues = []
        next_page_token = None
        max_results = 100
        try:
            url = f"{jira_url}/rest/api/3/search/jql"
            auth = _jira_auth(jira_email, api_token)
            headers_local = {"Accept": "application/json"}
            jql = JiraService._build_jql(project_key, statuses)

            while True:
                params = {
                    "jql": jql,
                    "fields": (
                        "summary,description,parent,issuetype,epic,priority,"
                        "customfield_10014,customfield_10040,customfield_10041"
                    ),
                    "maxResults": max_results,
                }
                if next_page_token:
                    params["nextPageToken"] = next_page_token
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.get(
                        url,
                        headers=headers_local,
                        params=params,
                        auth=auth,
                    )
                if response.status_code == 401:
                    raise JiraAuthException()
                response.raise_for_status()
                data = response.json()
                all_issues.extend(data.get("issues", []))
                next_page_token = data.get("nextPageToken")
                if data.get("isLast") or not next_page_token:
                    break

        except httpx.HTTPError as exc:
            logger.error("Jira fetch failed: %s", str(exc))
            raise JiraFetchException()

        epics_payload = JiraService.build_fetch_response(all_issues)
        return JiraService.enrich_story_statuses(epics_payload, project_id=project_id, db=db)

    @staticmethod
    async def fetch_project_story_statuses(
        jira_url: str, project_key: str, api_token: str, jira_email: str = ""
    ) -> list[str]:
        safe_project_key = project_key.replace('"', '\\"')
        jql = (
            f'project = "{safe_project_key}" AND issuetype in (Story, "User Story") '
            "ORDER BY created DESC"
        )
        auth = _jira_auth(jira_email, api_token)
        statuses = set()
        next_page_token = None
        max_results = 100
        try:
            while True:
                params = {"jql": jql, "fields": "status", "maxResults": max_results}
                if next_page_token:
                    params["nextPageToken"] = next_page_token
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.get(
                        f"{jira_url}/rest/api/3/search/jql",
                        headers={"Accept": "application/json"},
                        auth=auth,
                        params=params,
                    )
                if response.status_code == 401:
                    raise JiraAuthException()
                response.raise_for_status()
                data = response.json()
                for issue in data.get("issues", []):
                    name = issue.get("fields", {}).get("status", {}).get("name")
                    if name:
                        statuses.add(name)
                next_page_token = data.get("nextPageToken")
                if data.get("isLast") or not next_page_token:
                    break
        except httpx.HTTPError as exc:
            logger.error("Jira statuses fetch failed: %s", str(exc))
            raise JiraFetchException()

        return sorted(statuses)

    @staticmethod
    def _build_test_case_jql(project_key: str) -> str:
        """JQL restricted to the Jira issue type used for pushed/imported test
        cases (see settings.jira_test_case_issue_type_id), newest first."""
        safe_project_key = project_key.replace('"', '\\"')
        return (
            f'project = "{safe_project_key}" AND '
            f"issuetype = {settings.jira_test_case_issue_type_id} "
            "ORDER BY created DESC"
        )

    @staticmethod
    def build_test_case_response(all_issues: list) -> list[dict]:
        """Map raw Jira issues (test-case issue type) to the JiraTestCaseResponse shape."""
        test_cases = []
        for issue in all_issues:
            fields = issue.get("fields", {}) or {}
            status = fields.get("status") or {}
            priority = fields.get("priority") or {}
            components = fields.get("components") or []
            labels = fields.get("labels") or []

            test_cases.append(
                {
                    "id": issue.get("key"),
                    "name": fields.get("summary", "No Summary"),
                    # Jira has no first-class "test suite" field; a label is the
                    # closest project-configurable grouping available generically.
                    "suite": labels[0] if labels else None,
                    "status": status.get("name") or "Unknown",
                    "priority": priority.get("name"),
                    "module": components[0].get("name") if components else None,
                }
            )
        return test_cases

    MAX_TEST_CASE_PAGES = 20

    @staticmethod
    async def fetch_jira_test_cases(
        jira_url: str,
        project_key: str,
        api_token: str,
        jira_email: str = "",
    ) -> list[dict]:
        """Fetch test-case issues from Jira for a project, using the project's
        saved Jira URL/Project Key and the caller's own Jira email/API token."""
        all_issues: list[dict] = []
        next_page_token = None
        seen_tokens: set[str] = set()
        jql = JiraService._build_test_case_jql(project_key)
        auth = _jira_auth(jira_email, api_token)
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                for _ in range(JiraService.MAX_TEST_CASE_PAGES):
                    params = {
                        "jql": jql,
                        "fields": "summary,status,priority,components,labels",
                        "maxResults": MAX_RESULTS,
                    }
                    if next_page_token:
                        params["nextPageToken"] = next_page_token
                    response = await client.get(
                        f"{jira_url}/rest/api/3/search/jql",
                        headers={"Accept": "application/json"},
                        auth=auth,
                        params=params,
                    )
                    if response.status_code == 401:
                        raise JiraAuthException()
                    response.raise_for_status()
                    data = response.json()
                    all_issues.extend(data.get("issues", []))
                    next_page_token = data.get("nextPageToken")
                    if data.get("isLast") or not next_page_token or next_page_token in seen_tokens:
                        break
                    seen_tokens.add(next_page_token)
                else:
                    logger.warning(
                        "jira_test_case_fetch_truncated", extra={"project_key": project_key}
                    )
        except httpx.HTTPError as exc:
            logger.error("Jira test case fetch failed: %s", str(exc))
            raise JiraFetchException()

        return JiraService.build_test_case_response(all_issues)

    async def refresh_imported_stories(
        self,
        jira_url: str,
        project_key: str,
        api_token: str,
        project_id: uuid.UUID,
        statuses: list[str] | None = None,
        jira_email: str = "",
    ) -> dict:
        try:
            fresh_epics = await JiraService.fetch_jira_data(
                jira_url,
                project_key,
                api_token,
                statuses=statuses,
                db=self.db,
                jira_email=jira_email,
            )

            result = refresh_stories_from_jira(self.db, fresh_epics, project_id)

            return {
                "success": True,
                "imported_count": 0,
                "updated_count": len(result["changed_story_keys"]),
                "failed_count": 0,
                "changed_story_keys": result["changed_story_keys"],
                "new_story_keys": result.get("new_story_keys", []),
            }

        except Exception as exc:
            logger.exception("REFRESH FAILED")
            self.db.rollback()
            raise DatabaseOperationException(str(exc))

    # ── Per-project Jira configuration (settings screen) ──────────────────────

    def get_jira_config(self, project_id, user_id) -> JiraConfigResponse:
        """Return the saved Jira URL/Project Key for a project."""

        project = get_project_by_id(self.db, project_id)
        if project is None:
            raise DatabaseOperationException(f"Project {project_id} not found")

        return JiraConfigResponse(
            jira_url=project.jira_url,
            project_key=project.jira_project_key,
            is_connected=False,
        )

    def save_jira_config(
        self, project_id, user_id, payload: JiraConfigRequest
    ) -> JiraConfigResponse:
        jira_url = (payload.jira_url or "").strip() or None
        if jira_url:
            validate_jira_url(jira_url)
        project = update_project_jira_config(
            self.db,
            project_id,
            jira_url=jira_url,
            jira_project_key=(payload.project_key or "").strip() or None,
        )

        return JiraConfigResponse(
            jira_url=project.jira_url,
            project_key=project.jira_project_key,
            is_connected=False,
        )

    # ── Per-user Jira credentials (Profile page) ───────────────────────────────

    def get_my_jira_credentials(self, user_id) -> JiraCredentialsResponse:
        """Return the caller's saved Jira email and whether an API token is set."""

        user = get_user_by_id(self.db, user_id)
        return JiraCredentialsResponse(
            jira_email=user.jira_email if user else None,
            has_api_token=bool(user and user.jira_api_token),
        )

    async def save_my_jira_credentials(
        self, user_id, payload: JiraCredentialsRequest
    ) -> JiraCredentialsResponse:
        """Save the caller's own Jira email/API token, once Jira confirms the
        pair authenticates and belongs to that email's account."""

        existing = get_user_by_id(self.db, user_id)

        # None means the field was omitted and the stored value stands; "" means the
        # user cleared it and must not be filled back in, or the value being deleted
        # would be the one verified.
        submitted_email = _clean(payload.jira_email)
        submitted_token = _clean(payload.api_token)

        # The form only re-sends the token when it's retyped, so verify the pair that
        # will actually be used — otherwise an email-only edit could leave a
        # mismatched combination saved. Only fall back to the stored values, and only
        # decrypt, when the field was actually omitted.
        email = (
            ((existing.jira_email or "").strip() if existing else "")
            if submitted_email is None
            else submitted_email
        )
        token = self._stored_api_token(existing) if submitted_token is None else submitted_token

        if email and token:
            await self._verify_credentials_for_user(user_id, email, token)

        user = update_user_jira_credentials(
            self.db,
            user_id,
            jira_email=submitted_email,
            jira_api_token=submitted_token,
        )
        return JiraCredentialsResponse(
            jira_email=user.jira_email,
            has_api_token=bool(user.jira_api_token),
        )

    @staticmethod
    def _stored_api_token(user) -> str:
        """Return the user's saved token, treating one that cannot be decrypted as
        absent so a rotated encryption key can't block replacing or clearing it."""

        if not (user and user.jira_api_token):
            return ""
        try:
            return decrypt_token(user.jira_api_token).strip()
        except Exception:
            logger.warning(
                "jira_stored_token_undecryptable",
                extra={"user_id": str(getattr(user, "id", ""))},
            )
            return ""

    async def _verify_credentials_for_user(self, user_id, jira_email: str, api_token: str) -> None:
        """Verify the pair against each Jira instance the user's projects use,
        stopping at the first that authenticates.

        A 401 only rules out that one instance — a consultant's token is valid on
        their own client's tenant and not on another's — so it moves on to the
        next rather than rejecting outright.
        """

        jira_urls = get_configured_jira_urls_for_user(self.db, user_id)
        if not jira_urls:
            raise JiraInstanceNotConfiguredException()

        for jira_url in _unique_jira_urls(jira_urls):
            account_email = await self._fetch_jira_account_email(jira_url, jira_email, api_token)
            if account_email is None:
                continue
            if account_email and account_email.lower() != jira_email.lower():
                raise JiraCredentialsInvalidException(
                    f"This API token belongs to the Jira account {account_email}, "
                    f"not {jira_email}."
                )
            return

        raise JiraCredentialsInvalidException()

    @staticmethod
    async def _fetch_jira_account_email(
        jira_url: str, jira_email: str, api_token: str
    ) -> str | None:
        """Return the account email the credentials authenticate as at this Jira
        instance, "" when Jira hides it, or None when the instance could not
        confirm them either way (bad credentials here, error, unreachable)."""

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    f"{jira_url}/rest/api/3/myself",
                    headers={"Accept": "application/json"},
                    auth=(jira_email, api_token),
                )
        except httpx.HTTPError as exc:
            logger.error("Jira credential verification unreachable: %s", str(exc))
            return None

        if response.status_code >= 400:
            logger.warning(
                "jira_credential_verification_rejected",
                extra={"status_code": response.status_code},
            )
            return None

        try:
            return (response.json().get("emailAddress") or "").strip()
        except ValueError:
            return ""

    async def test_connection(self, project_id, user_id) -> JiraTestConnectionResponse:
        """Validate the saved Jira URL/Project Key/API token against the real Jira REST API."""

        project = get_project_by_id(self.db, project_id)
        if project is None:
            raise DatabaseOperationException(f"Project {project_id} not found")

        user = get_user_by_id(self.db, user_id)

        jira_url = (project.jira_url or "").strip()
        project_key = (project.jira_project_key or "").strip()
        jira_email = (user.jira_email or "").strip() if user else ""
        api_token = (
            decrypt_token(user.jira_api_token).strip() if user and user.jira_api_token else ""
        )

        if not jira_url or not project_key or not jira_email or not api_token:
            return JiraTestConnectionResponse(
                success=False,
                message=(
                    "Jira URL, Project Key must be set, and your Jira email/API "
                    "token must be saved in your Profile, before testing."
                ),
            )

        try:
            basic_auth = _jira_auth(jira_email, api_token)
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                # /myself validates the credentials against the Jira instance.
                me_response = await client.get(
                    f"{jira_url}/rest/api/3/myself",
                    headers={"Accept": "application/json"},
                    auth=basic_auth,
                )
                if me_response.status_code == 401:
                    return JiraTestConnectionResponse(
                        success=False,
                        message="Authentication failed. Check the email and API token.",
                    )
                me_response.raise_for_status()

                # Confirm the project key actually exists/is accessible.
                project_response = await client.get(
                    f"{jira_url}/rest/api/3/project/{project_key}",
                    headers={"Accept": "application/json"},
                    auth=basic_auth,
                )
                if project_response.status_code == 404:
                    return JiraTestConnectionResponse(
                        success=False,
                        message=(
                            f'Project key "{project_key}" was not found ' "on this Jira instance."
                        ),
                    )
                project_response.raise_for_status()

            return JiraTestConnectionResponse(
                success=True,
                message="Connection successful.",
            )
        except httpx.HTTPError as exc:
            logger.error("Jira test connection failed: %s", str(exc))
            return JiraTestConnectionResponse(
                success=False,
                message=(
                    "Could not reach the Jira instance. " "Check the Jira URL and try again."
                ),
            )

    async def apply_refresh_updates(
        self,
        jira_url: str,
        project_key: str,
        api_token: str,
        project_id: uuid.UUID,
        statuses: list[str] | None = None,
        jira_email: str = "",
    ):
        try:
            fresh_epics = await JiraService.fetch_jira_data(
                jira_url,
                project_key,
                api_token,
                statuses=statuses,
                db=self.db,
                jira_email=jira_email,
            )

            updated = apply_refresh_changes(self.db, fresh_epics, project_id)

            return {
                "success": True,
                "updated": updated,
            }
        except Exception as exc:
            logger.exception("APPLY REFRESH FAILED")
            self.db.rollback()
            raise DatabaseOperationException(str(exc))

    async def apply_refresh_updates_direct(
        self,
        fresh_epics: list[dict],
        project_id: UUID,
    ):
        try:
            updated = apply_refresh_changes(self.db, fresh_epics, project_id=project_id)

            return {
                "success": True,
                "updated": updated,
            }
        except Exception as exc:
            logger.exception("APPLY REFRESH DIRECT FAILED")
            self.db.rollback()
            raise DatabaseOperationException(str(exc))
