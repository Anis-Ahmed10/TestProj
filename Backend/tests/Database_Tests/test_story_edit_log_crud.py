"""CRUD tests for bulk_insert_edit_log."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.database.crud_story_edit_log import bulk_insert_edit_log

EDITED_AT = datetime(2026, 6, 23, 10, 30, 0, tzinfo=timezone.utc)

RECORDS = [
    {
        "storyId": "STORY-1",
        "epicId": "EPIC-1",
        "changes": [{"field": "storyTitle", "before": "Old", "after": "New"}],
        "editedAt": EDITED_AT,
    },
    {
        "storyId": "STORY-2",
        "epicId": "EPIC-1",
        "changes": [{"field": "description", "before": "Old desc", "after": "New desc"}],
        "editedAt": EDITED_AT,
    },
]


@pytest.fixture
def mock_db():
    return MagicMock()


def test_returns_count_of_inserted_records(mock_db):
    result = bulk_insert_edit_log(mock_db, RECORDS)
    assert result == 2


def test_calls_add_all_with_correct_count(mock_db):
    bulk_insert_edit_log(mock_db, RECORDS)
    mock_db.add_all.assert_called_once()
    rows = mock_db.add_all.call_args[0][0]
    assert len(rows) == 2


def test_orm_rows_have_correct_story_ids(mock_db):
    bulk_insert_edit_log(mock_db, RECORDS)
    rows = mock_db.add_all.call_args[0][0]
    assert rows[0].story_id == "STORY-1"
    assert rows[1].story_id == "STORY-2"


def test_orm_rows_have_correct_epic_id(mock_db):
    bulk_insert_edit_log(mock_db, RECORDS)
    rows = mock_db.add_all.call_args[0][0]
    assert rows[0].epic_id == "EPIC-1"


def test_orm_rows_have_correct_changes(mock_db):
    bulk_insert_edit_log(mock_db, RECORDS)
    rows = mock_db.add_all.call_args[0][0]
    assert rows[0].changes == [{"field": "storyTitle", "before": "Old", "after": "New"}]


def test_orm_rows_have_correct_edited_at(mock_db):
    bulk_insert_edit_log(mock_db, RECORDS)
    rows = mock_db.add_all.call_args[0][0]
    assert rows[0].edited_at == EDITED_AT


def test_commit_called_after_add_all(mock_db):
    bulk_insert_edit_log(mock_db, RECORDS)
    mock_db.add_all.assert_called_once()
    mock_db.commit.assert_called_once()


def test_empty_records_returns_zero_without_hitting_db(mock_db):
    result = bulk_insert_edit_log(mock_db, [])
    assert result == 0
    mock_db.add_all.assert_not_called()
    mock_db.commit.assert_not_called()


def test_db_error_triggers_rollback(mock_db):
    mock_db.commit.side_effect = Exception("DB connection lost")

    with pytest.raises(Exception, match="DB connection lost"):
        bulk_insert_edit_log(mock_db, RECORDS)

    mock_db.rollback.assert_called_once()


def test_db_error_does_not_swallow_exception(mock_db):
    mock_db.add_all.side_effect = RuntimeError("unexpected")

    with pytest.raises(RuntimeError):
        bulk_insert_edit_log(mock_db, RECORDS)

    mock_db.rollback.assert_called_once()


def test_single_record_inserts_correctly(mock_db):
    single = [RECORDS[0]]
    result = bulk_insert_edit_log(mock_db, single)
    assert result == 1
    rows = mock_db.add_all.call_args[0][0]
    assert len(rows) == 1
