from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.dependencies import get_current_user, get_current_user_id
from app.components.authorizer import AuthenticatedUser
from app.core.exceptions import AuthorizationError

_UID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

_VALID_CLAIMS = {
    "sub": str(_UID),
    "email": "user@example.com",
    "cognito:username": str(_UID),
    "name": "Test User",
}


def _make_user(role: str = "Test Lead", is_active: bool = True) -> MagicMock:
    """Build a users-table row stub with the attributes get_current_user reads."""
    user = MagicMock()
    user.id = _UID
    user.name = "Test User"
    user.email = "user@example.com"
    user.role = role
    user.is_active = is_active
    return user


def _call(authorization, db=None):
    """Call get_current_user with a mock DB session."""
    if db is None:
        db = MagicMock()
    return get_current_user(authorization=authorization, db=db)


def test_no_authorization_header_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        _call(authorization=None)
    assert exc_info.value.status_code == 401


def test_authorization_without_bearer_prefix_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        _call(authorization="Token abc123")
    assert exc_info.value.status_code == 401


def test_invalid_jwt_raises_401():
    """ValueError from decode_jwt_payload → 401."""
    with patch("app.api.dependencies.decode_jwt_payload", side_effect=ValueError("bad")):
        with pytest.raises(HTTPException) as exc_info:
            _call(authorization="Bearer bad.token")
    assert exc_info.value.status_code == 401


def test_missing_email_claim_raises_401():
    """Token with no email claim → 401 with specific detail."""
    with patch(
        "app.api.dependencies.decode_jwt_payload", return_value={"cognito:username": str(_UID)}
    ):
        with pytest.raises(HTTPException) as exc_info:
            _call(authorization="Bearer valid.token")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token missing email claim"


def test_missing_sub_claim_raises_401():
    """KeyError when sub is absent → 401 with specific detail."""
    claims_no_sub = {"email": "user@example.com", "cognito:username": str(_UID), "name": "Bob"}
    with patch("app.api.dependencies.decode_jwt_payload", return_value=claims_no_sub):
        with pytest.raises(HTTPException) as exc_info:
            _call(authorization="Bearer valid.token")
    assert exc_info.value.status_code == 401
    assert "Cognito claims" in exc_info.value.detail


def test_existing_user_returns_authenticated_user():
    """User already exists in DB → full context returned without creating."""
    existing_user = _make_user()

    with (
        patch("app.api.dependencies.decode_jwt_payload", return_value=_VALID_CLAIMS),
        patch("app.api.dependencies.get_user_by_email", return_value=existing_user),
        patch("app.api.dependencies.create_user_on_signup") as mock_create,
    ):
        result = _call(authorization="Bearer good.token")

    assert isinstance(result, AuthenticatedUser)
    assert result.id == _UID
    assert result.role == "Test Lead"
    assert result.is_active is True
    mock_create.assert_not_called()


def test_new_user_is_created_and_returned():
    """User not found in DB → create_user_on_signup is called; context returned."""
    new_user = _make_user()
    db = MagicMock()

    with (
        patch("app.api.dependencies.decode_jwt_payload", return_value=_VALID_CLAIMS),
        patch("app.api.dependencies.get_user_by_email", return_value=None),
        patch("app.api.dependencies.create_user_on_signup", return_value=new_user) as mock_create,
    ):
        result = get_current_user(authorization="Bearer good.token", db=db)

    assert result.id == _UID
    mock_create.assert_called_once_with(
        db, _UID, name=_VALID_CLAIMS["name"], email=_VALID_CLAIMS["email"]
    )


def test_inactive_user_raises_403():
    """Deactivated users are rejected even with a valid token."""
    inactive_user = _make_user(is_active=False)

    with (
        patch("app.api.dependencies.decode_jwt_payload", return_value=_VALID_CLAIMS),
        patch("app.api.dependencies.get_user_by_email", return_value=inactive_user),
    ):
        with pytest.raises(AuthorizationError) as exc_info:
            _call(authorization="Bearer good.token")
    assert exc_info.value.status_code == 403


def test_custom_role_is_preserved():
    """Roles outside the seeded catalogue pass through; the DB decides authority."""
    custom_user = _make_user(role="Release Manager")

    with (
        patch("app.api.dependencies.decode_jwt_payload", return_value=_VALID_CLAIMS),
        patch("app.api.dependencies.get_user_by_email", return_value=custom_user),
    ):
        result = _call(authorization="Bearer good.token")

    assert result.role == "Release Manager"


def test_role_casing_is_normalised():
    """Legacy lowercase 'test lead' rows resolve to the canonical name."""
    legacy_user = _make_user(role="test lead")

    with (
        patch("app.api.dependencies.decode_jwt_payload", return_value=_VALID_CLAIMS),
        patch("app.api.dependencies.get_user_by_email", return_value=legacy_user),
    ):
        result = _call(authorization="Bearer good.token")

    assert result.role == "Test Lead"


def test_get_current_user_id_delegates_to_current_user():
    current_user = AuthenticatedUser(
        id=_UID,
        name="Test User",
        email="user@example.com",
        role="Viewer",
        is_active=True,
    )
    assert get_current_user_id(current_user=current_user) == _UID
