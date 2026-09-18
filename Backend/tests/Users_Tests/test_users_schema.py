"""Tests for app.schemas.users."""

from __future__ import annotations

import unittest
from uuid import UUID

from app.schemas.users import UserSummary

_DUMMY_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class UserSummaryTests(unittest.TestCase):
    """Verify UserSummary validates and serialises expected fields."""

    def test_builds_from_attributes(self) -> None:
        from types import SimpleNamespace

        record = SimpleNamespace(
            id=_DUMMY_USER_ID,
            name="Alice",
            email="alice@example.com",
            role="Manager",
        )

        summary = UserSummary.model_validate(record)

        self.assertEqual(summary.id, _DUMMY_USER_ID)
        self.assertEqual(summary.name, "Alice")
        self.assertEqual(summary.email, "alice@example.com")
        self.assertEqual(summary.role, "Manager")

    def test_builds_from_attributes_with_null_role(self) -> None:
        """`role` is nullable in the users table — must not fail validation."""
        from types import SimpleNamespace

        record = SimpleNamespace(
            id=_DUMMY_USER_ID,
            name="Bob",
            email="bob@example.com",
            role=None,
        )

        summary = UserSummary.model_validate(record)

        self.assertIsNone(summary.role)


if __name__ == "__main__":
    unittest.main()
