"""Shared internal validation helpers for business services."""

from typing import Any, TypeVar

from pydantic import BaseModel

from app.constants import FORMAT_BDD, FORMAT_EXPLORATORY, FORMAT_STANDARD
from app.utils.signatures import build_row_signature, build_test_case_signature, normalize_text

ModelT = TypeVar("ModelT", bound=BaseModel)

__all__ = [
    "normalize_text",
    "build_test_case_signature",
    "build_row_signature",
    "build_description",
]


def build_description(
    test_case,
    format_type,
):
    """Build Jira-compatible description payload."""

    if format_type == FORMAT_STANDARD:

        text = f"""Steps:
{test_case.get("steps") or "-"}

Expected Result:
{test_case.get("expected") or "-"}"""

    elif format_type == FORMAT_BDD:

        scenario = test_case.get("scenario") or {}

        text = f"""Given:
{scenario.get("given") or "-"}

When:
{scenario.get("when") or "-"}

Then:
{scenario.get("then") or "-"}"""

    elif format_type == FORMAT_EXPLORATORY:

        text = f"""Mission:
{test_case.get("charter_mission") or "-"}

Focus:
{test_case.get("charter_focus") or "-"}

Scope:
{test_case.get("charter_scope") or "-"}

Techniques:
{test_case.get("techniques") or "-"}"""

    else:
        text = "No description"

    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": text,
                    }
                ],
            }
        ],
    }


def _build_project_index(
    projects: list[Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return (ordered payloads list, project_id → payload lookup)."""
    payloads: list[dict[str, Any]] = []
    lookup: dict[str, dict[str, Any]] = {}
    for project in projects:
        project_id = str(project.id)
        entry: dict[str, Any] = {
            "project_id": project_id,
            "project_name": project.name,
            "epics": [],
        }
        payloads.append(entry)
        lookup[project_id] = entry
    return payloads, lookup


def _attach_epics(
    epics: list[Any],
    project_lookup: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Nest each epic under its project; return epic_key → epic payload lookup."""
    lookup: dict[str, dict[str, Any]] = {}
    for epic in epics:
        project_entry = project_lookup.get(str(epic.project_id))
        if not project_entry:
            continue
        epic_entry: dict[str, Any] = {
            "epic_id": str(epic.id),
            "epic_key": epic.epic_key,
            "epic_title": epic.title,
            "user_stories": [],
        }
        project_entry["epics"].append(epic_entry)
        lookup[str(epic.epic_key)] = epic_entry
    return lookup


def _attach_stories(
    user_stories: list[Any],
    epic_lookup: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Nest each user story under its epic; return story_key → story payload lookup."""
    lookup: dict[str, dict[str, Any]] = {}
    for story in user_stories:
        epic_entry = epic_lookup.get(str(story.epic_id))
        if not epic_entry:
            continue
        story_key = str(story.story_key)
        story_entry: dict[str, Any] = {
            "id": str(story.id),
            "story_key": story_key,
            "title": story.title,
            "description": story.description,
            "acceptance_criteria": story.acceptance_criteria,
            "priority": story.priority,
            "story_edit_logs": [],
            "test_cases": [],
        }
        epic_entry["user_stories"].append(story_entry)
        lookup[story_key] = story_entry
    return lookup


def _index_edit_logs(
    story_edit_logs: list[Any],
) -> dict[str, list[dict[str, Any]]]:
    """Group edit-log entries by story_id key."""
    index: dict[str, list[dict[str, Any]]] = {}
    for edit_log in story_edit_logs:
        story_id = edit_log.story_id
        if not story_id:
            continue
        story_key = str(story_id)
        index.setdefault(story_key, []).append(
            {
                "changes": edit_log.changes or {},
                "edited_at": edit_log.edited_at,
            }
        )
    return index


def _attach_test_cases_and_logs(
    test_cases: list[Any],
    story_lookup: dict[str, dict[str, Any]],
    logs_by_story: dict[str, list[dict[str, Any]]],
) -> None:
    """Attach test cases to their stories and populate story_edit_logs in place."""
    for test_case in test_cases:
        story_key = str(test_case.user_story_id)
        story_entry = story_lookup.get(story_key)
        if not story_entry:
            continue
        story_entry["test_cases"].append(
            {
                "id": str(test_case.id),
                "title": test_case.title,
                "test_format_type": test_case.test_format_type,
                "test_data": test_case.test_data,
                "jira_key": test_case.jira_key,
                "status": test_case.status,
                "created_at": test_case.created_at,
            }
        )

    for story_key, story_entry in story_lookup.items():
        story_entry["story_edit_logs"] = logs_by_story.get(story_key, [])
