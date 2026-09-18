import asyncio
import logging
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pydantic
import pytest

from app.api import dependencies as deps
from app.api.v1.endpoints import database_operations
from app.components.authorizer import Permission
from app.core.exceptions import AppException
from app.schemas.user_stories import (
    ImportStoriesRequest,
    StoryEditLogRequest,
    StoryStatusLookupRequest,
)


def _make_request_model(project_id="proj-1", user_story_id="US-1"):
    from app.schemas.JiraSchemas import RequestModel

    return RequestModel(
        userStoryId=user_story_id,
        projectId=project_id,
        format="standard",
        test_cases=[],
    )


def test_save_stories_success():
    db = MagicMock()
    current_user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    payload = ImportStoriesRequest(
        selected_epics=[{"epicId": "EPIC-1", "user_stories": []}],
        project_id=project_id,
    )

    with patch.object(
        database_operations.DatabaseService,
        "save_selected_stories",
        return_value={"imported": 1},
    ) as mock_save:
        result = asyncio.run(database_operations.save_stories(payload, db, current_user_id))
        assert result == {"imported": 1}
        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["db"] is db
        assert call_kwargs["selected_epics"][0].epicId == "EPIC-1"
        assert call_kwargs["project_id"] == project_id


def test_save_stories_success_logs_project_id():
    db = MagicMock()
    current_user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    payload = ImportStoriesRequest(
        selected_epics=[{"epicId": "EPIC-1", "user_stories": []}],
        project_id=project_id,
    )

    with (
        patch.object(
            database_operations.DatabaseService,
            "save_selected_stories",
            return_value={"imported": 1},
        ),
        patch("app.utils.audit_log.create_log_entry") as mock_log,
    ):
        asyncio.run(database_operations.save_stories(payload, db, current_user_id))

    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["project_id"] == project_id


def test_save_stories_raises_and_converts_to_http_exception(caplog):
    db = MagicMock()
    current_user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    payload = ImportStoriesRequest(
        selected_epics=[{"epicId": "EPIC-2", "user_stories": []}],
        project_id=project_id,
    )

    def raise_exc(db, selected_epics, project_id):
        raise Exception("boom")

    with patch.object(
        database_operations.DatabaseService,
        "save_selected_stories",
        side_effect=raise_exc,
    ):
        caplog.set_level(logging.ERROR)
        with pytest.raises(AppException) as excinfo:
            asyncio.run(database_operations.save_stories(payload, db, current_user_id))

    assert excinfo.value.status_code == 500
    assert excinfo.value.code == "STORIES_SAVE_FAILED"
    assert excinfo.value.message == "Failed to save stories"


def test_save_stories_app_exception_is_propagated():
    """An AppException raised by the service is re-raised unchanged by the
    audit_log decorator, preserving its code/message/status for the global
    AppException handler to render."""
    db = MagicMock()
    current_user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    payload = ImportStoriesRequest(
        selected_epics=[{"epicId": "EPIC-3", "user_stories": []}],
        project_id=project_id,
    )
    app_exc = AppException(code="DUPLICATE", message="Story already exists", status_code=409)

    with patch.object(
        database_operations.DatabaseService,
        "save_selected_stories",
        side_effect=app_exc,
    ):
        with pytest.raises(AppException) as excinfo:
            asyncio.run(database_operations.save_stories(payload, db, current_user_id))

    assert excinfo.value.status_code == 409
    assert excinfo.value.code == "DUPLICATE"
    assert excinfo.value.message == "Story already exists"


def test_save_stories_log_entry_failure_is_swallowed(caplog):
    """If create_log_entry itself raises in the finally block, it's caught
    and logged, not propagated."""
    db = MagicMock()
    current_user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    payload = ImportStoriesRequest(
        selected_epics=[{"epicId": "EPIC-4", "user_stories": []}],
        project_id=project_id,
    )

    with (
        patch.object(
            database_operations.DatabaseService,
            "save_selected_stories",
            return_value={"imported": 1},
        ),
        patch(
            "app.utils.audit_log.create_log_entry",
            side_effect=Exception("log db down"),
        ),
    ):
        caplog.set_level(logging.WARNING)
        result = asyncio.run(database_operations.save_stories(payload, db, current_user_id))

    assert result == {"imported": 1}
    assert "application_log_entry_failed" in caplog.text
    assert any(getattr(rec, "handler", None) == "save_stories" for rec in caplog.records)


def test_save_test_cases_exception_converts_to_http_exception(caplog):
    """A failure inside DatabaseService.save_test_cases becomes a 500 AppException."""
    db = MagicMock()
    current_user_id = uuid.uuid4()
    request = _make_request_model()

    async def raise_exc(request, db):
        raise Exception("save failed")

    with patch.object(
        database_operations.DatabaseService,
        "save_test_cases",
        side_effect=raise_exc,
    ):
        caplog.set_level(logging.ERROR)
        with pytest.raises(AppException) as excinfo:
            asyncio.run(database_operations.save_test_cases(request, db, current_user_id))

    assert excinfo.value.status_code == 500
    assert excinfo.value.code == "TESTCASE_SAVE_FAILED"
    assert excinfo.value.message == "Failed to save test cases"


def test_save_test_cases_failure_logs_status_500_not_200(caplog):
    """Regression test: a failed save must be recorded in Pipeline Run
    History with status_code=500, not the stale default of 200.
    (status_code is now reassigned in the except branch before create_log_entry
    is called in `finally`.)"""
    db = MagicMock()
    current_user_id = uuid.uuid4()
    request = _make_request_model()

    async def raise_exc(request, db):
        raise Exception("save failed")

    with (
        patch.object(
            database_operations.DatabaseService,
            "save_test_cases",
            side_effect=raise_exc,
        ),
        patch("app.utils.audit_log.create_log_entry") as mock_log,
    ):
        caplog.set_level(logging.ERROR)
        with pytest.raises(AppException):
            asyncio.run(database_operations.save_test_cases(request, db, current_user_id))

    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["status_code"] == 500


def test_save_test_cases_log_entry_failure_is_swallowed(caplog):
    """If create_log_entry raises in the finally block for save_test_cases,
    it's caught, not propagated."""
    db = MagicMock()
    current_user_id = uuid.uuid4()
    request = _make_request_model()

    async def fake_save_test_cases(request, db):
        return {"saved_count": 0, "saved_test_cases": [], "skipped": [], "failed": []}

    with (
        patch.object(
            database_operations.DatabaseService,
            "save_test_cases",
            side_effect=fake_save_test_cases,
        ),
        patch(
            "app.utils.audit_log.create_log_entry",
            side_effect=Exception("log db down"),
        ),
    ):
        caplog.set_level(logging.WARNING)
        result = asyncio.run(database_operations.save_test_cases(request, db, current_user_id))

    assert result["saved_count"] == 0
    assert "application_log_entry_failed" in caplog.text
    assert any(getattr(rec, "handler", None) == "save_test_cases" for rec in caplog.records)


def test_save_test_cases_success_logs_project_id():
    db = MagicMock()
    current_user_id = uuid.uuid4()
    request = _make_request_model(project_id="proj-42")

    async def fake_save_test_cases(request, db):
        return {"saved_count": 0, "saved_test_cases": [], "skipped": [], "failed": []}

    with (
        patch.object(
            database_operations.DatabaseService,
            "save_test_cases",
            side_effect=fake_save_test_cases,
        ),
        patch("app.utils.audit_log.create_log_entry") as mock_log,
    ):
        asyncio.run(database_operations.save_test_cases(request, db, current_user_id))

    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["project_id"] == "proj-42"


# ── save_story_edit_log ──────────────────────────────────────────────────────


def _make_edit_log_payload(project_id=None):
    return StoryEditLogRequest(
        project_id=project_id or uuid.uuid4(),
        edit_log=[
            {
                "storyId": "US-1",
                "epicId": "EP-1",
                "changes": [{"field": "storyTitle", "before": "Old", "after": "New"}],
                "editedAt": datetime(2024, 1, 1, tzinfo=timezone.utc),
            }
        ],
    )


def test_save_story_edit_log_success():
    db = MagicMock()
    payload = _make_edit_log_payload()

    with patch.object(
        database_operations.DatabaseService,
        "save_story_edit_log",
        return_value=1,
    ) as mock_save:
        result = asyncio.run(database_operations.save_story_edit_log(payload, db))

    mock_save.assert_called_once_with(db=db, edit_log=payload.edit_log)
    assert result.saved == 1


def test_save_story_edit_log_exception_converts_to_http_exception(caplog):
    db = MagicMock()
    payload = _make_edit_log_payload()

    with patch.object(
        database_operations.DatabaseService,
        "save_story_edit_log",
        side_effect=Exception("db error"),
    ):
        caplog.set_level(logging.ERROR)
        with pytest.raises(AppException) as excinfo:
            asyncio.run(database_operations.save_story_edit_log(payload, db))

    assert excinfo.value.status_code == 500
    assert excinfo.value.code == "STORY_EDIT_LOG_SAVE_FAILED"
    assert excinfo.value.message == "Failed to save story edit log"


# ── require_project_permission_from_story_edit_log_payload ──────────────────


def test_story_edit_log_dependency_allows_member(monkeypatch):
    from app.api import dependencies as deps
    from app.components.authorizer import Permission

    project_id = uuid.uuid4()
    payload = _make_edit_log_payload(project_id=project_id)
    current_user = MagicMock(id=uuid.uuid4(), role="Test Engineer")
    authorizer = MagicMock()
    authorizer.has_permission.return_value = True
    db = MagicMock()

    monkeypatch.setattr(deps, "get_visible_project_ids", lambda db, uid: {project_id})

    dependency = deps.require_project_permission_from_story_edit_log_payload(
        Permission.STORY_EDIT_LOG
    )
    result = dependency(payload=payload, current_user=current_user, authorizer=authorizer, db=db)

    assert result is payload


def test_story_edit_log_dependency_rejects_non_member(monkeypatch):
    project_id = uuid.uuid4()
    other_project_id = uuid.uuid4()
    payload = _make_edit_log_payload(project_id=project_id)
    current_user = MagicMock(id=uuid.uuid4(), role="Test Engineer")
    authorizer = MagicMock()
    authorizer.has_permission.return_value = True
    db = MagicMock()

    monkeypatch.setattr(deps, "get_visible_project_ids", lambda db, uid: {other_project_id})

    dependency = deps.require_project_permission_from_story_edit_log_payload(
        Permission.STORY_EDIT_LOG
    )

    with pytest.raises(AppException) as excinfo:
        dependency(payload=payload, current_user=current_user, authorizer=authorizer, db=db)

    assert excinfo.value.status_code == 403


def test_story_edit_log_dependency_rejects_missing_project_id():
    with pytest.raises(pydantic.ValidationError):
        StoryEditLogRequest(
            edit_log=[
                {
                    "storyId": "US-1",
                    "epicId": "EP-1",
                    "changes": [{"field": "storyTitle", "before": "Old", "after": "New"}],
                    "editedAt": "2024-01-01T00:00:00Z",
                }
            ]
        )


# ── get_story_statuses ───────────────────────────────────────────────────────


def _make_status_lookup_payload(project_id):
    return StoryStatusLookupRequest(project_id=project_id, story_keys=["US-1"])


def test_get_story_statuses_success_logs_project_id():
    db = MagicMock()
    current_user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    payload = _make_status_lookup_payload(project_id)

    with (
        patch.object(
            database_operations.DatabaseService,
            "get_story_statuses",
            return_value={"US-1": {"already_exists": True, "status": "approved"}},
        ),
        patch("app.utils.audit_log.create_log_entry") as mock_log,
    ):
        result = asyncio.run(database_operations.get_story_statuses(payload, db, current_user_id))

    assert result.statuses["US-1"].status == "approved"
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["status_code"] == 200
    assert mock_log.call_args.kwargs["project_id"] == project_id


def test_get_story_statuses_exception_converts_to_app_exception(caplog):
    db = MagicMock()
    current_user_id = uuid.uuid4()
    payload = _make_status_lookup_payload(uuid.uuid4())

    with (
        patch.object(
            database_operations.DatabaseService,
            "get_story_statuses",
            side_effect=Exception("db error"),
        ),
        patch("app.utils.audit_log.create_log_entry") as mock_log,
    ):
        caplog.set_level(logging.ERROR)
        with pytest.raises(AppException) as excinfo:
            asyncio.run(database_operations.get_story_statuses(payload, db, current_user_id))

    assert excinfo.value.code == "STORY_STATUS_LOOKUP_FAILED"
    assert excinfo.value.status_code == 500
    assert mock_log.call_args.kwargs["status_code"] == 500
