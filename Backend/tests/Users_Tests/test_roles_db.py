"""Tests for app/database/users_db.py — list_roles and update_user_role."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import DatabaseOperationException, ResourceNotFoundError
from app.database.users_db import list_roles, update_user_role

_UID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_DUMMY_ROLE_NAME = "Test Manager"


def _make_db() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# list_roles
# ---------------------------------------------------------------------------


def test_list_roles_returns_all_roles():
    """Happy path: DB returns a list of role records."""
    db = _make_db()
    fake_roles = [MagicMock(name="Test Lead"), MagicMock(name="Test Manager")]
    db.execute.return_value.scalars.return_value.all.return_value = fake_roles

    result = list_roles(db)

    assert result == fake_roles
    db.execute.assert_called_once()


def test_list_roles_returns_empty_list_when_no_roles():
    """No roles in DB returns an empty list."""
    db = _make_db()
    db.execute.return_value.scalars.return_value.all.return_value = []

    result = list_roles(db)

    assert result == []


def test_list_roles_raises_database_operation_exception_on_error():
    """Any DB exception is wrapped in DatabaseOperationException."""
    db = _make_db()
    db.execute.side_effect = RuntimeError("connection lost")

    with pytest.raises(DatabaseOperationException):
        list_roles(db)


def test_list_roles_logs_exception_on_failure():
    """logger.exception('list_roles_failed') is invoked on error."""
    db = _make_db()
    db.execute.side_effect = RuntimeError("connection lost")

    with patch("app.database.users_db.logger") as mock_logger:
        with pytest.raises(DatabaseOperationException):
            list_roles(db)

    mock_logger.exception.assert_called_once_with("list_roles_failed")


# ---------------------------------------------------------------------------
# update_user_role
# ---------------------------------------------------------------------------


def test_update_user_role_happy_path():
    """Happy path: user and role both found; role is assigned and user returned."""
    db = _make_db()
    fake_user = MagicMock()
    fake_role = MagicMock()
    fake_role.name = _DUMMY_ROLE_NAME

    db.execute.return_value.scalars.return_value.first.return_value = fake_role

    with patch("app.database.users_db.get_user_by_id", return_value=fake_user):
        result = update_user_role(db, _UID, _DUMMY_ROLE_NAME)

    assert fake_user.role == _DUMMY_ROLE_NAME
    db.add.assert_called_once_with(fake_user)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(fake_user)
    assert result is fake_user


def test_update_user_role_raises_when_user_not_found():
    """Missing user → ResourceNotFoundError before touching DB."""
    db = _make_db()

    with patch("app.database.users_db.get_user_by_id", return_value=None):
        with pytest.raises(ResourceNotFoundError, match=str(_UID)):
            update_user_role(db, _UID, _DUMMY_ROLE_NAME)

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_update_user_role_raises_when_role_not_found():
    """Missing role → ResourceNotFoundError; no commit occurs."""
    db = _make_db()
    fake_user = MagicMock()
    db.execute.return_value.scalars.return_value.first.return_value = None

    with patch("app.database.users_db.get_user_by_id", return_value=fake_user):
        with pytest.raises(ResourceNotFoundError, match="not found"):
            update_user_role(db, _UID, "NonexistentRole")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_update_user_role_generic_exception_rolls_back_and_raises():
    """A generic exception during commit triggers rollback and is wrapped."""
    db = _make_db()
    fake_user = MagicMock()
    fake_role = MagicMock()
    fake_role.name = _DUMMY_ROLE_NAME
    db.execute.return_value.scalars.return_value.first.return_value = fake_role
    db.commit.side_effect = RuntimeError("disk full")

    with patch("app.database.users_db.get_user_by_id", return_value=fake_user):
        with pytest.raises(DatabaseOperationException):
            update_user_role(db, _UID, _DUMMY_ROLE_NAME)

    db.rollback.assert_called_once()


def test_update_user_role_logs_exception_on_failure():
    """logger.exception('update_user_role_failed') is invoked on generic error."""
    db = _make_db()
    fake_user = MagicMock()
    fake_role = MagicMock()
    fake_role.name = _DUMMY_ROLE_NAME
    db.execute.return_value.scalars.return_value.first.return_value = fake_role
    db.commit.side_effect = RuntimeError("disk full")

    with patch("app.database.users_db.get_user_by_id", return_value=fake_user):
        with patch("app.database.users_db.logger") as mock_logger:
            with pytest.raises(DatabaseOperationException):
                update_user_role(db, _UID, _DUMMY_ROLE_NAME)

    mock_logger.exception.assert_called_once_with(
        "update_user_role_failed",
        extra={"user_id": str(_UID), "role_name": _DUMMY_ROLE_NAME},
    )
