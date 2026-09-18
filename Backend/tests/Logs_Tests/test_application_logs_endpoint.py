"""Endpoint tests for the application logs route."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_current_user_id, get_request_authorizer
from app.api.v1.endpoints.application_logs import router as logs_router
from app.components.authorizer import AuthenticatedUser, Role
from app.core.connection import get_db
from app.core.exception_handlers import register_exception_handlers

_DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class _AllowAllAuthorizer:
    """Test authorizer that grants every permission; authz is not under test here."""

    def has_permission(self, user, permission) -> bool:
        return True

    def permissions_for(self, user) -> frozenset:
        return frozenset()


def _make_log(**overrides):
    base = {
        "id": uuid.uuid4(),
        "logged_at": datetime(2026, 7, 6, 10, 30, tzinfo=timezone.utc),
        "service_name": "ai",
        "user_id": uuid.uuid4(),
        "http_method": "POST",
        "endpoint": "/test-generator",
        "status_code": 200,
        "message": "Test cases generated successfully",
        "project_id": None,
        "client_name": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestApplicationLogsEndpoint:
    def setup_method(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(logs_router, prefix="/api/v1")
        app.dependency_overrides[get_db] = lambda: object()
        app.dependency_overrides[get_current_user_id] = lambda: _DUMMY_USER_ID
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id=_DUMMY_USER_ID,
            name="Test User",
            email="test@example.com",
            role=Role.TEST_LEAD.value,
            is_active=True,
        )
        app.dependency_overrides[get_request_authorizer] = lambda: _AllowAllAuthorizer()
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_returns_logs_with_total(self) -> None:
        logs = [_make_log(), _make_log(endpoint="/automation-selector")]
        with patch(
            "app.api.v1.endpoints.application_logs.list_log_entries",
            return_value=(logs, 2),
        ):
            response = self.client.get("/api/v1/logs")

        body = response.json()
        assert response.status_code == 200
        assert body["success"] is True
        assert body["message"] == "Application logs retrieved successfully"
        assert body["data"]["total"] == 2
        assert len(body["data"]["logs"]) == 2
        assert body["data"]["logs"][0]["service_name"] == "ai"

    def test_empty_result_uses_empty_message(self) -> None:
        with patch(
            "app.api.v1.endpoints.application_logs.list_log_entries",
            return_value=([], 0),
        ):
            response = self.client.get("/api/v1/logs")

        assert response.status_code == 200
        assert response.json()["message"] == "No application logs found"

    def test_service_filter_forwarded_to_query(self) -> None:
        with patch(
            "app.api.v1.endpoints.application_logs.list_log_entries",
            return_value=([_make_log(service_name="jira", endpoint="/jira/push-to-jira")], 1),
        ) as mock_list:
            response = self.client.get("/api/v1/logs", params={"service": "jira"})

        assert response.status_code == 200
        _, call_kwargs = mock_list.call_args
        assert call_kwargs["service_name"] == "jira"
        assert response.json()["data"]["logs"][0]["service_name"] == "jira"

    def test_pagination_params_forwarded(self) -> None:
        with patch(
            "app.api.v1.endpoints.application_logs.list_log_entries",
            return_value=([], 0),
        ) as mock_list:
            response = self.client.get("/api/v1/logs", params={"limit": 10, "offset": 20})

        assert response.status_code == 200
        _, call_kwargs = mock_list.call_args
        assert call_kwargs["limit"] == 10
        assert call_kwargs["offset"] == 20
