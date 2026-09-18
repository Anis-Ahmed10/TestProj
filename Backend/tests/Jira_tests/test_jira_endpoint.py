import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.database_operations import save_stories
from app.api.v1.endpoints.jira import apply_refresh_changes_endpoint, push_to_jira, refresh_stories

_DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_DUMMY_PROJECT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class DummyPayload:
    selected_epics = []
    project_id = _DUMMY_PROJECT_ID


class DummyRequest:
    test_cases = []
    projectId = str(_DUMMY_PROJECT_ID)
    userStoryId = "US-1"
    format = "standard"


@pytest.mark.asyncio
async def test_save_stories_route(monkeypatch):
    class DummyPayload:
        selected_epics = []
        project_id = _DUMMY_PROJECT_ID

    def fake_save(**kwargs):
        return {"success": True}

    monkeypatch.setattr(
        "app.api.v1.endpoints.database_operations.DatabaseService.save_selected_stories",
        fake_save,
    )

    result = await save_stories(
        payload=DummyPayload(),
        db=None,
        current_user_id=_DUMMY_USER_ID,
    )

    assert result == {"success": True}


@pytest.mark.asyncio
async def test_refresh_stories_route(monkeypatch):
    svc = AsyncMock()
    svc.db = MagicMock()
    svc.get_project_jira_credentials = MagicMock(
        return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
    )
    svc.refresh_imported_stories.return_value = {"success": True}

    result = await refresh_stories(
        project_id=_DUMMY_PROJECT_ID,
        service=svc,
        current_user_id=_DUMMY_USER_ID,
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_apply_refresh_changes_route(monkeypatch):
    svc = AsyncMock()
    svc.db = MagicMock()
    svc.get_project_jira_credentials = MagicMock(
        return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
    )
    svc.apply_refresh_updates.return_value = {"success": True}

    result = await apply_refresh_changes_endpoint(
        project_id=_DUMMY_PROJECT_ID,
        service=svc,
        current_user_id=_DUMMY_USER_ID,
    )

    assert result["success"] is True


class DummyService:
    db = MagicMock()

    async def push_to_jira(self, request, user_id):
        raise RuntimeError("boom")


class DummyHttpService:
    db = MagicMock()

    async def push_to_jira(self, request, user_id):
        raise HTTPException(status_code=400, detail="bad")


@pytest.mark.asyncio
async def test_push_to_jira_re_raises_http_exception():
    with pytest.raises(HTTPException):
        await push_to_jira(
            request=DummyRequest(),
            service=DummyHttpService(),
            current_user_id=_DUMMY_USER_ID,
        )


@pytest.mark.asyncio
async def test_push_to_jira_reraises_generic_exception():
    # Generic (non-HTTPException) errors propagate unchanged out of the endpoint.
    # The audit_log decorator logs/records them, and FastAPI's global exception
    # handler (see app/core/exception_handlers.py) converts them to a 500 at the
    # HTTP layer — the endpoint itself no longer duplicates that conversion.
    with pytest.raises(RuntimeError, match="boom"):
        await push_to_jira(
            request=DummyRequest(),
            service=DummyService(),
            current_user_id=_DUMMY_USER_ID,
        )


@pytest.mark.asyncio
@patch(
    "app.api.v1.endpoints.database_operations.DatabaseService.save_selected_stories",
)
async def test_save_stories(mock_import):
    mock_import.return_value = {"success": True}

    payload = MagicMock()
    payload.selected_epics = []
    payload.project_id = _DUMMY_PROJECT_ID

    result = await save_stories(
        payload,
        MagicMock(),
        _DUMMY_USER_ID,
    )

    assert result["success"] is True


@pytest.mark.asyncio
@patch(
    "app.api.v1.endpoints.database_operations.DatabaseService.save_selected_stories",
)
async def test_save_stories_empty(mock_import):
    mock_import.return_value = {
        "success": True,
        "inserted": [],
    }

    payload = MagicMock()
    payload.selected_epics = []
    payload.project_id = _DUMMY_PROJECT_ID

    result = await save_stories(
        payload,
        MagicMock(),
        _DUMMY_USER_ID,
    )

    assert result["success"] is True
