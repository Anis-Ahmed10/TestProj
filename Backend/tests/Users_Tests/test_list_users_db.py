"""Tests for app.database.users_db.list_users."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.core.exceptions import DatabaseOperationException
from app.database.users_db import list_users


class ListAllUsersDbTests(unittest.TestCase):
    """Verify list_users query behaviour and error wrapping."""

    def test_returns_users_from_query(self) -> None:
        """Happy path: DB returns a list of active users."""
        db = MagicMock()
        fake_users = [MagicMock(), MagicMock()]
        db.execute.return_value.scalars.return_value.all.return_value = fake_users

        result = list_users(db)

        self.assertEqual(result, fake_users)
        db.execute.assert_called_once()

    def test_returns_empty_list_when_no_users(self) -> None:
        """No active users → returns an empty list."""
        db = MagicMock()
        db.execute.return_value.scalars.return_value.all.return_value = []

        result = list_users(db)

        self.assertEqual(result, [])

    def test_wraps_unexpected_failure(self) -> None:
        """Any DB exception is wrapped in DatabaseOperationException."""
        db = MagicMock()
        db.execute.side_effect = RuntimeError("connection lost")

        with self.assertRaises(DatabaseOperationException):
            list_users(db)

    def test_logs_exception_on_failure(self) -> None:
        """logger.exception('list_users_failed') is invoked on error."""
        db = MagicMock()
        db.execute.side_effect = RuntimeError("connection lost")

        with patch("app.database.users_db.logger") as mock_logger:
            with self.assertRaises(DatabaseOperationException):
                list_users(db)

        mock_logger.exception.assert_called_once_with("list_users_failed")


if __name__ == "__main__":
    unittest.main()
