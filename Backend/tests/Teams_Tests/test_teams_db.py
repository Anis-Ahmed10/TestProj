"""Tests for app.database.teams_db query functions."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.exceptions import DatabaseOperationException
from app.database.teams_db import (
    get_available_users_for_project,
    get_team_members_by_project,
    remove_member_from_project,
)


class TeamsDbTests(unittest.TestCase):
    """Verify team database query execution and error handling."""

    def setUp(self) -> None:
        self.db = MagicMock()
        self.project_id = uuid4()
        self.user_id = uuid4()

    # --- GET AVAILABLE USERS TESTS ---

    def test_get_available_users_returns_users(self) -> None:
        fake_users = [MagicMock(), MagicMock()]

        self.db.execute.return_value.scalars.return_value.all.return_value = fake_users

        result = get_available_users_for_project(self.db, self.project_id)

        self.assertEqual(result, fake_users)
        self.db.execute.assert_called_once()

    def test_get_available_users_returns_empty_list(self) -> None:
        self.db.execute.return_value.scalars.return_value.all.return_value = []

        result = get_available_users_for_project(self.db, self.project_id)

        self.assertEqual(result, [])

    def test_get_available_users_raises_database_exception(self) -> None:
        self.db.execute.side_effect = Exception("DB failure")

        with self.assertRaises(DatabaseOperationException):
            get_available_users_for_project(self.db, self.project_id)

    # --- GET TEAM MEMBERS TESTS ---

    def test_get_team_members_returns_records(self) -> None:
        fake_data = [(MagicMock(), MagicMock()), (MagicMock(), MagicMock())]

        self.db.execute.return_value.all.return_value = fake_data

        result = get_team_members_by_project(self.db, self.project_id)

        self.assertEqual(result, fake_data)
        self.db.execute.assert_called_once()

    def test_get_team_members_raises_database_exception(self) -> None:
        self.db.execute.side_effect = Exception("DB error")

        with self.assertRaises(DatabaseOperationException):
            get_team_members_by_project(self.db, self.project_id)

    # --- REMOVE MEMBER TESTS ---

    def test_remove_member_success(self) -> None:
        fake_user = MagicMock()
        fake_user.name = "John Doe"

        fake_association = MagicMock()

        # Mock query chain: query().join().filter().first()
        self.db.query.return_value.join.return_value.filter.return_value.first.return_value = (
            fake_user,
            fake_association,
        )

        result = remove_member_from_project(self.db, self.project_id, self.user_id)

        self.db.delete.assert_called_once_with(fake_association)
        self.db.flush.assert_called_once()

        self.assertEqual(result, "John Doe")

    def test_remove_member_not_found(self) -> None:
        self.db.query.return_value.join.return_value.filter.return_value.first.return_value = None

        result = remove_member_from_project(self.db, self.project_id, self.user_id)

        self.assertIsNone(result)
        self.db.delete.assert_not_called()
        self.db.flush.assert_not_called()

    def test_remove_member_raises_database_exception(self) -> None:
        self.db.query.side_effect = Exception("DB failure")

        with self.assertRaises(DatabaseOperationException):
            remove_member_from_project(self.db, self.project_id, self.user_id)


if __name__ == "__main__":
    unittest.main()
