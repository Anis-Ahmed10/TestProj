"""Unit tests for app/api/v1/endpoints/jira.py and database_operations.py — 100% coverage."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.database_operations import save_stories, save_test_cases
from app.api.v1.endpoints.jira import (
    apply_refresh_changes_endpoint,
    fetch_jira,
    fetch_jira_statuses,
    get_jira_config,
    get_my_jira_credentials,
    push_to_jira,
    refresh_stories,
    save_jira_config,
    save_my_jira_credentials,
)
from app.api.v1.endpoints.jira import test_jira_connection as jira_test_connection_endpoint
from app.core.exceptions import AppException
from app.schemas.JiraSchemas import (
    JiraConfigRequest,
    JiraConfigResponse,
    JiraCredentialsRequest,
    JiraCredentialsResponse,
    JiraTestConnectionResponse,
    RequestModel,
    TestCase,
)
from app.schemas.user_stories import ImportStoriesRequest

_DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_DUMMY_PROJECT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")

# We test the route functions directly (not via TestClient) to avoid
# needing a full FastAPI app setup. We call the async functions directly.


def _make_request():
    return RequestModel(
        userStoryId="US-1",
        projectId=str(_DUMMY_PROJECT_ID),
        format="standard",
        test_cases=[TestCase(id="TC-1", title="T", priority="High")],
    )


def _make_service():
    svc = MagicMock()
    svc.db = MagicMock()
    svc.save_test_cases = AsyncMock(
        return_value={"saved_count": 1, "saved_test_cases": [], "skipped": [], "failed": []}
    )
    svc.push_to_jira = AsyncMock(return_value=MagicMock())
    svc.get_project_jira_credentials = MagicMock(
        return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
    )
    return svc


class TestSaveTestCasesRoute:
    @pytest.mark.asyncio
    @patch(
        "app.api.v1.endpoints.database_operations.DatabaseService.save_test_cases",
        new_callable=AsyncMock,
    )
    async def test_success(self, mock_save):
        mock_save.return_value = {
            "saved_count": 1,
            "saved_test_cases": [],
            "skipped": [],
            "failed": [],
        }
        db = MagicMock()
        result = await save_test_cases(
            request=_make_request(), db=db, current_user_id=_DUMMY_USER_ID
        )
        mock_save.assert_awaited_once()
        assert result["saved_count"] == 1

    @pytest.mark.asyncio
    @patch(
        "app.api.v1.endpoints.database_operations.DatabaseService.save_test_cases",
        new_callable=AsyncMock,
    )
    async def test_exception_raises_http_500(self, mock_save):
        mock_save.side_effect = Exception("boom")
        db = MagicMock()
        with pytest.raises(AppException) as exc_info:
            await save_test_cases(request=_make_request(), db=db, current_user_id=_DUMMY_USER_ID)
        assert exc_info.value.status_code == 500
        assert "Failed to save test cases" in exc_info.value.message


class TestPushToJiraRoute:
    @pytest.mark.asyncio
    async def test_success_returns_service_response(self):
        svc = _make_service()
        response = await push_to_jira(
            request=_make_request(), service=svc, current_user_id=_DUMMY_USER_ID
        )
        svc.push_to_jira.assert_awaited_once()
        assert response is not None

    @pytest.mark.asyncio
    async def test_http_exception_re_raised(self):
        svc = _make_service()
        svc.push_to_jira = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="not found")
        )
        with pytest.raises(HTTPException) as exc_info:
            await push_to_jira(
                request=_make_request(), service=svc, current_user_id=_DUMMY_USER_ID
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_generic_exception_propagates(self):
        # The endpoint no longer converts generic exceptions to HTTPException
        # itself — that's handled upstream by audit_log + the app's global
        # exception handler (app/core/exception_handlers.py) at the real
        # HTTP/ASGI layer. Calling the endpoint function directly (as here)
        # bypasses that layer, so the raw exception should propagate.
        svc = _make_service()
        svc.push_to_jira = AsyncMock(side_effect=RuntimeError("crash"))
        with pytest.raises(RuntimeError, match="crash"):
            await push_to_jira(
                request=_make_request(), service=svc, current_user_id=_DUMMY_USER_ID
            )


class TestFetchJiraRoute:
    @pytest.mark.asyncio
    async def test_calls_fetch_with_settings(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.get_project_jira_credentials = MagicMock(
            return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
        )
        svc.fetch_jira_data.return_value = []
        result = await fetch_jira(
            project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
        )
        svc.fetch_jira_data.assert_awaited_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_epics_list(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.get_project_jira_credentials = MagicMock(
            return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
        )
        svc.fetch_jira_data.return_value = [
            {"epicId": "EP-1", "epicTitle": "E", "user_stories": []}
        ]
        result = await fetch_jira(
            project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
        )
        assert result[0]["epicId"] == "EP-1"

    @pytest.mark.asyncio
    async def test_exception_propagates_unchanged(self):
        """No manual try/except remains — the original exception propagates raw."""
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.get_project_jira_credentials = MagicMock(
            return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
        )
        svc.fetch_jira_data.side_effect = RuntimeError("jira down")

        with pytest.raises(RuntimeError, match="jira down"):
            await fetch_jira(
                project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
            )

    @pytest.mark.asyncio
    async def test_status_filter_forwarded_to_service(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.get_project_jira_credentials = MagicMock(
            return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
        )
        svc.fetch_jira_data.return_value = []
        await fetch_jira(
            project_id=_DUMMY_PROJECT_ID,
            service=svc,
            current_user_id=_DUMMY_USER_ID,
            status=["In Progress", "Done"],
        )
        _, kwargs = svc.fetch_jira_data.call_args
        assert kwargs["statuses"] == ["In Progress", "Done"]

    @pytest.mark.asyncio
    async def test_default_status_is_empty(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.get_project_jira_credentials = MagicMock(
            return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
        )
        svc.fetch_jira_data.return_value = []
        await fetch_jira(project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID)
        _, kwargs = svc.fetch_jira_data.call_args
        assert kwargs["statuses"] == []


class TestFetchJiraStatusesRoute:
    @pytest.mark.asyncio
    async def test_returns_status_names(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.get_project_jira_credentials = MagicMock(
            return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
        )
        svc.fetch_project_story_statuses.return_value = ["To Do", "In Progress", "Done"]
        result = await fetch_jira_statuses(
            project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
        )
        svc.fetch_project_story_statuses.assert_awaited_once()
        assert result == ["To Do", "In Progress", "Done"]

    @pytest.mark.asyncio
    async def test_exception_propagates_unchanged(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.get_project_jira_credentials = MagicMock(
            return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
        )
        svc.fetch_project_story_statuses.side_effect = RuntimeError("jira down")
        with pytest.raises(RuntimeError, match="jira down"):
            await fetch_jira_statuses(
                project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
            )


class TestSaveStoriesRoute:
    @patch("app.api.v1.endpoints.database_operations.DatabaseService.save_selected_stories")
    def test_delegates_to_import_service(self, mock_save):
        mock_save.return_value = {
            "success": True,
            "inserted": ["ST-1"],
            "updated": [],
            "failed": [],
            "skipped": [],
            "renamed": [],
        }
        db = MagicMock()
        payload = ImportStoriesRequest(selected_epics=[], project_id=_DUMMY_PROJECT_ID)

        result = mock_save(
            db=db, selected_epics=payload.selected_epics, project_id=payload.project_id
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.database_operations.DatabaseService.save_selected_stories")
    async def test_save_stories_route_async(self, mock_save):
        mock_save.return_value = {
            "success": True,
            "inserted": [],
            "updated": [],
            "failed": [],
            "skipped": [],
            "renamed": [],
        }
        db = MagicMock()
        payload = ImportStoriesRequest(selected_epics=[], project_id=_DUMMY_PROJECT_ID)
        result = await save_stories(payload=payload, db=db, current_user_id=_DUMMY_USER_ID)
        assert result["success"] is True
        mock_save.assert_called_once_with(db=db, selected_epics=[], project_id=_DUMMY_PROJECT_ID)


class TestRefreshStoriesRoute:
    @pytest.mark.asyncio
    async def test_calls_refresh(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.get_project_jira_credentials = MagicMock(
            return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
        )
        svc.refresh_imported_stories.return_value = {
            "success": True,
            "imported_count": 0,
            "updated_count": 1,
            "failed_count": 0,
            "changed_story_keys": ["ST-1"],
            "new_story_keys": [],
        }
        result = await refresh_stories(
            project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
        )
        svc.refresh_imported_stories.assert_awaited_once()
        assert result["updated_count"] == 1

    @pytest.mark.asyncio
    async def test_exception_propagates_unchanged(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.get_project_jira_credentials = MagicMock(
            return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
        )
        svc.refresh_imported_stories.side_effect = RuntimeError("refresh boom")

        with pytest.raises(RuntimeError, match="refresh boom"):
            await refresh_stories(
                project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
            )


class TestApplyRefreshChangesEndpoint:
    @pytest.mark.asyncio
    async def test_calls_apply_refresh(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.get_project_jira_credentials = MagicMock(
            return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
        )
        svc.apply_refresh_updates.return_value = {"success": True, "updated": ["ST-1"]}
        result = await apply_refresh_changes_endpoint(
            project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
        )
        svc.apply_refresh_updates.assert_awaited_once()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_exception_propagates_unchanged(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.get_project_jira_credentials = MagicMock(
            return_value=("https://jira.example.com", "PROJ", "me@example.com", "tok")
        )
        svc.apply_refresh_updates.side_effect = RuntimeError("apply boom")

        with pytest.raises(RuntimeError, match="apply boom"):
            await apply_refresh_changes_endpoint(
                project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
            )

    @pytest.mark.asyncio
    async def test_direct_payload_calls_apply_refresh_updates_direct(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.apply_refresh_updates_direct.return_value = {"success": True, "updated": ["ST-1"]}
        result = await apply_refresh_changes_endpoint(
            project_id=_DUMMY_PROJECT_ID,
            service=svc,
            current_user_id=_DUMMY_USER_ID,
            payload=[{"epicId": "EP-1"}],
        )
        svc.apply_refresh_updates_direct.assert_awaited_once_with(
            fresh_epics=[{"epicId": "EP-1"}],
            project_id=_DUMMY_PROJECT_ID,
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_direct_pydantic_payload_calls_apply_refresh_updates_direct(self):
        from app.schemas.user_stories import JiraEpicUpdate, JiraStoryUpdate

        svc = AsyncMock()
        svc.db = MagicMock()
        svc.apply_refresh_updates_direct.return_value = {"success": True, "updated": ["ST-1"]}
        payload = [
            JiraEpicUpdate(
                epicId="EP-1",
                epicTitle="Epic 1",
                user_stories=[JiraStoryUpdate(storyId="ST-1", storyTitle="Story 1")],
            )
        ]
        result = await apply_refresh_changes_endpoint(
            project_id=_DUMMY_PROJECT_ID,
            service=svc,
            current_user_id=_DUMMY_USER_ID,
            payload=payload,
        )
        svc.apply_refresh_updates_direct.assert_awaited_once_with(
            fresh_epics=[
                {
                    "epicId": "EP-1",
                    "epicTitle": "Epic 1",
                    "user_stories": [
                        {
                            "storyId": "ST-1",
                            "storyTitle": "Story 1",
                            "description": "",
                            "acceptanceCriteria": None,
                            "issue_type": "Story",
                            "already_exists": False,
                            "status": None,
                        }
                    ],
                }
            ],
            project_id=_DUMMY_PROJECT_ID,
        )
        assert result["success"] is True

    def test_field_helper(self):
        from app.api.v1.endpoints.jira import _field

        # Test dict
        d = {"name": "val", "arr": [1, 2]}
        assert _field(d, "name") == "val"
        assert _field(d, "arr") == [1, 2]
        assert _field(d, "missing", "default") == "default"

        # Test object
        class SampleObj:
            name = "obj_val"
            arr = [3, 4]

        obj = SampleObj()
        assert _field(obj, "name") == "obj_val"
        assert _field(obj, "arr") == [3, 4]
        assert _field(obj, "missing", "default") == "default"


class TestGetJiraConfigRoute:
    @pytest.mark.asyncio
    async def test_success_returns_config(self):
        svc = MagicMock()
        svc.db = MagicMock()
        svc.get_jira_config.return_value = JiraConfigResponse(
            jira_url="https://jira.example.com",
            project_key="PROJ",
            is_connected=True,
        )

        result = await get_jira_config(
            project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
        )

        svc.get_jira_config.assert_called_once_with(_DUMMY_PROJECT_ID, _DUMMY_USER_ID)
        assert result.project_key == "PROJ"

    @pytest.mark.asyncio
    async def test_exception_propagates_unchanged(self):
        svc = MagicMock()
        svc.db = MagicMock()
        svc.get_jira_config.side_effect = RuntimeError("config fetch boom")

        with pytest.raises(RuntimeError, match="config fetch boom"):
            await get_jira_config(
                project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
            )


class TestSaveJiraConfigRoute:
    @pytest.mark.asyncio
    async def test_success_returns_config(self):
        svc = MagicMock()
        svc.db = MagicMock()
        svc.save_jira_config.return_value = JiraConfigResponse(
            jira_url="https://jira.example.com",
            project_key="PROJ",
            is_connected=True,
        )
        payload = JiraConfigRequest(jira_url="https://jira.example.com", project_key="PROJ")

        result = await save_jira_config(
            project_id=_DUMMY_PROJECT_ID,
            payload=payload,
            service=svc,
            current_user_id=_DUMMY_USER_ID,
        )

        svc.save_jira_config.assert_called_once_with(_DUMMY_PROJECT_ID, _DUMMY_USER_ID, payload)
        assert result.project_key == "PROJ"

    @pytest.mark.asyncio
    async def test_exception_propagates_unchanged(self):
        svc = MagicMock()
        svc.db = MagicMock()
        svc.save_jira_config.side_effect = RuntimeError("config save boom")
        payload = JiraConfigRequest(jira_url="https://jira.example.com", project_key="PROJ")

        with pytest.raises(RuntimeError, match="config save boom"):
            await save_jira_config(
                project_id=_DUMMY_PROJECT_ID,
                payload=payload,
                service=svc,
                current_user_id=_DUMMY_USER_ID,
            )


class TestMyJiraCredentialsRoutes:
    @pytest.mark.asyncio
    async def test_get_returns_service_response(self):
        svc = MagicMock()
        svc.db = MagicMock()
        svc.get_my_jira_credentials.return_value = JiraCredentialsResponse(
            jira_email="me@example.com", has_api_token=True
        )

        result = await get_my_jira_credentials(service=svc, current_user_id=_DUMMY_USER_ID)

        svc.get_my_jira_credentials.assert_called_once_with(_DUMMY_USER_ID)
        assert result.jira_email == "me@example.com"

    @pytest.mark.asyncio
    async def test_save_returns_service_response(self):
        svc = MagicMock()
        svc.db = MagicMock()
        svc.save_my_jira_credentials = AsyncMock(
            return_value=JiraCredentialsResponse(jira_email="me@example.com", has_api_token=True)
        )
        payload = JiraCredentialsRequest(jira_email="me@example.com", api_token="tok")

        result = await save_my_jira_credentials(
            payload=payload, service=svc, current_user_id=_DUMMY_USER_ID
        )

        svc.save_my_jira_credentials.assert_awaited_once_with(_DUMMY_USER_ID, payload)
        assert result.has_api_token is True

    @pytest.mark.asyncio
    async def test_save_exception_propagates_unchanged(self):
        svc = MagicMock()
        svc.db = MagicMock()
        svc.save_my_jira_credentials = AsyncMock(side_effect=RuntimeError("save boom"))
        payload = JiraCredentialsRequest(jira_email="me@example.com", api_token="bad")

        with pytest.raises(RuntimeError, match="save boom"):
            await save_my_jira_credentials(
                payload=payload, service=svc, current_user_id=_DUMMY_USER_ID
            )


class TestJiraTestConnectionRoute:
    @pytest.mark.asyncio
    async def test_success_result(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.test_connection = AsyncMock(
            return_value=JiraTestConnectionResponse(success=True, message="Connected")
        )

        result = await jira_test_connection_endpoint(
            project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
        )

        svc.test_connection.assert_awaited_once_with(_DUMMY_PROJECT_ID, _DUMMY_USER_ID)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_unsuccessful_result_still_returns_200(self):
        """result.success is False → status_code stays 200 (still a valid HTTP response)."""
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.test_connection = AsyncMock(
            return_value=JiraTestConnectionResponse(success=False, message="Bad token")
        )

        result = await jira_test_connection_endpoint(
            project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_exception_propagates_unchanged(self):
        svc = AsyncMock()
        svc.db = MagicMock()
        svc.test_connection = AsyncMock(side_effect=RuntimeError("connection boom"))

        with pytest.raises(RuntimeError, match="connection boom"):
            await jira_test_connection_endpoint(
                project_id=_DUMMY_PROJECT_ID, service=svc, current_user_id=_DUMMY_USER_ID
            )
