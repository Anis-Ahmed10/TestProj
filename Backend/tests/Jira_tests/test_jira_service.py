"""Unit tests for JiraService — 100% coverage of jiraService.py."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import (
    DatabaseOperationException,
    JiraAuthException,
    JiraCredentialsInvalidException,
    JiraFetchException,
    JiraInstanceNotConfiguredException,
    JiraNotConfiguredException,
)
from app.database.crud_jira_import import get_existing_story_statuses
from app.services.jiraService import JiraService, _jira_auth

# ══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════════════════════════════════════


def _epic(key="EP-1", summary="My Epic"):
    return {
        "key": key,
        "fields": {"issuetype": {"name": "Epic"}, "summary": summary},
    }


def _story(key="US-1", summary="My Story", parent_key="EP-1"):
    return {
        "key": key,
        "fields": {
            "issuetype": {"name": "Story"},
            "summary": summary,
            "description": None,
            "parent": {"key": parent_key} if parent_key else None,
            "customfield_10040": None,
            "customfield_10041": None,
        },
    }


def _make_test_case(tc_id="TC-1", title="Login test", priority="High"):
    return {
        "id": tc_id,
        "title": title,
        "priority": priority,
        "tags": ["smoke"],
        "steps": [],
        "expected_result": "Pass",
    }


def _make_request(test_cases=None, fmt="bdd", story_id="US-1"):
    """Build a mock RequestModel with normalised test-case mocks."""
    raw_tcs = test_cases or [_make_test_case()]
    tc_mocks = []
    for tc in raw_tcs:
        m = MagicMock()
        m.normalize.return_value.model_dump.return_value = tc
        tc_mocks.append(m)

    req = MagicMock()
    req.test_cases = tc_mocks
    req.format = fmt
    req.userStoryId = story_id
    return req


def _http_resp(payload, status_code=200):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = payload
    r.raise_for_status = MagicMock()
    return r


def _service():
    """JiraService with the Jira duplicate lookup stubbed out."""
    svc = JiraService(db=MagicMock())
    svc.fetch_jira_duplicates = AsyncMock(return_value=(set(), set()))
    return svc


def _make_paging_client(responses):
    """
    Build an AsyncClient mock that works correctly when httpx.AsyncClient is
    instantiated *inside* a loop (new context manager each iteration).

    The patch replaces the class itself, so every call to
    ``httpx.AsyncClient(...)`` returns this mock.  Each ``async with`` block
    calls ``__aenter__`` once; we return the same client object so that
    ``client.get`` accumulates call count correctly.
    """
    response_iter = iter(responses)

    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(side_effect=lambda *a, **kw: next(response_iter))
    return client


class TestBuildFetchResponse:

    def test_stories_nested_under_matching_epic(self):
        result = JiraService.build_fetch_response([_epic(), _story()])
        assert len(result) == 1
        assert result[0]["epicId"] == "EP-1"
        assert result[0]["user_stories"][0]["storyId"] == "US-1"

    def test_story_title_comes_from_summary_field(self):
        """Regression: storyTitle must use summary, not the missing storyTitle key."""
        result = JiraService.build_fetch_response([_epic(), _story(summary="Correct")])
        assert result[0]["user_stories"][0]["storyTitle"] == "Correct"

    def test_orphan_story_no_parent_goes_to_ungrouped(self):
        result = JiraService.build_fetch_response([_story(parent_key=None)])
        ids = [e["epicId"] for e in result]
        assert "UNGROUPED" in ids
        ug = next(e for e in result if e["epicId"] == "UNGROUPED")
        assert ug["user_stories"][0]["storyId"] == "US-1"

    def test_orphan_story_unknown_parent_goes_to_ungrouped(self):
        """Story whose parent epic is absent from the issue list → UNGROUPED."""
        result = JiraService.build_fetch_response([_story(parent_key="EP-MISSING")])
        ids = [e["epicId"] for e in result]
        assert "UNGROUPED" in ids

    def test_no_ungrouped_when_all_stories_matched(self):
        """branch 202->192: ungrouped list is empty, UNGROUPED bucket must NOT be created."""
        result = JiraService.build_fetch_response([_epic(), _story()])
        assert all(e["epicId"] != "UNGROUPED" for e in result)

    def test_empty_input(self):
        assert JiraService.build_fetch_response([]) == []

    def test_multiple_epics_route_correctly(self):
        issues = [
            _epic("EP-1"),
            _epic("EP-2", "Second"),
            _story("US-1", parent_key="EP-1"),
            _story("US-2", parent_key="EP-2"),
        ]
        by_id = {e["epicId"]: e for e in JiraService.build_fetch_response(issues)}
        assert len(by_id["EP-1"]["user_stories"]) == 1
        assert len(by_id["EP-2"]["user_stories"]) == 1

    def test_user_story_issue_type_variant(self):
        """'user story' (with space) is also a valid story type."""
        issue = {
            "key": "US-10",
            "fields": {
                "issuetype": {"name": "User Story"},
                "summary": "A user story",
                "description": None,
                "parent": None,
                "customfield_10040": None,
                "customfield_10041": None,
            },
        }
        result = JiraService.build_fetch_response([issue])
        assert any(e["epicId"] == "UNGROUPED" for e in result)

    def test_epic_with_no_stories_has_empty_list(self):
        result = JiraService.build_fetch_response([_epic()])
        assert result[0]["user_stories"] == []

    def test_ungrouped_branch_with_mixed_story_membership(self):
        epic = _epic("EP-1")
        grouped_story = _story(key="US-1", summary="Grouped", parent_key="EP-1")
        ungrouped_story = _story(key="US-2", summary="Ungrouped", parent_key="EP-MISSING")

        result = JiraService.build_fetch_response([epic, grouped_story, ungrouped_story])

        epic_bucket = next(x for x in result if x["epicId"] == "EP-1")
        assert len(epic_bucket["user_stories"]) == 1
        assert epic_bucket["user_stories"][0]["storyId"] == "US-1"

        ungrouped_bucket = next(x for x in result if x["epicId"] == "UNGROUPED")
        assert len(ungrouped_bucket["user_stories"]) == 1
        assert ungrouped_bucket["user_stories"][0]["storyId"] == "US-2"

    def test_unknown_issue_type_ignored(self):
        bug = {
            "key": "BUG-1",
            "fields": {
                "issuetype": {"name": "Bug"},
                "summary": "A bug that should be ignored",
                "description": None,
                "parent": None,
                "customfield_10040": None,
                "customfield_10041": None,
            },
        }
        result = JiraService.build_fetch_response([_epic(), _story(), bug])

        # Only the epic bucket exists — BUG-1 must not appear anywhere
        assert len(result) == 1
        assert result[0]["epicId"] == "EP-1"
        all_story_ids = [s["storyId"] for s in result[0]["user_stories"]]
        assert "BUG-1" not in all_story_ids


class TestJiraAuth:
    @pytest.mark.parametrize("jira_email, api_token", [("", "token"), ("email", "")])
    def test_rejects_missing_credential_part(self, jira_email, api_token):
        with pytest.raises(JiraNotConfiguredException):
            _jira_auth(jira_email, api_token)


class TestFetchJiraData:

    @pytest.mark.asyncio
    async def test_single_page_happy_path(self):
        """total <= max_results: loop runs once, break fires immediately."""
        responses = [_http_resp({"issues": [_epic()], "total": 1})]
        client = _make_paging_client(responses)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService.fetch_jira_data(
                "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
            )

        assert result[0]["epicId"] == "EP-1"
        assert client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_401_raises_jira_auth_exception(self):
        """First page returns 401 → JiraAuthException raised immediately."""
        responses = [_http_resp({}, status_code=401)]
        client = _make_paging_client(responses)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            with pytest.raises(JiraAuthException):
                await JiraService.fetch_jira_data(
                    "https://jira.example.com", "PROJ", "bad", jira_email="me@example.com"
                )

    @pytest.mark.asyncio
    async def test_network_error_raises_jira_fetch_exception(self):
        """httpx.ConnectError (subclass of HTTPError) → wrapped as JiraFetchException."""
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            with pytest.raises(JiraFetchException):
                await JiraService.fetch_jira_data(
                    "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
                )

    @pytest.mark.asyncio
    async def test_paginates_when_total_exceeds_max_results(self):
        page1_issues = [_epic(f"EP-{i}") for i in range(100)]
        page2_issues = [_epic(f"EP-{i}") for i in range(100, 105)]

        responses = [
            _http_resp({"issues": page1_issues, "nextPageToken": "p2"}),
            _http_resp({"issues": page2_issues, "isLast": True}),
        ]
        client = _make_paging_client(responses)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService.fetch_jira_data(
                "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
            )

        # Both pages fetched
        assert client.get.call_count == 2
        # All 105 epics are present in the result
        returned_ids = {e["epicId"] for e in result}
        assert returned_ids == {f"EP-{i}" for i in range(105)}

    @pytest.mark.asyncio
    async def test_paginates_exactly_three_pages(self):
        """3-page scenario: follow nextPageToken until isLast."""
        responses = [
            _http_resp({"issues": [_epic(f"EP-{i}") for i in range(100)], "nextPageToken": "p2"}),
            _http_resp(
                {"issues": [_epic(f"EP-{i}") for i in range(100, 200)], "nextPageToken": "p3"}
            ),
            _http_resp({"issues": [_epic(f"EP-{i}") for i in range(200, 250)], "isLast": True}),
        ]
        client = _make_paging_client(responses)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService.fetch_jira_data(
                "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
            )

        assert client.get.call_count == 3
        assert {e["epicId"] for e in result} == {f"EP-{i}" for i in range(250)}

    @pytest.mark.asyncio
    async def test_401_on_second_page_raises_jira_auth_exception(self):
        """
        401 arriving on the second page (after the back-edge is already taken)
        must still raise JiraAuthException, not be swallowed.
        """
        responses = [
            _http_resp({"issues": [_epic("EP-1")], "nextPageToken": "p2"}),  # page 1: continue
            _http_resp({}, status_code=401),  # page 2: 401
        ]
        client = _make_paging_client(responses)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            with pytest.raises(JiraAuthException):
                await JiraService.fetch_jira_data(
                    "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
                )

        assert client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_marks_existing_story_statuses_from_database(self):
        responses = [
            _http_resp({"issues": [_epic("EP-1"), _story("US-1", "Existing Story")], "total": 1})
        ]
        client = _make_paging_client(responses)
        service = JiraService(db=MagicMock())

        with (
            patch("app.services.jiraService.httpx.AsyncClient", return_value=client),
            patch(
                "app.services.jiraService.get_existing_story_statuses",
                return_value={"US-1": {"already_exists": True, "status": "approved"}},
            ),
        ):
            result = await service.fetch_jira_data(
                "https://jira.example.com",
                "PROJ",
                "token",
                project_id=uuid.uuid4(),
                db=service.db,
                jira_email="me@example.com",
            )

        story = result[0]["user_stories"][0]
        assert story["already_exists"] is True
        assert story["status"] == "approved"


class TestStoryStatusEnrichmentHelpers:
    def test_get_existing_story_statuses_returns_empty_for_missing_db_or_keys(self):
        assert get_existing_story_statuses(None, ["US-1"], "project-1") == {}
        assert get_existing_story_statuses(MagicMock(), [], "project-1") == {}

    def test_get_existing_story_statuses_normalizes_statuses_and_skips_blank_keys(self):
        db = MagicMock()
        project_id = uuid.uuid4()
        rows = [("US-1", "Approved"), ("US-2", "   "), ("", "ignored"), ("US-3", None)]

        stories_query = MagicMock()
        stories_query.join.return_value.filter.return_value.all.return_value = rows
        pending_query = MagicMock()
        pending_query.filter.return_value.distinct.return_value.all.return_value = []
        db.query.side_effect = [stories_query, pending_query]

        result = get_existing_story_statuses(db, ["US-1", "US-2", "", "US-3"], project_id)

        assert result == {
            "US-1": {"already_exists": True, "status": "approved"},
            "US-2": {"already_exists": True, "status": "pending"},
            "US-3": {"already_exists": True, "status": "pending"},
        }

    def test_get_existing_story_statuses_marks_stories_awaiting_review(self):
        """A pending approval request reports 'pending_approval', overriding a NULL or
        'rejected' user_stories.status — and even when no user_stories row exists yet
        (legacy submissions made before stories were persisted at submit time)."""
        db = MagicMock()
        project_id = uuid.uuid4()
        rows = [("US-1", None), ("US-2", "rejected")]

        stories_query = MagicMock()
        stories_query.join.return_value.filter.return_value.all.return_value = rows
        pending_query = MagicMock()
        # US-1 has a user_stories row; US-3 is a legacy pending request with none.
        pending_query.filter.return_value.distinct.return_value.all.return_value = [
            ("US-1",),
            ("US-3",),
        ]
        db.query.side_effect = [stories_query, pending_query]

        result = get_existing_story_statuses(db, ["US-1", "US-2", "US-3"], project_id)

        assert result == {
            "US-1": {"already_exists": True, "status": "pending_approval"},
            "US-2": {"already_exists": True, "status": "rejected"},
            "US-3": {"already_exists": True, "status": "pending_approval"},
        }

    def test_get_existing_story_statuses_returns_empty_when_all_keys_blank(self):
        db = MagicMock()

        result = get_existing_story_statuses(db, ["", None], "project-1")

        assert result == {}
        db.query.assert_not_called()

    def test_enrich_story_statuses_returns_empty_payload_unchanged(self):
        assert JiraService.enrich_story_statuses([]) == []

    def test_enrich_story_statuses_sets_defaults_when_db_missing(self):
        payload = [{"epicId": "EP-1", "user_stories": [{"storyId": "US-1"}]}]

        result = JiraService.enrich_story_statuses(payload, db=None)

        story = result[0]["user_stories"][0]
        assert story["already_exists"] is False
        assert story["status"] == "pending"

    def test_enrich_story_statuses_defaults_for_unmatched_story_keys(self):
        payload = [{"epicId": "EP-1", "user_stories": [{"storyId": "US-1"}]}]
        db = MagicMock()
        project_id = uuid.uuid4()

        with patch(
            "app.services.jiraService.get_existing_story_statuses",
            return_value={"US-2": {"already_exists": True, "status": "approved"}},
        ) as mock_existing_statuses:
            result = JiraService.enrich_story_statuses(payload, db=db, project_id=project_id)

        mock_existing_statuses.assert_called_once_with(db, ["US-1"], project_id)
        story = result[0]["user_stories"][0]
        assert story["already_exists"] is False
        assert story["status"] == "pending"


class TestBuildJql:

    def test_no_statuses_returns_plain_project_query(self):
        jql = JiraService._build_jql("PROJ", None)
        assert jql == 'project = "PROJ" ORDER BY created DESC'

    def test_empty_and_blank_statuses_ignored(self):
        jql = JiraService._build_jql("PROJ", ["", "   "])
        assert jql == 'project = "PROJ" ORDER BY created DESC'

    def test_single_status_keeps_epics(self):
        jql = JiraService._build_jql("PROJ", ["In Progress"])
        assert jql == (
            'project = "PROJ" AND (issuetype = Epic OR '
            '(issuetype in (Story, "User Story") AND status in ("In Progress"))) '
            "ORDER BY created DESC"
        )

    def test_multiple_statuses_comma_joined(self):
        jql = JiraService._build_jql("PROJ", ["To Do", "Done"])
        assert 'status in ("To Do", "Done")' in jql

    def test_status_with_quote_is_escaped(self):
        jql = JiraService._build_jql("PROJ", ['Blocked "hard"'])
        assert r'"Blocked \"hard\""' in jql


class TestFetchJiraDataStatusFilter:

    @pytest.mark.asyncio
    async def test_statuses_threaded_into_jql_param(self):
        client = _make_paging_client([_http_resp({"issues": [_epic()], "total": 1})])
        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            await JiraService.fetch_jira_data(
                "https://jira.example.com",
                "PROJ",
                "token",
                statuses=["In Progress"],
                jira_email="me@example.com",
            )
        _, kwargs = client.get.call_args
        assert 'status in ("In Progress")' in kwargs["params"]["jql"]


class TestFetchProjectStatuses:

    @pytest.mark.asyncio
    async def test_returns_distinct_story_status_names(self):
        payload = {
            "issues": [
                {"fields": {"status": {"name": "To Do"}}},
                {"fields": {"status": {"name": "In Progress"}}},
                {"fields": {"status": {"name": "Done"}}},
            ]
        }
        client = _make_paging_client([_http_resp(payload)])
        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService.fetch_project_story_statuses(
                "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
            )
        assert set(result) == {"To Do", "In Progress", "Done"}

    @pytest.mark.asyncio
    async def test_duplicate_statuses_collapsed(self):
        payload = {
            "issues": [
                {"fields": {"status": {"name": "In Progress"}}},
                {"fields": {"status": {"name": "In Progress"}}},
                {"fields": {"status": {"name": "To Do"}}},
            ]
        }
        client = _make_paging_client([_http_resp(payload)])
        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService.fetch_project_story_statuses(
                "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
            )
        assert sorted(result) == ["In Progress", "To Do"]

    @pytest.mark.asyncio
    async def test_skips_issues_with_no_status_name(self):
        # A missing/blank status name must be skipped rather than added as an empty
        # option in the caller's filter dropdown.
        payload = {
            "issues": [
                {"fields": {"status": {"name": "To Do"}}},
                {"fields": {"status": {}}},
                {"fields": {}},
                {},
            ]
        }
        client = _make_paging_client([_http_resp(payload)])
        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService.fetch_project_story_statuses(
                "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
            )
        assert result == ["To Do"]

    @pytest.mark.asyncio
    async def test_paginates_until_all_statuses_collected(self):
        page1 = {
            "issues": [{"fields": {"status": {"name": "To Do"}}} for _ in range(100)],
            "nextPageToken": "p2",
        }
        # Status that appears only on the second page must not be missed.
        page2 = {"issues": [{"fields": {"status": {"name": "Blocked"}}}], "isLast": True}
        client = _make_paging_client([_http_resp(page1), _http_resp(page2)])
        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService.fetch_project_story_statuses(
                "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
            )
        assert set(result) == {"To Do", "Blocked"}
        assert client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_401_raises_jira_auth_exception(self):
        client = _make_paging_client([_http_resp({}, status_code=401)])
        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            with pytest.raises(JiraAuthException):
                await JiraService.fetch_project_story_statuses(
                    "https://jira.example.com", "PROJ", "bad", jira_email="me@example.com"
                )

    @pytest.mark.asyncio
    async def test_network_error_raises_jira_fetch_exception(self):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            with pytest.raises(JiraFetchException):
                await JiraService.fetch_project_story_statuses(
                    "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
                )


class TestFetchJiraDuplicates:
    @staticmethod
    def _svc():
        return JiraService(db=MagicMock())

    @pytest.mark.asyncio
    @patch("app.services.jiraService.httpx.AsyncClient")
    async def test_returns_ids_and_titles_from_jira(self, MockClient):
        client_instance = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"issues": [{"fields": {"summary": "TC-1 - My Test Title"}}]}
        client_instance.get = AsyncMock(return_value=resp)

        jira_ids, jira_titles = await self._svc().fetch_jira_duplicates(
            [{"id": "TC-1", "title": "My Test Title"}],
            "https://jira.example.com",
            "PROJ",
            "tok",
            jira_email="me@example.com",
        )
        assert len(jira_ids) > 0
        assert len(jira_titles) > 0

    @pytest.mark.asyncio
    async def test_empty_test_cases_returns_empty_sets(self):
        jira_ids, jira_titles = await self._svc().fetch_jira_duplicates(
            [], "https://jira.example.com", "PROJ", "tok", jira_email="me@example.com"
        )
        assert jira_ids == set()
        assert jira_titles == set()

    @pytest.mark.asyncio
    @patch("app.services.jiraService.httpx.AsyncClient")
    async def test_http_error_returns_empty_sets(self, MockClient):
        client_instance = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        client_instance.get = AsyncMock(side_effect=httpx.HTTPError("fail"))

        jira_ids, jira_titles = await self._svc().fetch_jira_duplicates(
            [{"id": "TC-1", "title": "T"}],
            "https://jira.example.com",
            "PROJ",
            "tok",
            jira_email="me@example.com",
        )
        assert jira_ids == set()
        assert jira_titles == set()

    @pytest.mark.asyncio
    @patch("app.services.jiraService.httpx.AsyncClient")
    async def test_issue_with_no_separator_not_added(self, MockClient):
        client_instance = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"issues": [{"fields": {"summary": "NoSeparatorHere"}}]}
        client_instance.get = AsyncMock(return_value=resp)

        jira_ids, jira_titles = await self._svc().fetch_jira_duplicates(
            [{"id": "TC-1", "title": "T"}],
            "https://jira.example.com",
            "PROJ",
            "tok",
            jira_email="me@example.com",
        )
        assert jira_ids == set()
        assert jira_titles == set()

    @pytest.mark.asyncio
    @patch("app.services.jiraService.httpx.AsyncClient")
    async def test_test_case_with_no_id_still_builds_title_condition(self, MockClient):
        client_instance = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"issues": []}
        client_instance.get = AsyncMock(return_value=resp)

        jira_ids, _ = await self._svc().fetch_jira_duplicates(
            [{"id": "", "title": "T"}],
            "https://jira.example.com",
            "PROJ",
            "tok",
            jira_email="me@example.com",
        )
        assert jira_ids == set()

    @pytest.mark.asyncio
    @patch("app.services.jiraService.httpx.AsyncClient")
    async def test_test_case_with_no_title_still_builds_id_condition(self, MockClient):
        client_instance = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"issues": []}
        client_instance.get = AsyncMock(return_value=resp)

        _, jira_titles = await self._svc().fetch_jira_duplicates(
            [{"id": "TC-1", "title": ""}],
            "https://jira.example.com",
            "PROJ",
            "tok",
            jira_email="me@example.com",
        )
        assert jira_titles == set()


def _make_post_client(post_return=None, post_side_effect=None):
    """AsyncClient mock suitable for push_bulk_to_jira (uses POST, single call)."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    if post_side_effect is not None:
        client.post = AsyncMock(side_effect=post_side_effect)
    else:
        client.post = AsyncMock(return_value=post_return)
    return client


class TestPushBulkToJira:

    @pytest.mark.asyncio
    async def test_happy_path_all_accepted(self):
        resp = _http_resp({"issues": [{"key": "TEST-1"}], "errors": []})
        client = _make_post_client(post_return=resp)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            success, failed = await _service().push_bulk_to_jira(
                [_make_test_case()],
                "bdd",
                user_story_id="US-1",
                jira_url="https://jira.example.com",
                project_key="PROJ",
                api_token="tok",
                jira_email="me@example.com",
            )

        assert len(success) == 1
        assert success[0]["jira_key"] == "TEST-1"
        assert failed == []

    @pytest.mark.asyncio
    async def test_unknown_issue_type_ignored(self):
        client = _make_post_client(post_side_effect=httpx.HTTPError("down"))

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            success, failed = await _service().push_bulk_to_jira(
                [_make_test_case()],
                "bdd",
                user_story_id="US-1",
                jira_url="https://jira.example.com",
                project_key="PROJ",
                api_token="tok",
                jira_email="me@example.com",
            )

        assert success == []
        assert len(failed) == 1
        assert failed[0]["tc_id"] == "TC-1"

    @pytest.mark.asyncio
    async def test_partial_jira_errors_split_into_both_lists(self):
        tc1 = _make_test_case("TC-1", "Test One")
        tc2 = _make_test_case("TC-2", "Test Two")

        resp = _http_resp(
            {
                "issues": [{"key": "TEST-1"}],
                "errors": [{"failedElementNumber": 1, "elementErrors": {"msg": "bad"}}],
            }
        )
        client = _make_post_client(post_return=resp)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            success, failed = await _service().push_bulk_to_jira(
                [tc1, tc2],
                "bdd",
                user_story_id="US-1",
                jira_url="https://jira.example.com",
                project_key="PROJ",
                api_token="tok",
                jira_email="me@example.com",
            )

        assert len(success) == 1
        assert success[0]["jira_key"] == "TEST-1"
        assert len(failed) == 1
        assert failed[0]["tc_id"] == "TC-2"


_BULK_SAVE_PATH = "app.services.jiraService.bulk_save_test_cases"


def _patch_creds(svc):
    return patch.object(
        svc,
        "get_project_jira_credentials",
        return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok"),
    )


def _mock_db_result(inserted=1):
    r = MagicMock()
    r.inserted = [{"id": f"TC-{i}"} for i in range(inserted)]
    r.skipped = []
    r.failed = []
    return r


class TestPushToJira:

    @pytest.mark.asyncio
    async def test_happy_path_empty_failures(self):
        svc = _service()
        bulk_success = [{"tc": _make_test_case(), "tc_id": "TC-1", "jira_key": "TEST-1"}]

        with (
            patch.object(svc, "push_bulk_to_jira", new=AsyncMock(return_value=(bulk_success, []))),
            _patch_creds(svc),
        ):
            resp = await svc.push_to_jira(_make_request(), user_id="user-1")

        assert resp.pushed_count == 1
        assert resp.failed_count == 0
        assert resp.duplicate_count == 0
        assert resp.db_saved_count == 0

    @pytest.mark.asyncio
    async def test_happy_path_with_db_saves_and_counts(self):
        svc = _service()

        bulk_success = [
            {
                "tc": _make_test_case(),
                "tc_id": "TC-1",
                "jira_key": "TEST-1",
            }
        ]

        with (
            patch.object(
                svc,
                "push_bulk_to_jira",
                new=AsyncMock(return_value=(bulk_success, [])),
            ),
            patch("app.services.jiraService.update_jira_key") as mock_update,
            _patch_creds(svc),
        ):
            resp = await svc.push_to_jira(
                _make_request(),
                user_id="user-1",
            )

        mock_update.assert_called_once()
        assert resp.pushed_count == 1

    @pytest.mark.asyncio
    async def test_db_update_exception_propagates(self):
        svc = _service()

        bulk_success = [
            {
                "tc": _make_test_case(),
                "tc_id": "TC-1",
                "jira_key": "TEST-1",
            }
        ]

        with (
            patch.object(
                svc,
                "push_bulk_to_jira",
                new=AsyncMock(return_value=(bulk_success, [])),
            ),
            patch(
                "app.services.jiraService.update_jira_key",
                side_effect=Exception("DB down"),
            ),
            _patch_creds(svc),
        ):
            with pytest.raises(Exception, match="DB down"):
                await svc.push_to_jira(
                    _make_request(),
                    user_id="user-1",
                )

    @pytest.mark.asyncio
    async def test_in_session_duplicate_skipped(self):
        from app.constants import ACTION_SKIP

        svc = _service()
        with (
            patch(
                "app.services.jiraService.validate_and_register_test_case",
                return_value=ACTION_SKIP,
            ),
            patch.object(svc, "push_bulk_to_jira", new=AsyncMock(return_value=([], []))),
            _patch_creds(svc),
        ):
            resp = await svc.push_to_jira(_make_request(), user_id="user-1")

        assert resp.duplicate_count == 1
        assert resp.pushed_count == 0

    @pytest.mark.asyncio
    async def test_jira_duplicate_by_id_skipped(self):
        from app.services.internal import normalize_text

        tc = _make_test_case("TC-DUP", "Unique Title")
        svc = _service()
        svc.fetch_jira_duplicates = AsyncMock(return_value=({normalize_text("TC-DUP")}, set()))
        with (
            patch.object(svc, "push_bulk_to_jira", new=AsyncMock(return_value=([], []))),
            _patch_creds(svc),
        ):
            resp = await svc.push_to_jira(_make_request(test_cases=[tc]), user_id="user-1")

        assert resp.duplicate_count == 1

    @pytest.mark.asyncio
    async def test_jira_duplicate_by_title_skipped(self):
        from app.services.internal import normalize_text

        tc = _make_test_case("TC-NEW", "Existing Title")
        svc = _service()
        svc.fetch_jira_duplicates = AsyncMock(
            return_value=(set(), {normalize_text("Existing Title")})
        )
        with (
            patch.object(svc, "push_bulk_to_jira", new=AsyncMock(return_value=([], []))),
            _patch_creds(svc),
        ):
            resp = await svc.push_to_jira(_make_request(test_cases=[tc]), user_id="user-1")

        assert resp.duplicate_count == 1

    @pytest.mark.asyncio
    async def test_bulk_failed_items_appear_in_failed_list(self):
        svc = _service()
        bulk_failed = [{"tc_id": "TC-1", "error": "bad field"}]

        with (
            patch.object(svc, "push_bulk_to_jira", new=AsyncMock(return_value=([], bulk_failed))),
            _patch_creds(svc),
        ):
            resp = await svc.push_to_jira(_make_request(), user_id="user-1")

        assert resp.failed_count == 1
        assert resp.pushed_count == 0

    @pytest.mark.asyncio
    async def test_response_total_equals_request_length(self):
        svc = _service()
        tcs = [_make_test_case(f"TC-{i}", f"Title {i}") for i in range(5)]

        with (
            patch.object(svc, "push_bulk_to_jira", new=AsyncMock(return_value=([], []))),
            _patch_creds(svc),
        ):
            resp = await svc.push_to_jira(_make_request(test_cases=tcs), user_id="user-1")

        assert resp.total == 5


class TestJiraServiceConfigAndConnection:
    def test_get_project_jira_credentials_raises_when_project_missing(self):
        svc = JiraService(db=MagicMock())

        with patch("app.services.jiraService.get_project_by_id", return_value=None):
            with pytest.raises(DatabaseOperationException, match="Project proj-1 not found"):
                svc.get_project_jira_credentials("proj-1", "user-1")

    def test_get_project_jira_credentials_raises_when_required_values_missing(self):
        svc = JiraService(db=MagicMock())
        project = SimpleNamespace(jira_url="   ", jira_project_key="   ")
        user = SimpleNamespace(jira_email="   ", jira_api_token="   ")

        with (
            patch("app.services.jiraService.get_project_by_id", return_value=project),
            patch("app.services.jiraService.get_user_by_id", return_value=user),
            patch("app.services.jiraService.decrypt_token", side_effect=lambda t: t),
        ):
            with pytest.raises(JiraNotConfiguredException):
                svc.get_project_jira_credentials("proj-1", "user-1")

    def test_get_project_jira_credentials_returns_resolved_values(self):
        svc = JiraService(db=MagicMock())
        project = SimpleNamespace(jira_url=" https://jira.example.com ", jira_project_key=" PROJ ")
        user = SimpleNamespace(jira_email=" me@example.com ", jira_api_token="encrypted-token")

        with (
            patch("app.services.jiraService.get_project_by_id", return_value=project),
            patch("app.services.jiraService.get_user_by_id", return_value=user),
            patch(
                "app.services.jiraService.decrypt_token",
                side_effect=lambda t: " token " if t == "encrypted-token" else t,
            ),
        ):
            resolved = svc.get_project_jira_credentials("proj-1", "user-1")

        assert resolved == ("https://jira.example.com", "PROJ", "me@example.com", "token")

    def test_get_jira_config_returns_saved_values(self):
        svc = JiraService(db=MagicMock())
        project = SimpleNamespace(jira_url="https://jira.example.com", jira_project_key="PROJ")

        with patch("app.services.jiraService.get_project_by_id", return_value=project):
            response = svc.get_jira_config("proj-1", "user-1")

        assert response.jira_url == "https://jira.example.com"
        assert response.project_key == "PROJ"
        assert response.is_connected is False

    def test_get_jira_config_raises_when_project_missing(self):
        svc = JiraService(db=MagicMock())

        with patch("app.services.jiraService.get_project_by_id", return_value=None):
            with pytest.raises(DatabaseOperationException, match="Project proj-1 not found"):
                svc.get_jira_config("proj-1", "user-1")

    def test_save_jira_config_updates_project(self):
        svc = JiraService(db=MagicMock())
        payload = SimpleNamespace(jira_url="https://example.atlassian.net", project_key="PROJ")
        updated_project = SimpleNamespace(
            jira_url="https://example.atlassian.net", jira_project_key="PROJ"
        )

        with (
            patch("app.services.jiraService.validate_jira_url") as mock_validate,
            patch(
                "app.services.jiraService.update_project_jira_config",
                return_value=updated_project,
            ) as mock_update_project,
        ):
            response = svc.save_jira_config("proj-1", "user-1", payload)

        mock_validate.assert_called_once_with(payload.jira_url)
        mock_update_project.assert_called_once()
        assert response.project_key == "PROJ"

    def test_save_jira_config_skips_url_validation_when_blank(self):
        svc = JiraService(db=MagicMock())
        payload = SimpleNamespace(jira_url="", project_key="PROJ")
        updated_project = SimpleNamespace(
            jira_url="https://jira.example.com", jira_project_key="PROJ"
        )

        with (
            patch("app.services.jiraService.validate_jira_url") as mock_validate,
            patch(
                "app.services.jiraService.update_project_jira_config",
                return_value=updated_project,
            ),
        ):
            response = svc.save_jira_config("proj-1", "user-1", payload)

        mock_validate.assert_not_called()
        assert response.jira_url == "https://jira.example.com"

    @pytest.mark.asyncio
    async def test_test_connection_returns_false_when_required_config_missing(self):
        svc = JiraService(db=MagicMock())
        project = SimpleNamespace(jira_url="", jira_project_key="")
        user = SimpleNamespace(jira_email="", jira_api_token="")

        with (
            patch("app.services.jiraService.get_project_by_id", return_value=project),
            patch("app.services.jiraService.get_user_by_id", return_value=user),
        ):
            response = await svc.test_connection("proj-1", "user-1")

        assert response.success is False
        assert "must" in response.message

    @pytest.mark.asyncio
    async def test_test_connection_raises_when_project_missing(self):
        svc = JiraService(db=MagicMock())

        with patch("app.services.jiraService.get_project_by_id", return_value=None):
            with pytest.raises(DatabaseOperationException, match="Project proj-1 not found"):
                await svc.test_connection("proj-1", "user-1")

    @pytest.mark.asyncio
    async def test_test_connection_reports_auth_error(self):
        svc = JiraService(db=MagicMock())
        project = SimpleNamespace(jira_url="https://jira.example.com", jira_project_key="PROJ")
        user = SimpleNamespace(jira_email="test@example.com", jira_api_token="token")
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(
            return_value=MagicMock(status_code=401, raise_for_status=MagicMock())
        )

        with (
            patch("app.services.jiraService.get_project_by_id", return_value=project),
            patch("app.services.jiraService.get_user_by_id", return_value=user),
            patch("app.services.jiraService.httpx.AsyncClient", return_value=client),
            patch("app.services.jiraService.decrypt_token", side_effect=lambda t: t),
        ):
            response = await svc.test_connection("proj-1", "user-1")

        assert response.success is False
        assert response.message == "Authentication failed. Check the email and API token."

    @pytest.mark.asyncio
    async def test_test_connection_reports_missing_project_key(self):
        svc = JiraService(db=MagicMock())
        project = SimpleNamespace(jira_url="https://jira.example.com", jira_project_key="PROJ")
        user = SimpleNamespace(jira_email="test@example.com", jira_api_token="token")
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        me_response = MagicMock(status_code=200, raise_for_status=MagicMock())
        project_response = MagicMock(status_code=404, raise_for_status=MagicMock())
        client.get = AsyncMock(side_effect=[me_response, project_response])

        with (
            patch("app.services.jiraService.get_project_by_id", return_value=project),
            patch("app.services.jiraService.get_user_by_id", return_value=user),
            patch("app.services.jiraService.httpx.AsyncClient", return_value=client),
            patch("app.services.jiraService.decrypt_token", side_effect=lambda t: t),
        ):
            response = await svc.test_connection("proj-1", "user-1")

        assert response.success is False
        assert response.message == 'Project key "PROJ" was not found on this Jira instance.'

    @pytest.mark.asyncio
    async def test_test_connection_succeeds_when_http_calls_pass(self):
        svc = JiraService(db=MagicMock())
        project = SimpleNamespace(jira_url="https://jira.example.com", jira_project_key="PROJ")
        user = SimpleNamespace(jira_email="test@example.com", jira_api_token="token")
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        me_response = MagicMock(status_code=200, raise_for_status=MagicMock())
        project_response = MagicMock(status_code=200, raise_for_status=MagicMock())
        client.get = AsyncMock(side_effect=[me_response, project_response])

        with (
            patch("app.services.jiraService.get_project_by_id", return_value=project),
            patch("app.services.jiraService.get_user_by_id", return_value=user),
            patch("app.services.jiraService.httpx.AsyncClient", return_value=client),
            patch("app.services.jiraService.decrypt_token", side_effect=lambda t: t),
        ):
            response = await svc.test_connection("proj-1", "user-1")

        assert response.success is True
        assert response.message == "Connection successful."

    @pytest.mark.asyncio
    async def test_test_connection_handles_http_errors(self):
        svc = JiraService(db=MagicMock())
        project = SimpleNamespace(jira_url="https://jira.example.com", jira_project_key="PROJ")
        user = SimpleNamespace(jira_email="test@example.com", jira_api_token="token")
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))

        with (
            patch("app.services.jiraService.get_project_by_id", return_value=project),
            patch("app.services.jiraService.get_user_by_id", return_value=user),
            patch("app.services.jiraService.httpx.AsyncClient", return_value=client),
            patch("app.services.jiraService.decrypt_token", side_effect=lambda t: t),
        ):
            response = await svc.test_connection("proj-1", "user-1")

        assert response.success is False
        assert (
            response.message
            == "Could not reach the Jira instance. Check the Jira URL and try again."
        )

    def test_get_my_jira_credentials_returns_saved_email_and_token_flag(self):
        svc = JiraService(db=MagicMock())
        user = SimpleNamespace(jira_email="me@example.com", jira_api_token="encrypted")

        with patch("app.services.jiraService.get_user_by_id", return_value=user):
            response = svc.get_my_jira_credentials("user-1")

        assert response.jira_email == "me@example.com"
        assert response.has_api_token is True

    def test_get_my_jira_credentials_defaults_when_user_missing(self):
        svc = JiraService(db=MagicMock())

        with patch("app.services.jiraService.get_user_by_id", return_value=None):
            response = svc.get_my_jira_credentials("user-1")

        assert response.jira_email is None
        assert response.has_api_token is False

    @pytest.mark.asyncio
    async def test_save_my_jira_credentials_saves_when_jira_verifies_the_pair(self):
        svc = JiraService(db=MagicMock())
        payload = SimpleNamespace(jira_email="me@example.com", api_token="tok")
        updated_user = SimpleNamespace(jira_email="me@example.com", jira_api_token="encrypted")

        with (
            patch("app.services.jiraService.get_user_by_id", return_value=None),
            patch.object(JiraService, "_verify_credentials_for_user", AsyncMock()) as mock_verify,
            patch(
                "app.services.jiraService.update_user_jira_credentials",
                return_value=updated_user,
            ) as mock_update,
        ):
            response = await svc.save_my_jira_credentials("user-1", payload)

        mock_verify.assert_awaited_once_with("user-1", "me@example.com", "tok")
        mock_update.assert_called_once_with(
            svc.db, "user-1", jira_email="me@example.com", jira_api_token="tok"
        )
        assert response.jira_email == "me@example.com"
        assert response.has_api_token is True

    @pytest.mark.asyncio
    async def test_save_my_jira_credentials_verifies_email_only_edit_against_saved_token(self):
        """An email-only edit still has to be verified, using the stored token,
        or a mismatched pair could be saved without ever being checked."""
        svc = JiraService(db=MagicMock())
        payload = SimpleNamespace(jira_email="new@example.com", api_token=None)
        existing = SimpleNamespace(jira_email="old@example.com", jira_api_token="encrypted")
        updated_user = SimpleNamespace(jira_email="new@example.com", jira_api_token="encrypted")

        with (
            patch("app.services.jiraService.get_user_by_id", return_value=existing),
            patch("app.services.jiraService.decrypt_token", return_value="stored-tok"),
            patch.object(JiraService, "_verify_credentials_for_user", AsyncMock()) as mock_verify,
            patch(
                "app.services.jiraService.update_user_jira_credentials",
                return_value=updated_user,
            ),
        ):
            await svc.save_my_jira_credentials("user-1", payload)

        mock_verify.assert_awaited_once_with("user-1", "new@example.com", "stored-tok")

    @pytest.mark.asyncio
    async def test_save_my_jira_credentials_clears_a_revoked_token_without_verifying(self):
        """Clearing the token must not verify the token being deleted — a
        revoked one would fail and leave the user unable to remove it."""
        svc = JiraService(db=MagicMock())
        payload = SimpleNamespace(jira_email="me@example.com", api_token="")
        existing = SimpleNamespace(jira_email="me@example.com", jira_api_token="encrypted")
        updated_user = SimpleNamespace(jira_email="me@example.com", jira_api_token=None)

        with (
            patch("app.services.jiraService.get_user_by_id", return_value=existing),
            patch.object(JiraService, "_verify_credentials_for_user", AsyncMock()) as mock_verify,
            patch(
                "app.services.jiraService.update_user_jira_credentials",
                return_value=updated_user,
            ) as mock_update,
        ):
            response = await svc.save_my_jira_credentials("user-1", payload)

        mock_verify.assert_not_awaited()
        mock_update.assert_called_once_with(
            svc.db, "user-1", jira_email="me@example.com", jira_api_token=""
        )
        assert response.has_api_token is False

    @pytest.mark.asyncio
    async def test_save_my_jira_credentials_clears_the_email_without_verifying(self):
        """Blanking the email is reachable from the Profile form; it must not
        verify the stored email it is about to replace."""
        svc = JiraService(db=MagicMock())
        payload = SimpleNamespace(jira_email="", api_token=None)
        existing = SimpleNamespace(jira_email="me@example.com", jira_api_token="encrypted")
        updated_user = SimpleNamespace(jira_email=None, jira_api_token="encrypted")

        with (
            patch("app.services.jiraService.get_user_by_id", return_value=existing),
            patch("app.services.jiraService.decrypt_token", return_value="stored-tok"),
            patch.object(JiraService, "_verify_credentials_for_user", AsyncMock()) as mock_verify,
            patch(
                "app.services.jiraService.update_user_jira_credentials",
                return_value=updated_user,
            ) as mock_update,
        ):
            await svc.save_my_jira_credentials("user-1", payload)

        mock_verify.assert_not_awaited()
        mock_update.assert_called_once_with(svc.db, "user-1", jira_email="", jira_api_token=None)

    @pytest.mark.asyncio
    async def test_save_my_jira_credentials_strips_whitespace_before_saving(self):
        """The stripped pair is what gets verified, so it must also be what is
        stored — otherwise a padded value is saved that Jira never approved."""
        svc = JiraService(db=MagicMock())
        payload = SimpleNamespace(jira_email="  me@example.com  ", api_token="  tok  ")
        updated_user = SimpleNamespace(jira_email="me@example.com", jira_api_token="encrypted")

        with (
            patch("app.services.jiraService.get_user_by_id", return_value=None),
            patch.object(JiraService, "_verify_credentials_for_user", AsyncMock()),
            patch(
                "app.services.jiraService.update_user_jira_credentials",
                return_value=updated_user,
            ) as mock_update,
        ):
            await svc.save_my_jira_credentials("user-1", payload)

        mock_update.assert_called_once_with(
            svc.db, "user-1", jira_email="me@example.com", jira_api_token="tok"
        )

    @pytest.mark.asyncio
    async def test_save_my_jira_credentials_does_not_decrypt_when_token_is_replaced(self):
        """A retyped token makes the stored one irrelevant; decrypting it anyway
        would let a rotated key block the save."""
        svc = JiraService(db=MagicMock())
        payload = SimpleNamespace(jira_email=None, api_token="new-tok")
        existing = SimpleNamespace(jira_email="me@example.com", jira_api_token="encrypted")
        updated_user = SimpleNamespace(jira_email="me@example.com", jira_api_token="encrypted")

        with (
            patch("app.services.jiraService.get_user_by_id", return_value=existing),
            patch("app.services.jiraService.decrypt_token") as mock_decrypt,
            patch.object(JiraService, "_verify_credentials_for_user", AsyncMock()) as mock_verify,
            patch(
                "app.services.jiraService.update_user_jira_credentials",
                return_value=updated_user,
            ),
        ):
            await svc.save_my_jira_credentials("user-1", payload)

        mock_decrypt.assert_not_called()
        mock_verify.assert_awaited_once_with("user-1", "me@example.com", "new-tok")

    def test_stored_api_token_treats_an_undecryptable_token_as_absent(self):
        """A rotated encryption key must not trap the user with credentials they
        can no longer replace."""
        user = SimpleNamespace(id="user-1", jira_email="me@example.com", jira_api_token="corrupt")

        with patch("app.services.jiraService.decrypt_token", side_effect=ValueError("bad key")):
            assert JiraService._stored_api_token(user) == ""

    def test_stored_api_token_returns_empty_when_nothing_saved(self):
        assert JiraService._stored_api_token(None) == ""
        assert JiraService._stored_api_token(SimpleNamespace(id="u", jira_api_token=None)) == ""

    @pytest.mark.asyncio
    async def test_save_my_jira_credentials_does_not_save_when_verification_fails(self):
        svc = JiraService(db=MagicMock())
        payload = SimpleNamespace(jira_email="me@example.com", api_token="bad-tok")

        with (
            patch("app.services.jiraService.get_user_by_id", return_value=None),
            patch.object(
                JiraService,
                "_verify_credentials_for_user",
                AsyncMock(side_effect=JiraCredentialsInvalidException()),
            ),
            patch("app.services.jiraService.update_user_jira_credentials") as mock_update,
        ):
            with pytest.raises(JiraCredentialsInvalidException):
                await svc.save_my_jira_credentials("user-1", payload)

        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_verify_credentials_raises_when_user_has_no_jira_instance(self):
        svc = JiraService(db=MagicMock())

        with patch("app.services.jiraService.get_configured_jira_urls_for_user", return_value=[]):
            with pytest.raises(JiraInstanceNotConfiguredException):
                await svc._verify_credentials_for_user("user-1", "me@example.com", "tok")

    @pytest.mark.asyncio
    async def test_verify_credentials_tries_the_next_instance_when_the_first_cannot_confirm(self):
        """A 401 only rules out that tenant — a consultant's token is valid on
        one client's Jira and not another's."""
        svc = JiraService(db=MagicMock())

        with (
            patch(
                "app.services.jiraService.get_configured_jira_urls_for_user",
                return_value=["https://client-a.atlassian.net", "https://client-b.atlassian.net"],
            ),
            patch.object(
                JiraService,
                "_fetch_jira_account_email",
                AsyncMock(side_effect=[None, "me@example.com"]),
            ) as mock_fetch,
        ):
            await svc._verify_credentials_for_user("user-1", "me@example.com", "tok")

        assert mock_fetch.await_count == 2

    @pytest.mark.asyncio
    async def test_verify_credentials_rejects_a_mismatch_without_trying_more_instances(self):
        svc = JiraService(db=MagicMock())

        with (
            patch(
                "app.services.jiraService.get_configured_jira_urls_for_user",
                return_value=["https://client-a.atlassian.net", "https://client-b.atlassian.net"],
            ),
            patch.object(
                JiraService,
                "_fetch_jira_account_email",
                AsyncMock(return_value="someone.else@example.com"),
            ) as mock_fetch,
        ):
            with pytest.raises(JiraCredentialsInvalidException, match="someone.else@example.com"):
                await svc._verify_credentials_for_user("user-1", "me@example.com", "tok")

        assert mock_fetch.await_count == 1

    @pytest.mark.asyncio
    async def test_verify_credentials_rejects_when_no_instance_could_confirm(self):
        svc = JiraService(db=MagicMock())

        with (
            patch(
                "app.services.jiraService.get_configured_jira_urls_for_user",
                return_value=["https://client-a.atlassian.net"],
            ),
            patch.object(JiraService, "_fetch_jira_account_email", AsyncMock(return_value=None)),
        ):
            with pytest.raises(JiraCredentialsInvalidException):
                await svc._verify_credentials_for_user("user-1", "me@example.com", "tok")

    @pytest.mark.asyncio
    async def test_verify_credentials_accepts_matching_account_ignoring_case(self):
        svc = JiraService(db=MagicMock())

        with (
            patch(
                "app.services.jiraService.get_configured_jira_urls_for_user",
                return_value=["https://jira.example.com"],
            ),
            patch.object(
                JiraService, "_fetch_jira_account_email", AsyncMock(return_value="Me@Example.com")
            ),
        ):
            await svc._verify_credentials_for_user("user-1", "me@example.com", "tok")

    @pytest.mark.asyncio
    async def test_verify_credentials_deduplicates_instances_differing_by_trailing_slash(self):
        svc = JiraService(db=MagicMock())

        with (
            patch(
                "app.services.jiraService.get_configured_jira_urls_for_user",
                return_value=["https://jira.example.com", "https://jira.example.com/"],
            ),
            patch.object(
                JiraService, "_fetch_jira_account_email", AsyncMock(return_value=None)
            ) as mock_fetch,
        ):
            with pytest.raises(JiraCredentialsInvalidException):
                await svc._verify_credentials_for_user("user-1", "me@example.com", "tok")

        mock_fetch.assert_awaited_once_with("https://jira.example.com", "me@example.com", "tok")

    @pytest.mark.asyncio
    async def test_fetch_jira_account_email_returns_none_for_bad_credentials(self):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=MagicMock(status_code=401))

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService._fetch_jira_account_email(
                "https://jira.example.com", "me@example.com", "bad-tok"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_jira_account_email_returns_the_authenticated_account(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {"emailAddress": "someone.else@example.com"}
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=response)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService._fetch_jira_account_email(
                "https://jira.example.com", "me@example.com", "tok"
            )

        assert result == "someone.else@example.com"

    @pytest.mark.asyncio
    async def test_fetch_jira_account_email_returns_blank_when_jira_hides_the_email(self):
        """Account privacy settings can omit emailAddress; a successful auth is
        then the strongest signal available."""
        response = MagicMock(status_code=200)
        response.json.return_value = {"accountId": "abc123"}
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=response)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService._fetch_jira_account_email(
                "https://jira.example.com", "me@example.com", "tok"
            )

        assert result == ""

    @pytest.mark.asyncio
    async def test_fetch_jira_account_email_returns_blank_for_invalid_json(self):
        response = MagicMock(status_code=200)
        response.json.side_effect = ValueError("invalid JSON")
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=response)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService._fetch_jira_account_email(
                "https://jira.example.com", "me@example.com", "tok"
            )

        assert result == ""

    @pytest.mark.asyncio
    async def test_fetch_jira_account_email_returns_none_when_jira_unreachable(self):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(side_effect=httpx.ConnectError("down"))

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService._fetch_jira_account_email(
                "https://jira.example.com", "me@example.com", "tok"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_jira_account_email_returns_none_for_error_statuses(self):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(return_value=MagicMock(status_code=500))

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService._fetch_jira_account_email(
                "https://jira.example.com", "me@example.com", "tok"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_imported_stories_returns_summary_on_success(self):
        svc = JiraService(db=MagicMock())

        with (
            patch.object(
                JiraService,
                "fetch_jira_data",
                new=AsyncMock(return_value=[{"epicId": "EP-1"}]),
            ) as mock_fetch,
            patch(
                "app.services.jiraService.refresh_stories_from_jira",
                return_value={"changed_story_keys": ["US-1"], "new_story_keys": ["US-2"]},
            ) as mock_refresh,
        ):
            project_id = uuid.uuid4()
            result = await svc.refresh_imported_stories(
                "https://jira.example.com", "PROJ", "token", project_id
            )

        mock_fetch.assert_called_once_with(
            "https://jira.example.com", "PROJ", "token", statuses=None, db=svc.db, jira_email=""
        )
        mock_refresh.assert_called_once_with(svc.db, [{"epicId": "EP-1"}], project_id)
        assert result["success"] is True
        assert result["updated_count"] == 1
        assert result["new_story_keys"] == ["US-2"]

    @pytest.mark.asyncio
    async def test_refresh_imported_stories_rolls_back_and_raises_on_failure(self):
        svc = JiraService(db=MagicMock())

        with (
            patch.object(
                JiraService,
                "fetch_jira_data",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
            patch("app.services.jiraService.logger") as mock_logger,
        ):
            with pytest.raises(DatabaseOperationException, match="boom"):
                await svc.refresh_imported_stories(
                    "https://jira.example.com", "PROJ", "token", uuid.uuid4()
                )

        svc.db.rollback.assert_called_once()
        mock_logger.exception.assert_called_once_with("REFRESH FAILED")


@pytest.mark.asyncio
async def test_apply_refresh_updates_uses_refresh_changes_helper():
    svc = JiraService(db=MagicMock())

    with (
        patch.object(
            JiraService,
            "fetch_jira_data",
            new=AsyncMock(return_value=[{"epicId": "EP-1"}]),
        ) as mock_fetch,
        patch(
            "app.services.jiraService.apply_refresh_changes", return_value=["updated"]
        ) as mock_apply,
    ):
        project_id = uuid.uuid4()
        result = await svc.apply_refresh_updates(
            "https://jira.example.com", "PROJ", "token", project_id
        )

    mock_fetch.assert_called_once_with(
        "https://jira.example.com", "PROJ", "token", statuses=None, db=svc.db, jira_email=""
    )
    mock_apply.assert_called_once_with(svc.db, [{"epicId": "EP-1"}], project_id)
    assert result == {"success": True, "updated": ["updated"]}


class TestBuildTestCaseJql:

    def test_returns_jql_scoped_to_test_case_issue_type(self):
        jql = JiraService._build_test_case_jql("PROJ")
        assert jql == ('project = "PROJ" AND issuetype = 10012 ORDER BY created DESC')


class TestBuildTestCaseResponse:

    def test_maps_full_fields(self):
        issues = [
            {
                "key": "ADTD-101",
                "fields": {
                    "summary": "Login works",
                    "status": {"name": "To Do"},
                    "priority": {"name": "High"},
                    "components": [{"name": "Auth"}],
                    "labels": ["smoke"],
                },
            }
        ]
        result = JiraService.build_test_case_response(issues)
        assert result == [
            {
                "id": "ADTD-101",
                "name": "Login works",
                "suite": "smoke",
                "status": "To Do",
                "priority": "High",
                "module": "Auth",
            }
        ]

    def test_missing_optional_fields_default_sensibly(self):
        issues = [{"key": "ADTD-102", "fields": {}}]
        result = JiraService.build_test_case_response(issues)
        assert result == [
            {
                "id": "ADTD-102",
                "name": "No Summary",
                "suite": None,
                "status": "Unknown",
                "priority": None,
                "module": None,
            }
        ]

    def test_empty_issues_returns_empty_list(self):
        assert JiraService.build_test_case_response([]) == []


class TestFetchJiraTestCases:

    @pytest.mark.asyncio
    async def test_single_page_happy_path(self):
        responses = [
            _http_resp(
                {
                    "issues": [
                        {
                            "key": "ADTD-1",
                            "fields": {
                                "summary": "Checkout works",
                                "status": {"name": "Done"},
                                "priority": {"name": "Medium"},
                                "components": [],
                                "labels": [],
                            },
                        }
                    ],
                    "isLast": True,
                }
            )
        ]
        client = _make_paging_client(responses)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService.fetch_jira_test_cases(
                "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
            )

        assert result == [
            {
                "id": "ADTD-1",
                "name": "Checkout works",
                "suite": None,
                "status": "Done",
                "priority": "Medium",
                "module": None,
            }
        ]
        assert client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_paginates_via_next_page_token(self):
        page1 = _http_resp({"issues": [{"key": "ADTD-1", "fields": {}}], "nextPageToken": "p2"})
        page2 = _http_resp({"issues": [{"key": "ADTD-2", "fields": {}}], "isLast": True})
        client = _make_paging_client([page1, page2])

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService.fetch_jira_test_cases(
                "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
            )

        assert [tc["id"] for tc in result] == ["ADTD-1", "ADTD-2"]
        assert client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_401_raises_jira_auth_exception(self):
        responses = [_http_resp({}, status_code=401)]
        client = _make_paging_client(responses)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            with pytest.raises(JiraAuthException):
                await JiraService.fetch_jira_test_cases(
                    "https://jira.example.com", "PROJ", "bad-token", jira_email="me@example.com"
                )

    @pytest.mark.asyncio
    async def test_network_error_raises_jira_fetch_exception(self):
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            with pytest.raises(JiraFetchException):
                await JiraService.fetch_jira_test_cases(
                    "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
                )

    @pytest.mark.asyncio
    async def test_no_test_cases_returns_empty_list(self):
        """No JIRA_TEST_CASE_ISSUE_TYPE_ID issues for the project is a valid,
        non-error result — the endpoint layer decides what an empty list means."""
        responses = [_http_resp({"issues": [], "isLast": True})]
        client = _make_paging_client(responses)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            result = await JiraService.fetch_jira_test_cases(
                "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_exceeds_page_cap_logs_truncation_warning(self):
        """Jira never returns isLast/no-next-token within MAX_TEST_CASE_PAGES —
        covers the for/else truncation-warning branch added for the
        unbounded-pagination fix."""
        responses = [
            _http_resp(
                {"issues": [{"key": f"ADTD-{i}", "fields": {}}], "nextPageToken": f"page-{i}"}
            )
            for i in range(JiraService.MAX_TEST_CASE_PAGES)
        ]
        client = _make_paging_client(responses)

        with patch("app.services.jiraService.httpx.AsyncClient", return_value=client):
            with patch("app.services.jiraService.logger") as mock_logger:
                result = await JiraService.fetch_jira_test_cases(
                    "https://jira.example.com", "PROJ", "token", jira_email="me@example.com"
                )

        assert client.get.call_count == JiraService.MAX_TEST_CASE_PAGES
        assert len(result) == JiraService.MAX_TEST_CASE_PAGES
        mock_logger.warning.assert_called_once_with(
            "jira_test_case_fetch_truncated", extra={"project_key": "PROJ"}
        )

    def test_story_parent_from_epic_dict(self):
        issues = [
            _epic("EP-1"),
            {
                "key": "US-1",
                "fields": {
                    "issuetype": {"name": "Story"},
                    "summary": "Summary",
                    "epic": {"key": "EP-1"},
                },
            },
        ]
        result = JiraService.build_fetch_response(issues)
        assert result[0]["epicId"] == "EP-1"
        assert result[0]["user_stories"][0]["storyId"] == "US-1"

    def test_story_parent_from_epic_string(self):
        issues = [
            _epic("EP-1"),
            {
                "key": "US-1",
                "fields": {
                    "issuetype": {"name": "Story"},
                    "summary": "Summary",
                    "epic": "EP-1",
                },
            },
        ]
        result = JiraService.build_fetch_response(issues)
        assert result[0]["epicId"] == "EP-1"
        assert result[0]["user_stories"][0]["storyId"] == "US-1"

    def test_story_parent_from_customfield_string(self):
        issues = [
            _epic("EP-1"),
            {
                "key": "US-1",
                "fields": {
                    "issuetype": {"name": "Story"},
                    "summary": "Summary",
                    "customfield_10014": "EP-1",
                },
            },
        ]
        result = JiraService.build_fetch_response(issues)
        assert result[0]["epicId"] == "EP-1"
        assert result[0]["user_stories"][0]["storyId"] == "US-1"

    def test_story_parent_from_customfield_string_non_matching(self):
        issues = [
            {
                "key": "US-1",
                "fields": {
                    "issuetype": {"name": "Story"},
                    "summary": "Summary",
                    "customfield_10014": "not-a-valid-issue-key",
                },
            },
        ]
        result = JiraService.build_fetch_response(issues)
        assert result[0]["epicId"] == "UNGROUPED"

    def test_story_parent_from_customfield_dict(self):
        issues = [
            _epic("EP-1"),
            {
                "key": "US-1",
                "fields": {
                    "issuetype": {"name": "Story"},
                    "summary": "Summary",
                    "customfield_10014": {"key": "EP-1"},
                },
            },
        ]
        result = JiraService.build_fetch_response(issues)
        assert result[0]["epicId"] == "EP-1"
        assert result[0]["user_stories"][0]["storyId"] == "US-1"

    @pytest.mark.asyncio
    async def test_apply_refresh_updates_with_and_without_project_id(self):
        service = JiraService(db=MagicMock())
        with patch.object(JiraService, "fetch_jira_data", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []
            with patch(
                "app.services.jiraService.apply_refresh_changes", return_value=["US-1"]
            ) as mock_apply:
                # With project_id
                res1 = await service.apply_refresh_updates(
                    "https://jira.com", "PROJ", "tok", project_id=uuid.uuid4()
                )
                assert res1 == {"success": True, "updated": ["US-1"]}
                assert mock_apply.call_count == 1

                # Without project_id
                res2 = await service.apply_refresh_updates(
                    "https://jira.com", "PROJ", "tok", project_id=None
                )
                assert res2 == {"success": True, "updated": ["US-1"]}
                assert mock_apply.call_count == 2

    @pytest.mark.asyncio
    async def test_apply_refresh_updates_direct_with_and_without_project_id(self):
        service = JiraService(db=MagicMock())
        with patch(
            "app.services.jiraService.apply_refresh_changes", return_value=["US-1"]
        ) as mock_apply:
            res1 = await service.apply_refresh_updates_direct([], project_id=uuid.uuid4())
            assert res1 == {"success": True, "updated": ["US-1"]}

            res2 = await service.apply_refresh_updates_direct([], project_id=None)
            assert res2 == {"success": True, "updated": ["US-1"]}
            assert mock_apply.call_count == 2

    @pytest.mark.asyncio
    async def test_apply_refresh_updates_direct_exception_rolls_back_and_raises(self):
        db = MagicMock()
        service = JiraService(db=db)
        with patch(
            "app.services.jiraService.apply_refresh_changes",
            side_effect=RuntimeError("direct apply fail"),
        ):
            with pytest.raises(DatabaseOperationException, match="direct apply fail"):
                await service.apply_refresh_updates_direct([], project_id=uuid.uuid4())
        db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_refresh_updates_exception_rolls_back_and_raises(self):
        db = MagicMock()
        service = JiraService(db=db)
        with patch.object(JiraService, "fetch_jira_data", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []
            with patch(
                "app.services.jiraService.apply_refresh_changes",
                side_effect=RuntimeError("apply fail"),
            ):
                with pytest.raises(DatabaseOperationException, match="apply fail"):
                    await service.apply_refresh_updates(
                        "https://jira.com", "PROJ", "tok", project_id=uuid.uuid4()
                    )
        db.rollback.assert_called_once()
