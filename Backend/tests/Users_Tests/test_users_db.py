"""Tests for app/database/users_db.py — 100% branch coverage."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import DatabaseOperationException
from app.database.users_db import (
    create_user_on_signup,
    get_user_by_email,
    get_user_by_id,
    update_user_jira_credentials,
)


def _make_db():
    return MagicMock()


def test_get_user_by_email_returns_user_when_found():
    """Happy path: DB returns a user record."""
    db = _make_db()
    fake_user = MagicMock()
    db.execute.return_value.scalars.return_value.first.return_value = fake_user

    result = get_user_by_email(db, "  Test@Example.Com  ")

    assert result is fake_user
    # Email must be lowercased + stripped before querying
    db.execute.assert_called_once()


def test_get_user_by_email_returns_none_when_not_found():
    """No user record → returns None."""
    db = _make_db()
    db.execute.return_value.scalars.return_value.first.return_value = None

    result = get_user_by_email(db, "nobody@example.com")

    assert result is None


def test_get_user_by_email_raises_database_operation_exception_on_error():
    """Any DB exception is wrapped in DatabaseOperationException."""
    db = _make_db()
    db.execute.side_effect = RuntimeError("connection lost")

    with pytest.raises(DatabaseOperationException):
        get_user_by_email(db, "user@example.com")


_UID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def test_create_user_on_signup_happy_path():
    """User is created, committed, and refreshed; the new User is returned."""
    db = _make_db()
    fake_user = MagicMock()
    # db.refresh populates the user; return it via db.refresh side_effect
    db.refresh.side_effect = lambda u: None

    with patch("app.database.users_db.User", return_value=fake_user):
        result = create_user_on_signup(db, _UID, "Alice", "Alice@Example.com")

    db.add.assert_called_once_with(fake_user)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(fake_user)
    assert result is fake_user


def test_create_user_on_signup_integrity_error_returns_existing_user():
    """IntegrityError (duplicate) triggers rollback and returns the existing user."""
    db = _make_db()
    db.add.side_effect = IntegrityError("dup", {}, None)
    existing = MagicMock()

    with patch("app.database.users_db.get_user_by_email", return_value=existing):
        result = create_user_on_signup(db, _UID, "Alice", "alice@example.com")

    db.rollback.assert_called_once()
    assert result is existing


def test_create_user_on_signup_integrity_error_no_existing_user_raises():
    """IntegrityError with no existing record raises DatabaseOperationException."""
    db = _make_db()
    db.add.side_effect = IntegrityError("dup", {}, None)

    with patch("app.database.users_db.get_user_by_email", return_value=None):
        with pytest.raises(DatabaseOperationException):
            create_user_on_signup(db, _UID, "Alice", "alice@example.com")


def test_create_user_on_signup_generic_exception_raises_database_operation_exception():
    """Any non-IntegrityError exception triggers rollback and raises DatabaseOperationException."""
    db = _make_db()
    db.add.side_effect = RuntimeError("disk full")

    with pytest.raises(DatabaseOperationException):
        create_user_on_signup(db, _UID, "Alice", "alice@example.com")

    db.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# get_user_by_id
# ---------------------------------------------------------------------------


def test_get_user_by_id_returns_user_when_found():
    """Happy path: db.get() returns a user record."""
    db = _make_db()
    fake_user = MagicMock()
    db.get.return_value = fake_user

    result = get_user_by_id(db, _UID)

    assert result is fake_user
    db.get.assert_called_once_with(_user_model(), _UID)


def test_get_user_by_id_returns_none_when_not_found():
    """No user record → returns None."""
    db = _make_db()
    db.get.return_value = None

    result = get_user_by_id(db, _UID)

    assert result is None


def test_get_user_by_id_raises_database_operation_exception_on_error():
    """Any DB exception is wrapped in DatabaseOperationException."""
    db = _make_db()
    db.get.side_effect = RuntimeError("connection lost")

    with pytest.raises(DatabaseOperationException):
        get_user_by_id(db, _UID)


def _user_model():
    """Import lazily to avoid an unused top-level import if User model moves."""
    from app.models.users_models import User

    return User


# ---------------------------------------------------------------------------
# update_user_jira_credentials
# ---------------------------------------------------------------------------


def test_update_user_jira_credentials_happy_path_encrypts_and_saves():
    """A provided token is encrypted; a provided email is stored as-is."""
    db = _make_db()
    fake_user = MagicMock()

    with patch("app.database.users_db.get_user_by_id", return_value=fake_user):
        with patch(
            "app.database.users_db.encrypt_token", return_value="ENCRYPTED"
        ) as mock_encrypt:
            result = update_user_jira_credentials(
                db, _UID, jira_email="me@example.com", jira_api_token="plain-token"
            )

    mock_encrypt.assert_called_once_with("plain-token")
    assert fake_user.jira_api_token == "ENCRYPTED"
    assert fake_user.jira_email == "me@example.com"
    db.add.assert_called_once_with(fake_user)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(fake_user)
    assert result is fake_user


def test_update_user_jira_credentials_clears_token_when_empty_string():
    """An empty string is falsy, so it clears the stored token instead of encrypting."""
    db = _make_db()
    fake_user = MagicMock()

    with patch("app.database.users_db.get_user_by_id", return_value=fake_user):
        with patch("app.database.users_db.encrypt_token") as mock_encrypt:
            result = update_user_jira_credentials(db, _UID, jira_api_token="")

    mock_encrypt.assert_not_called()
    assert fake_user.jira_api_token is None
    assert result is fake_user


def test_update_user_jira_credentials_clears_email_when_empty_string():
    db = _make_db()
    fake_user = MagicMock()

    with patch("app.database.users_db.get_user_by_id", return_value=fake_user):
        update_user_jira_credentials(db, _UID, jira_email="")

    assert fake_user.jira_email is None


def test_update_user_jira_credentials_leaves_fields_unset_when_not_passed():
    """Omitting a field (default None) leaves the existing value untouched."""
    db = _make_db()
    fake_user = MagicMock(jira_email="existing@example.com", jira_api_token="existing-token")

    with patch("app.database.users_db.get_user_by_id", return_value=fake_user):
        update_user_jira_credentials(db, _UID)

    assert fake_user.jira_email == "existing@example.com"
    assert fake_user.jira_api_token == "existing-token"


def test_update_user_jira_credentials_raises_when_user_not_found():
    """A missing user raises DatabaseOperationException and does not touch db.add/commit."""
    db = _make_db()

    with patch("app.database.users_db.get_user_by_id", return_value=None):
        with pytest.raises(DatabaseOperationException, match=str(_UID)):
            update_user_jira_credentials(db, _UID, jira_api_token="plain-token")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_update_user_jira_credentials_generic_exception_rolls_back_and_raises():
    """A generic exception during commit triggers rollback and is wrapped."""
    db = _make_db()
    fake_user = MagicMock()
    db.commit.side_effect = RuntimeError("disk full")

    with patch("app.database.users_db.get_user_by_id", return_value=fake_user):
        with patch("app.database.users_db.encrypt_token", return_value="ENCRYPTED"):
            with pytest.raises(DatabaseOperationException):
                update_user_jira_credentials(db, _UID, jira_api_token="plain-token")

    db.rollback.assert_called_once()


def test_update_user_jira_credentials_logs_exception_on_failure():
    """logger.exception('update_user_jira_credentials_failed') is invoked on error."""
    db = _make_db()
    fake_user = MagicMock()
    db.commit.side_effect = RuntimeError("disk full")

    with patch("app.database.users_db.get_user_by_id", return_value=fake_user):
        with patch("app.database.users_db.encrypt_token", return_value="ENCRYPTED"):
            with patch("app.database.users_db.logger") as mock_logger:
                with pytest.raises(DatabaseOperationException):
                    update_user_jira_credentials(db, _UID, jira_api_token="plain-token")

    mock_logger.exception.assert_called_once_with(
        "update_user_jira_credentials_failed",
        extra={"user_id": str(_UID)},
    )
