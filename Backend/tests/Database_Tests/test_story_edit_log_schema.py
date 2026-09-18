"""Schema validation tests for StoryEditLogRequest and related models."""

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.user_stories import (
    StoryChangeSchema,
    StoryEditLogRequest,
    StoryEditLogResponse,
)

PROJECT_ID = uuid.uuid4()

VALID_PAYLOAD = {
    "project_id": PROJECT_ID,
    "edit_log": [
        {
            "storyId": "STORY-1",
            "epicId": "EPIC-1",
            "editedAt": "2026-06-23T10:30:00.000Z",
            "changes": [
                {"field": "storyTitle", "before": "Old title", "after": "New title"},
                {"field": "description", "before": "Old desc", "after": "New desc"},
            ],
        }
    ],
}


def test_valid_payload_parses():
    req = StoryEditLogRequest(**VALID_PAYLOAD)
    assert len(req.edit_log) == 1
    record = req.edit_log[0]
    assert record.storyId == "STORY-1"
    assert record.epicId == "EPIC-1"
    assert len(record.changes) == 2


def test_edited_at_parsed_as_datetime():
    req = StoryEditLogRequest(**VALID_PAYLOAD)
    assert isinstance(req.edit_log[0].editedAt, datetime)


def test_project_id_parsed_as_uuid():
    req = StoryEditLogRequest(**VALID_PAYLOAD)
    assert req.project_id == PROJECT_ID


def test_missing_project_id_raises():
    payload_without_project_id = {"edit_log": VALID_PAYLOAD["edit_log"]}
    with pytest.raises(ValidationError) as exc:
        StoryEditLogRequest(**payload_without_project_id)
    assert "project_id" in str(exc.value)


def test_invalid_project_id_raises():
    with pytest.raises(ValidationError):
        StoryEditLogRequest(project_id="not-a-uuid", edit_log=VALID_PAYLOAD["edit_log"])


def test_empty_edit_log_is_rejected():
    with pytest.raises(ValidationError):
        StoryEditLogRequest(project_id=PROJECT_ID, edit_log=[])


def test_empty_changes_list_is_rejected():
    with pytest.raises(ValidationError):
        StoryEditLogRequest(
            project_id=PROJECT_ID,
            edit_log=[
                {
                    "storyId": "STORY-1",
                    "epicId": "EPIC-1",
                    "editedAt": "2026-06-23T10:30:00Z",
                    "changes": [],
                }
            ],
        )


_ONE_CHANGE = [{"field": "storyTitle", "before": "Old", "after": "New"}]


def test_missing_story_id_raises():
    with pytest.raises(ValidationError) as exc:
        StoryEditLogRequest(
            edit_log=[
                {
                    "epicId": "EPIC-1",
                    "editedAt": "2026-06-23T10:30:00Z",
                    "changes": _ONE_CHANGE,
                }
            ]
        )
    assert "storyId" in str(exc.value)


def test_missing_epic_id_raises():
    with pytest.raises(ValidationError) as exc:
        StoryEditLogRequest(
            project_id=PROJECT_ID,
            edit_log=[
                {
                    "storyId": "STORY-1",
                    "editedAt": "2026-06-23T10:30:00Z",
                    "changes": _ONE_CHANGE,
                }
            ],
        )
    assert "epicId" in str(exc.value)


def test_missing_edited_at_raises():
    with pytest.raises(ValidationError):
        StoryEditLogRequest(
            project_id=PROJECT_ID,
            edit_log=[
                {
                    "storyId": "STORY-1",
                    "epicId": "EPIC-1",
                    "changes": _ONE_CHANGE,
                }
            ],
        )


def test_invalid_edited_at_format_raises():
    with pytest.raises(ValidationError):
        StoryEditLogRequest(
            project_id=PROJECT_ID,
            edit_log=[
                {
                    "storyId": "STORY-1",
                    "epicId": "EPIC-1",
                    "editedAt": "not-a-date",
                    "changes": _ONE_CHANGE,
                }
            ],
        )


def test_story_change_schema_fields():
    change = StoryChangeSchema(field="storyTitle", before="A", after="B")
    assert change.field == "storyTitle"
    assert change.before == "A"
    assert change.after == "B"


def test_story_change_empty_strings_allowed():
    change = StoryChangeSchema(field="description", before="", after="New value")
    assert change.before == ""


def test_story_change_empty_before_defaults():
    change = StoryChangeSchema(field="storyTitle", after="New title")
    assert change.before == ""


def test_story_change_empty_after_defaults():
    change = StoryChangeSchema(field="description", before="Old desc")
    assert change.after == ""


def test_story_change_invalid_field_raises():
    with pytest.raises(ValidationError):
        StoryChangeSchema(field="assignee", before="x", after="y")


def test_story_edit_log_response():
    resp = StoryEditLogResponse(saved=3)
    assert resp.saved == 3


def test_multiple_records_parse():
    req = StoryEditLogRequest(
        project_id=PROJECT_ID,
        edit_log=[
            {
                "storyId": f"STORY-{i}",
                "epicId": "EPIC-1",
                "editedAt": "2026-06-23T10:30:00Z",
                "changes": [{"field": "storyTitle", "before": "old", "after": "new"}],
            }
            for i in range(5)
        ],
    )
    assert len(req.edit_log) == 5
    assert req.edit_log[4].storyId == "STORY-4"
