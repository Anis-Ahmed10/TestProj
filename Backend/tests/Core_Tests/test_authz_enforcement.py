from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_request_authorizer, require_permission
from app.components.authorizer import AuthenticatedUser, Permission
from app.core.exception_handlers import register_exception_handlers

_UID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=_UID,
        name="Test User",
        email="test.user@example.com",
        role="Test Lead",
        is_active=True,
    )


class _Authorizer:
    """Stub authorizer whose decision is fixed per test."""

    def __init__(self, allow: bool) -> None:
        self._allow = allow

    def has_permission(self, user, permission) -> bool:
        return self._allow

    def permissions_for(self, user) -> frozenset:
        return frozenset()


def _build_client(*, allow: bool, authenticated: bool = True) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get(
        "/guarded",
        dependencies=[Depends(require_permission(Permission.CLIENT_CREATE))],
    )
    def guarded() -> dict:
        return {"ok": True}

    app.dependency_overrides[get_request_authorizer] = lambda: _Authorizer(allow)
    if authenticated:
        app.dependency_overrides[get_current_user] = _user
    return TestClient(app, raise_server_exceptions=False)


def test_allowed_permission_returns_200() -> None:
    response = _build_client(allow=True).get("/guarded")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_denied_permission_returns_403() -> None:
    response = _build_client(allow=False).get("/guarded")
    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "AUTHORIZATION_DENIED"


def test_unauthenticated_request_is_401_not_403() -> None:
    # No get_current_user override and no Authorization header -> identity fails first.
    response = _build_client(allow=True, authenticated=False).get("/guarded")
    assert response.status_code == 401
