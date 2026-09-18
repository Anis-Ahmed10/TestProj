"""Tests for app.services.users.UsersService."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.core.exceptions import AppException
from app.services.users import UsersService

_DUMMY_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


_DUMMY_PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")


def _make_user_record(**overrides):
    defaults = {
        "id": _DUMMY_USER_ID,
        "name": "Alice",
        "email": "alice@example.com",
        "role": "Manager",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class ListApprovalUsersServiceTests(unittest.TestCase):
    """Verify UsersService.list_approval_users resolves a project's approvers."""

    @patch("app.services.users.get_project_approvers")
    def test_maps_manager_and_lead_to_approvers(self, mock_get_approvers) -> None:
        mock_get_approvers.return_value = [
            ("Project Manager", "Pat Manager", "pat@example.com"),
            ("Project Lead", "Lee Lead", "lee@example.com"),
        ]

        db = MagicMock()
        service = UsersService(db=db)

        result = service.list_approval_users(db, _DUMMY_PROJECT_ID)

        self.assertEqual(
            [(a.role_label, a.name, a.email) for a in result],
            mock_get_approvers.return_value,
        )
        mock_get_approvers.assert_called_once_with(db, _DUMMY_PROJECT_ID)

    @patch("app.services.users.get_project_approvers")
    def test_returns_empty_list_when_project_has_no_approvers(self, mock_get_approvers) -> None:
        mock_get_approvers.return_value = []

        db = MagicMock()
        service = UsersService(db=db)

        result = service.list_approval_users(db, _DUMMY_PROJECT_ID)

        self.assertEqual(result, [])

    @patch("app.services.users.get_project_approvers")
    def test_wraps_unexpected_failure(self, mock_get_approvers) -> None:
        mock_get_approvers.side_effect = RuntimeError("boom")

        db = MagicMock()
        service = UsersService(db=db)

        with self.assertRaises(AppException) as context:
            service.list_approval_users(db, _DUMMY_PROJECT_ID)

        self.assertEqual(context.exception.code, "USERS_LIST_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    @patch("app.services.users.get_project_approvers")
    def test_reraises_app_exception(self, mock_get_approvers) -> None:
        expected = AppException(code="USERS_LIST_FAILED", message="nope", status_code=503)
        mock_get_approvers.side_effect = expected

        db = MagicMock()
        service = UsersService(db=db)

        with self.assertRaises(AppException) as context:
            service.list_approval_users(db, _DUMMY_PROJECT_ID)

        self.assertIs(context.exception, expected)


class ListAllUsersServiceTests(unittest.TestCase):
    """Verify UsersService.list_users logic."""

    @patch("app.services.users.list_users")
    def test_returns_mapped_summaries(self, mock_list_users) -> None:
        mock_list_users.return_value = [_make_user_record()]

        db = MagicMock()
        service = UsersService(db=db)

        result = service.list_users(db)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, "alice@example.com")
        mock_list_users.assert_called_once_with(db)

    @patch("app.services.users.list_users")
    def test_returns_empty_list_when_no_users(self, mock_list_users) -> None:
        mock_list_users.return_value = []

        db = MagicMock()
        service = UsersService(db=db)

        result = service.list_users(db)

        self.assertEqual(result, [])

    @patch("app.services.users.list_users")
    def test_wraps_unexpected_failure(self, mock_list_users) -> None:
        mock_list_users.side_effect = RuntimeError("boom")

        db = MagicMock()
        service = UsersService(db=db)

        with self.assertRaises(AppException) as context:
            service.list_users(db)

        self.assertEqual(context.exception.code, "USERS_LIST_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    @patch("app.services.users.list_users")
    def test_reraises_app_exception(self, mock_list_users) -> None:
        expected = AppException(code="USERS_LIST_FAILED", message="nope", status_code=503)
        mock_list_users.side_effect = expected

        db = MagicMock()
        service = UsersService(db=db)

        with self.assertRaises(AppException) as context:
            service.list_users(db)

        self.assertIs(context.exception, expected)


if __name__ == "__main__":
    unittest.main()
