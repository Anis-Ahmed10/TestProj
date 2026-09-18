"""Endpoint tests for POST /database/story-edit-log."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_current_user, get_request_authorizer
from app.api.v1.endpoints.database_operations import router
from app.components.authorizer import AuthenticatedUser, Role
from app.core.connection import get_db
from app.core.exception_handlers import register_exception_handlers


class _AllowAllAuthorizer:
    """Test authorizer that grants every permission; authz is not under test here."""

    def has_permission(self, user, permission) -> bool:
        return True

    def permissions_for(self, user) -> frozenset:
        return frozenset()


PROJECT_ID = str(uuid.uuid4())

VALID_PAYLOAD = {
    "project_id": PROJECT_ID,
    "edit_log": [
        {
            "storyId": "STORY-1",
            "epicId": "EPIC-1",
            "editedAt": "2026-06-23T10:30:00Z",
            "changes": [{"field": "storyTitle", "before": "Old title", "after": "New title"}],
        }
    ],
}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)

    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Test User",
        email="test.user@example.com",
        role=Role.TEST_LEAD.value,
        is_active=True,
    )
    app.dependency_overrides[get_request_authorizer] = lambda: _AllowAllAuthorizer()

    with patch("app.api.dependencies.get_visible_project_ids", return_value=None):
        yield TestClient(app, raise_server_exceptions=False)


URL = "/database/story-edit-log"


def test_returns_201_with_saved_count(client):
    with patch(
        "app.api.v1.endpoints.database_operations.DatabaseService.save_story_edit_log"
    ) as mock_svc:
        mock_svc.return_value = 1
        response = client.post(URL, json=VALID_PAYLOAD)

    assert response.status_code == 201
    assert response.json() == {"saved": 1}


def test_empty_edit_log_returns_422(client):
    response = client.post(URL, json={"project_id": PROJECT_ID, "edit_log": []})
    assert response.status_code == 422


def test_calls_service_with_parsed_edit_log(client):
    with patch(
        "app.api.v1.endpoints.database_operations.DatabaseService.save_story_edit_log"
    ) as mock_svc:
        mock_svc.return_value = 1
        client.post(URL, json=VALID_PAYLOAD)

    mock_svc.assert_called_once()
    edit_log_arg = mock_svc.call_args.kwargs["edit_log"]
    assert len(edit_log_arg) == 1
    assert edit_log_arg[0].storyId == "STORY-1"


_ONE_CHANGE = [{"field": "storyTitle", "before": "Old", "after": "New"}]


def test_returns_422_when_story_id_missing(client):
    bad_payload = {
        "project_id": PROJECT_ID,
        "edit_log": [
            {
                "epicId": "EPIC-1",
                "editedAt": "2026-06-23T10:30:00Z",
                "changes": _ONE_CHANGE,
            }
        ],
    }
    response = client.post(URL, json=bad_payload)
    assert response.status_code == 422


def test_returns_422_when_edited_at_invalid(client):
    bad_payload = {
        "project_id": PROJECT_ID,
        "edit_log": [
            {
                "storyId": "STORY-1",
                "epicId": "EPIC-1",
                "editedAt": "not-a-date",
                "changes": _ONE_CHANGE,
            }
        ],
    }
    response = client.post(URL, json=bad_payload)
    assert response.status_code == 422


def test_returns_422_when_edit_log_field_missing(client):
    response = client.post(URL, json={"project_id": PROJECT_ID})
    assert response.status_code == 422


def test_returns_422_when_project_id_missing(client):
    payload_without_project_id = {"edit_log": VALID_PAYLOAD["edit_log"]}
    response = client.post(URL, json=payload_without_project_id)
    assert response.status_code == 422


def test_returns_500_when_service_raises(client):
    with patch(
        "app.api.v1.endpoints.database_operations.DatabaseService.save_story_edit_log"
    ) as mock_svc:
        mock_svc.side_effect = SQLAlchemyError("DB exploded")
        response = client.post(URL, json=VALID_PAYLOAD)

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "STORY_EDIT_LOG_SAVE_FAILED"
    assert body["error"]["message"] == "Failed to save story edit log"


def test_multiple_records_returns_correct_count(client):
    with patch(
        "app.api.v1.endpoints.database_operations.DatabaseService.save_story_edit_log"
    ) as mock_svc:
        mock_svc.return_value = 4
        payload = {
            "project_id": PROJECT_ID,
            "edit_log": [
                {
                    "storyId": f"STORY-{i}",
                    "epicId": "EPIC-1",
                    "editedAt": "2026-06-23T10:30:00Z",
                    "changes": [{"field": "storyTitle", "before": "x", "after": "y"}],
                }
                for i in range(4)
            ],
        }
        response = client.post(URL, json=payload)

    assert response.status_code == 201
    assert response.json()["saved"] == 4


def test_returns_403_when_caller_lacks_project_access(client):
    with patch(
        "app.api.dependencies.get_visible_project_ids",
        return_value={uuid.uuid4()},
    ):
        response = client.post(URL, json=VALID_PAYLOAD)

    assert response.status_code == 403
