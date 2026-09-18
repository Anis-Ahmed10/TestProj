"""Dedicated endpoint tests for client routes."""

import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_client_service,
    get_current_user,
    get_current_user_id,
    get_request_authorizer,
)
from app.api.v1.endpoints import clients as clients_endpoint
from app.api.v1.endpoints.clients import router as clients_router
from app.components.authorizer import AuthenticatedUser, Role
from app.core.connection import get_db
from app.core.exception_handlers import register_exception_handlers
from app.core.exceptions import AppException
from app.schemas.clients import (
    ClientDetailResponseNoTimestamps,
    ClientListResponse,
    ClientResponse,
    ClientUpdate,
)


class _AllowAllAuthorizer:
    """Test authorizer that grants every permission; authz is not under test here."""

    def has_permission(self, user, permission) -> bool:
        return True

    def permissions_for(self, user) -> frozenset:
        return frozenset()


def _make_client(**overrides):
    created_at = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    last_modified = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
    base = {
        "id": 7,
        "name": "Acme Corp",
        "industry": "Technology",
        "location": "Pune",
        "contact": "qa@acme.example",
        "status": "active",
        "manager_id": uuid.UUID("10000000-0000-0000-0000-000000000010"),
        "manager_name": "Test Manager",
        "programmes_count": 2,
        "projects_count": 4,
        "active_members_count": 6,
        "created_at": created_at,
        "last_modified": last_modified,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _StubClientService:
    def __init__(self) -> None:
        self.db = object()
        self.create_result = None
        self.list_result = None
        self.detail_result = None
        self.update_result = None
        self.archive_result = None
        self.create_error = None
        self.list_error = None
        self.detail_error = None
        self.update_error = None
        self.archive_error = None
        self.create_calls = []
        self.list_calls = []
        self.detail_calls = []
        self.update_calls = []
        self.archive_calls = []

    def create_client(self, db, payload, manager_id=None):
        self.create_calls.append((db, payload, manager_id))
        if self.create_error is not None:
            raise self.create_error
        return self.create_result

    def list_clients(self, db, current_user_id):
        self.list_calls.append((db, current_user_id))
        if self.list_error is not None:
            raise self.list_error
        return self.list_result

    def get_client_details(self, client_name, current_user_id):
        self.detail_calls.append((client_name, current_user_id))
        if self.detail_error is not None:
            raise self.detail_error
        return self.detail_result

    def update_client(self, client_name, payload, current_user_id):
        self.update_calls.append((client_name, payload, current_user_id))
        if self.update_error is not None:
            raise self.update_error
        return self.update_result

    def archive_client(self, client_name, current_user_id):
        self.archive_calls.append((client_name, current_user_id))
        if self.archive_error is not None:
            raise self.archive_error
        return self.archive_result


class _ExplodingClientService:
    def get_client_details(
        self, client_name: str, current_user_id: uuid.UUID
    ) -> ClientDetailResponseNoTimestamps:
        _ = (client_name, current_user_id)
        raise RuntimeError("boom")

    def update_client(
        self, client_name: str, payload: ClientUpdate, current_user_id: uuid.UUID
    ) -> ClientResponse:
        _ = (client_name, payload, current_user_id)
        raise RuntimeError("boom")

    def archive_client(self, client_name: str, current_user_id: uuid.UUID) -> str:
        _ = (client_name, current_user_id)
        raise RuntimeError("boom")


class _AppErrorClientService:
    def get_client_details(
        self, client_name: str, current_user_id: uuid.UUID
    ) -> ClientDetailResponseNoTimestamps:
        _ = (client_name, current_user_id)
        raise AppException(code="NOT_FOUND", message="Client missing", status_code=404)

    def update_client(
        self, client_name: str, payload: ClientUpdate, current_user_id: uuid.UUID
    ) -> ClientResponse:
        _ = (client_name, payload, current_user_id)
        raise AppException(code="NOT_FOUND", message="Client missing", status_code=404)

    def archive_client(self, client_name: str, current_user_id: uuid.UUID) -> str:
        _ = (client_name, current_user_id)
        raise AppException(code="NOT_FOUND", message="Client missing", status_code=404)


class _ForbiddenClientService:
    """Service double simulating a client that exists but is outside the
    caller's visibility scope (Lead/Engineer not on any project for it)."""

    def get_client_details(
        self, client_name: str, current_user_id: uuid.UUID
    ) -> ClientDetailResponseNoTimestamps:
        _ = (client_name, current_user_id)
        raise AppException(
            code="FORBIDDEN",
            message="You do not have access to this client.",
            status_code=HTTPStatus.FORBIDDEN,
        )


class _ForbiddenClientServiceForMutations:
    def update_client(self, client_name, payload, current_user_id):
        raise AppException(
            code="FORBIDDEN", message="You do not have access to this client.", status_code=403
        )

    def archive_client(self, client_name, current_user_id):
        raise AppException(
            code="FORBIDDEN", message="You do not have access to this client.", status_code=403
        )


class TestClientEndpoint:
    _DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

    def setup_method(self) -> None:
        self.service = _StubClientService()
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(clients_router, prefix="/api/v1")
        app.dependency_overrides[get_client_service] = lambda: self.service
        app.dependency_overrides[get_db] = lambda: object()
        app.dependency_overrides[get_current_user_id] = lambda: self._DUMMY_USER_ID
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id=self._DUMMY_USER_ID,
            name="Test User",
            email="test.user@example.com",
            role=Role.TEST_LEAD.value,
            is_active=True,
        )
        app.dependency_overrides[get_request_authorizer] = lambda: _AllowAllAuthorizer()
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_create_client_returns_success_response(self) -> None:
        self.service.create_result = ClientResponse.model_validate(_make_client(id=11))
        payload = {
            "name": "  Acme Corp  ",
            "industry": "  Technology  ",
            "location": "  Pune  ",
            "primaryContact": "  qa@acme.example  ",
        }

        response = self.client.post("/api/v1/clients", json=payload)

        body = response.json()
        assert response.status_code == 201
        assert body["success"] is True
        assert body["message"] == "Client created successfully"
        assert body["data"]["name"] == "Acme Corp"
        assert self.service.create_calls[0][1].contact == "qa@acme.example"

    def test_create_client_returns_app_exception(self) -> None:
        self.service.create_error = AppException(
            code="CLIENT_ALREADY_EXISTS",
            message="A client with this name already exists.",
            status_code=HTTPStatus.CONFLICT,
        )
        payload = {
            "name": "Acme Corp",
            "industry": "Technology",
            "location": "Pune",
            "contact": "qa@acme.example",
        }

        response = self.client.post("/api/v1/clients", json=payload)

        assert response.status_code == HTTPStatus.CONFLICT
        assert response.json()["error"]["code"] == "CLIENT_ALREADY_EXISTS"

    def test_create_client_wraps_unexpected_error(self) -> None:
        self.service.create_error = RuntimeError("boom")
        payload = {
            "name": "Acme Corp",
            "industry": "Technology",
            "location": "Pune",
            "contact": "qa@acme.example",
        }

        response = self.client.post("/api/v1/clients", json=payload)

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "CLIENT_CREATE_FAILED"

    def test_list_clients_returns_success_response(self) -> None:
        self.service.list_result = ClientListResponse(
            items=[ClientResponse.model_validate(_make_client(id=21))],
            total=1,
        )

        response = self.client.get("/api/v1/clients")

        body = response.json()
        assert response.status_code == 200
        assert body["message"] == "Clients retrieved successfully"
        assert body["data"]["total"] == 1

    def test_list_clients_passes_current_user_id_to_service(self) -> None:
        self.service.list_result = ClientListResponse(items=[], total=0)

        self.client.get("/api/v1/clients")

        assert len(self.service.list_calls) == 1
        _db, current_user_id = self.service.list_calls[0]
        assert current_user_id == self._DUMMY_USER_ID

    def test_list_clients_uses_empty_message(self) -> None:
        self.service.list_result = ClientListResponse(items=[], total=0)

        response = self.client.get("/api/v1/clients")

        assert response.status_code == 200
        assert response.json()["message"] == "No clients available"

    def test_list_clients_returns_app_exception(self) -> None:
        self.service.list_error = AppException(
            code="CLIENT_LIST_FAILED",
            message="Unable to fetch clients right now.",
            status_code=500,
        )

        response = self.client.get("/api/v1/clients")

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "CLIENT_LIST_FAILED"

    def test_list_clients_wraps_unexpected_error(self) -> None:
        self.service.list_error = RuntimeError("boom")

        response = self.client.get("/api/v1/clients")

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "CLIENT_LIST_FAILED"

    def test_get_client_details_returns_success_response(self) -> None:
        self.service.detail_result = ClientDetailResponseNoTimestamps.model_validate(
            _make_client(programmes=[])
        )

        response = self.client.get("/api/v1/clients/Acme%20Corp")

        body = response.json()
        assert response.status_code == 200
        assert body["success"] is True
        assert body["message"] == "Client retrieved successfully"
        assert body["data"]["name"] == "Acme Corp"
        assert self.service.detail_calls == [("Acme Corp", self._DUMMY_USER_ID)]

    def test_get_client_details_passes_current_user_id_to_service(self) -> None:
        self.service.detail_result = ClientDetailResponseNoTimestamps.model_validate(
            _make_client(programmes=[])
        )

        self.client.get("/api/v1/clients/Acme%20Corp")

        assert len(self.service.detail_calls) == 1
        client_name, current_user_id = self.service.detail_calls[0]
        assert client_name == "Acme Corp"
        assert current_user_id == self._DUMMY_USER_ID

    def test_get_client_details_returns_app_exception(self) -> None:
        self.service.detail_error = AppException(
            code="NOT_FOUND",
            message="Client missing",
            status_code=404,
        )

        response = self.client.get("/api/v1/clients/Acme%20Corp")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_get_client_details_returns_forbidden_when_outside_visibility_scope(self) -> None:
        """A client that exists but isn't visible to the caller (e.g. a Lead
        or Engineer not assigned to any project under it) should surface as
        403, distinct from the 404 used for a client that doesn't exist."""

        self.service.detail_error = AppException(
            code="FORBIDDEN",
            message="You do not have access to this client.",
            status_code=HTTPStatus.FORBIDDEN,
        )

        response = self.client.get("/api/v1/clients/Acme%20Corp")

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.json()["error"]["code"] == "FORBIDDEN"

    def test_update_client_returns_success_response(self) -> None:
        self.service.update_result = ClientResponse.model_validate(
            _make_client(
                name="Acme Global",
                industry="Insurance",
                location="Pune",
                contact="jamie@acme.example",
                status="inactive",
            )
        )
        payload = {
            "name": "Acme Global",
            "industry": "Insurance",
            "location": "Pune",
            "contact": "jamie@acme.example",
            "status": "inactive",
        }

        response = self.client.patch("/api/v1/clients/Acme%20Corp", json=payload)

        body = response.json()
        assert response.status_code == 200
        assert body["success"] is True
        assert body["message"] == "Client updated successfully"
        assert body["data"]["name"] == "Acme Global"
        assert self.service.update_calls[0][0] == "Acme Corp"
        assert self.service.update_calls[0][1].status == "inactive"
        assert self.service.update_calls[0][2] == self._DUMMY_USER_ID

    def test_update_client_returns_app_exception(self) -> None:
        self.service.update_error = AppException(
            code="NOT_FOUND",
            message="Client missing",
            status_code=404,
        )

        response = self.client.patch(
            "/api/v1/clients/Acme%20Corp",
            json={"industry": "Insurance"},
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_archive_client_returns_success_response(self) -> None:
        self.service.archive_result = "Acme Corp"

        response = self.client.delete("/api/v1/clients/Acme%20Corp")

        body = response.json()
        assert response.status_code == 200
        assert body["success"] is True
        assert body["message"] == "Client archived successfully"
        assert body["data"]["archived_client_name"] == "Acme Corp"
        assert self.service.archive_calls == [("Acme Corp", self._DUMMY_USER_ID)]

    def test_archive_client_returns_app_exception(self) -> None:
        self.service.archive_error = AppException(
            code="NOT_FOUND",
            message="Client missing",
            status_code=404,
        )

        response = self.client.delete("/api/v1/clients/Acme%20Corp")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


class TestClientEndpointRouteHandlers:
    _DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

    def test_get_client_details_logs_and_reraises_unexpected_errors(self) -> None:
        with patch("app.utils.audit_log._logger") as mock_logger:
            try:
                clients_endpoint.get_client_details(
                    client_name="Acme Corp",
                    service=_ExplodingClientService(),
                    current_user_id=self._DUMMY_USER_ID,
                )
            except AppException as exc:
                assert exc.code == "CLIENT_DETAILS_FETCH_FAILED"
                assert exc.message == "Failed to fetch client details"
            else:
                raise AssertionError("Expected AppException to be raised")

        mock_logger.exception.assert_called_once_with("%s_operation_failed", "clients")

    def test_get_client_details_reraises_forbidden_without_logging(self) -> None:
        """A 403 raised by the service (visibility guard) should pass
        through untouched, not get logged/wrapped as an unexpected error."""

        with patch("app.utils.audit_log._logger") as mock_logger:
            try:
                clients_endpoint.get_client_details(
                    client_name="Acme Corp",
                    service=_ForbiddenClientService(),
                    current_user_id=self._DUMMY_USER_ID,
                )
            except AppException as exc:
                assert exc.code == "FORBIDDEN"
                assert exc.status_code == HTTPStatus.FORBIDDEN
            else:
                raise AssertionError("Expected AppException to be raised")

        mock_logger.exception.assert_not_called()

    def test_update_client_logs_and_reraises_unexpected_errors(self) -> None:
        with patch("app.utils.audit_log._logger") as mock_logger:
            try:
                clients_endpoint.update_client(
                    client_name="Acme Corp",
                    payload=ClientUpdate(industry="Insurance"),
                    service=_ExplodingClientService(),
                    current_user_id=self._DUMMY_USER_ID,
                )
            except AppException as exc:
                assert exc.code == "CLIENT_UPDATE_FAILED"
                assert exc.message == "Failed to update client"
            else:
                raise AssertionError("Expected AppException to be raised")

        mock_logger.exception.assert_called_once_with("%s_operation_failed", "clients")

    def test_update_client_reraises_application_errors_without_logging(self) -> None:
        with patch("app.utils.audit_log._logger") as mock_logger:
            try:
                clients_endpoint.update_client(
                    client_name="Acme Corp",
                    payload=ClientUpdate(industry="Insurance"),
                    service=_AppErrorClientService(),
                    current_user_id=self._DUMMY_USER_ID,
                )
            except AppException as exc:
                assert exc.code == "NOT_FOUND"
            else:
                raise AssertionError("Expected AppException to be raised")

        mock_logger.exception.assert_not_called()

    def test_archive_client_logs_and_reraises_unexpected_errors(self) -> None:
        with patch("app.utils.audit_log._logger") as mock_logger:
            try:
                clients_endpoint.archive_client(
                    client_name="Acme Corp",
                    service=_ExplodingClientService(),
                    current_user_id=self._DUMMY_USER_ID,
                )
            except AppException as exc:
                assert exc.code == "CLIENT_ARCHIVE_FAILED"
                assert exc.message == "Failed to archive client"
            else:
                raise AssertionError("Expected AppException to be raised")

        mock_logger.exception.assert_called_once_with("%s_operation_failed", "clients")

    def test_archive_client_reraises_application_errors_without_logging(self) -> None:
        with patch("app.utils.audit_log._logger") as mock_logger:
            try:
                clients_endpoint.archive_client(
                    client_name="Acme Corp",
                    service=_AppErrorClientService(),
                    current_user_id=self._DUMMY_USER_ID,
                )
            except AppException as exc:
                assert exc.code == "NOT_FOUND"
            else:
                raise AssertionError("Expected AppException to be raised")

        mock_logger.exception.assert_not_called()

    def test_update_client_reraises_forbidden(self) -> None:
        try:
            clients_endpoint.update_client(
                client_name="Acme Corp",
                payload=ClientUpdate(industry="Insurance"),
                service=_ForbiddenClientServiceForMutations(),
                current_user_id=self._DUMMY_USER_ID,
            )
        except AppException as exc:
            assert exc.code == "FORBIDDEN"
        else:
            raise AssertionError("Expected AppException to be raised")

    def test_archive_client_reraises_forbidden(self) -> None:
        try:
            clients_endpoint.archive_client(
                client_name="Acme Corp",
                service=_ForbiddenClientServiceForMutations(),
                current_user_id=self._DUMMY_USER_ID,
            )
        except AppException as exc:
            assert exc.code == "FORBIDDEN"
        else:
            raise AssertionError("Expected AppException to be raised")
