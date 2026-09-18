"""Service layer tests for DatabaseService.save_story_edit_log."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.user_stories import (
    StoryChangeSchema,
    StoryEditRecordSchema,
)
from app.services.databaseService import DatabaseService

EDITED_AT = datetime(2026, 6, 23, 10, 30, 0, tzinfo=timezone.utc)


def _make_record(story_id: str, epic_id: str, changes: list) -> StoryEditRecordSchema:
    return StoryEditRecordSchema(
        storyId=story_id,
        epicId=epic_id,
        editedAt=EDITED_AT,
        changes=[StoryChangeSchema(**c) for c in changes],
    )


@pytest.fixture
def mock_db():
    return MagicMock()


@patch("app.services.databaseService.bulk_insert_edit_log")
def test_delegates_to_crud(mock_crud, mock_db):
    mock_crud.return_value = 1
    records = [
        _make_record("STORY-1", "EPIC-1", [{"field": "storyTitle", "before": "A", "after": "B"}])
    ]

    result = DatabaseService.save_story_edit_log(mock_db, records)

    mock_crud.assert_called_once()
    assert result == 1


@patch("app.services.databaseService.bulk_insert_edit_log")
def test_converts_pydantic_to_dicts(mock_crud, mock_db):
    mock_crud.return_value = 1
    records = [
        _make_record("STORY-1", "EPIC-1", [{"field": "storyTitle", "before": "A", "after": "B"}])
    ]

    DatabaseService.save_story_edit_log(mock_db, records)

    _, kwargs = mock_crud.call_args
    passed_records = kwargs["records"]
    assert isinstance(passed_records[0], dict)
    assert passed_records[0]["storyId"] == "STORY-1"
    assert passed_records[0]["epicId"] == "EPIC-1"
    assert passed_records[0]["editedAt"] == EDITED_AT


@patch("app.services.databaseService.bulk_insert_edit_log")
def test_changes_serialised_to_dicts(mock_crud, mock_db):
    mock_crud.return_value = 1
    records = [
        _make_record(
            "STORY-1",
            "EPIC-1",
            [
                {"field": "storyTitle", "before": "Old", "after": "New"},
                {"field": "description", "before": "Desc A", "after": "Desc B"},
            ],
        )
    ]

    DatabaseService.save_story_edit_log(mock_db, records)

    passed_records = mock_crud.call_args.kwargs["records"]
    changes = passed_records[0]["changes"]
    assert isinstance(changes[0], dict)
    assert changes[0] == {"field": "storyTitle", "before": "Old", "after": "New"}
    assert changes[1] == {"field": "description", "before": "Desc A", "after": "Desc B"}


@patch("app.services.databaseService.bulk_insert_edit_log")
def test_passes_db_session_to_crud(mock_crud, mock_db):
    mock_crud.return_value = 0
    DatabaseService.save_story_edit_log(mock_db, [])
    mock_crud.assert_called_once_with(db=mock_db, records=[])


@patch("app.services.databaseService.bulk_insert_edit_log")
def test_empty_edit_log_passes_empty_list_to_crud(mock_crud, mock_db):
    mock_crud.return_value = 0
    result = DatabaseService.save_story_edit_log(mock_db, [])
    assert result == 0
    mock_crud.assert_called_once_with(db=mock_db, records=[])


@patch("app.services.databaseService.bulk_insert_edit_log")
def test_multiple_records_all_converted(mock_crud, mock_db):
    mock_crud.return_value = 3
    records = [
        _make_record(
            f"STORY-{i}", "EPIC-1", [{"field": "storyTitle", "before": "x", "after": "y"}]
        )
        for i in range(3)
    ]

    result = DatabaseService.save_story_edit_log(mock_db, records)

    passed_records = mock_crud.call_args.kwargs["records"]
    assert len(passed_records) == 3
    assert result == 3


@patch("app.services.databaseService.bulk_insert_edit_log")
def test_crud_exception_propagates(mock_crud, mock_db):
    mock_crud.side_effect = RuntimeError("DB failure")
    records = [
        _make_record("STORY-1", "EPIC-1", [{"field": "storyTitle", "before": "x", "after": "y"}])
    ]

    with pytest.raises(RuntimeError, match="DB failure"):
        DatabaseService.save_story_edit_log(mock_db, records)
