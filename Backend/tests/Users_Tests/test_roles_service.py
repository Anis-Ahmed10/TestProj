"""Tests for UsersService.list_roles and UsersService.update_user_role."""

from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.exceptions import AppException
from app.services.users import UsersService

_DUMMY_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_DUMMY_ROLE_NAME = "Test Manager"


def _make_role_record(**overrides):
    defaults = {
        "id": uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        "name": _DUMMY_ROLE_NAME,
        "description": "Manages test teams",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_user_record(**overrides):
    defaults = {
        "id": _DUMMY_USER_ID,
        "name": "Alice",
        "email": "alice@example.com",
        "role": _DUMMY_ROLE_NAME,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# list_roles
# ---------------------------------------------------------------------------


class ListRolesServiceTests(unittest.TestCase):
    """Verify UsersService.list_roles delegates correctly and maps output."""

    @patch("app.services.users.list_roles")
    def test_returns_mapped_role_summaries(self, mock_list_roles) -> None:
        mock_list_roles.return_value = [_make_role_record()]

        db = MagicMock()
        service = UsersService(db=db)

        result = service.list_roles(db)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, _DUMMY_ROLE_NAME)
        mock_list_roles.assert_called_once_with(db)

    @patch("app.services.users.list_roles")
    def test_returns_empty_list_when_no_roles(self, mock_list_roles) -> None:
        mock_list_roles.return_value = []

        db = MagicMock()
        service = UsersService(db=db)

        result = service.list_roles(db)

        self.assertEqual(result, [])

    @patch("app.services.users.list_roles")
    def test_wraps_unexpected_failure(self, mock_list_roles) -> None:
        mock_list_roles.side_effect = RuntimeError("boom")

        db = MagicMock()
        service = UsersService(db=db)

        with self.assertRaises(AppException) as ctx:
            service.list_roles(db)

        self.assertEqual(ctx.exception.code, "ROLES_LIST_FAILED")
        self.assertEqual(ctx.exception.status_code, 500)

    @patch("app.services.users.list_roles")
    def test_reraises_app_exception(self, mock_list_roles) -> None:
        expected = AppException(code="ROLES_LIST_FAILED", message="nope", status_code=503)
        mock_list_roles.side_effect = expected

        db = MagicMock()
        service = UsersService(db=db)

        with self.assertRaises(AppException) as ctx:
            service.list_roles(db)

        self.assertIs(ctx.exception, expected)


# ---------------------------------------------------------------------------
# update_user_role
# ---------------------------------------------------------------------------


class UpdateUserRoleServiceTests(unittest.TestCase):
    """Verify UsersService.update_user_role delegates correctly and maps output."""

    @patch("app.services.users.update_user_role")
    def test_returns_updated_user_response(self, mock_update_user_role) -> None:
        mock_update_user_role.return_value = _make_user_record()

        db = MagicMock()
        service = UsersService(db=db)

        result = service.update_user_role(db, _DUMMY_USER_ID, _DUMMY_ROLE_NAME)

        self.assertEqual(result.id, _DUMMY_USER_ID)
        self.assertEqual(result.role, _DUMMY_ROLE_NAME)
        mock_update_user_role.assert_called_once_with(db, _DUMMY_USER_ID, _DUMMY_ROLE_NAME)

    @patch("app.services.users.update_user_role")
    def test_reraises_app_exception(self, mock_update_user_role) -> None:
        expected = AppException(code="UPDATE_USER_ROLE_FAILED", message="nope", status_code=404)
        mock_update_user_role.side_effect = expected

        db = MagicMock()
        service = UsersService(db=db)

        with self.assertRaises(AppException) as ctx:
            service.update_user_role(db, _DUMMY_USER_ID, _DUMMY_ROLE_NAME)

        self.assertIs(ctx.exception, expected)

    @patch("app.services.users.update_user_role")
    def test_wraps_unexpected_failure(self, mock_update_user_role) -> None:
        mock_update_user_role.side_effect = RuntimeError("boom")

        db = MagicMock()
        service = UsersService(db=db)

        with self.assertRaises(AppException) as ctx:
            service.update_user_role(db, _DUMMY_USER_ID, _DUMMY_ROLE_NAME)

        self.assertEqual(ctx.exception.code, "UPDATE_USER_ROLE_FAILED")
        self.assertEqual(ctx.exception.status_code, 500)


if __name__ == "__main__":
    unittest.main()
