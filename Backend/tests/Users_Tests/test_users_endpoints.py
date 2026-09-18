from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_request_authorizer
from app.api.v1.endpoints.users import router as users_router
from app.components.authorizer import AuthenticatedUser
from app.core.exception_handlers import register_exception_handlers

_UID = uuid.UUID("00000000-0000-0000-0000-000000000001")

ME_URL = "/api/v1/users/current-user"


def _user(role: str = "Test Lead") -> AuthenticatedUser:
    return AuthenticatedUser(
        id=_UID,
        name="Test User",
        email="test.user@example.com",
        role=role,
        is_active=True,
    )


class _Authorizer:
    """Stub authorizer returning a fixed permission set."""

    def __init__(self, permissions: set[str]) -> None:
        self._permissions = frozenset(permissions)

    def has_permission(self, user, permission) -> bool:
        return permission.value in self._permissions

    def permissions_for(self, user) -> frozenset:
        return self._permissions


def _build_client(role: str, permissions: set[str]) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(users_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: _user(role)
    app.dependency_overrides[get_request_authorizer] = lambda: _Authorizer(permissions)
    return TestClient(app, raise_server_exceptions=False)


class TestCurrentUserEndpoint:
    def test_returns_identity_and_sorted_permissions(self) -> None:
        client = _build_client("Test Lead", {"client:read", "client:create", "jira:push"})

        response = client.get(ME_URL)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == str(_UID)
        assert data["name"] == "Test User"
        assert data["email"] == "test.user@example.com"
        assert data["role"] == "Test Lead"
        assert data["permissions"] == ["client:create", "client:read", "jira:push"]

    def test_role_with_no_permissions_returns_empty_list(self) -> None:
        client = _build_client("Unmapped Role", set())

        response = client.get(ME_URL)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["role"] == "Unmapped Role"
        assert data["permissions"] == []
