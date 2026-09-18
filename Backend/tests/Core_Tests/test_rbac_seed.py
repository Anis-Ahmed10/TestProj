"""Tests for the idempotent RBAC defaults seeder.

The seeder runs on every startup, so the property that matters is idempotence:
a second run against an already-seeded database must add nothing, and a partial
database must be topped up without disturbing admin-added permission links.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.components.authorizer.models import Permission, Role
from app.components.authorizer.policy import ROLE_PERMISSIONS
from app.components.authorizer.seed import seed_rbac_defaults
from app.models.rbac_models import PermissionModel, RoleModel


def _db(permission_rows: list, role_rows: list) -> MagicMock:
    """Mock the executes the seeder issues, in order: advisory lock, permissions, roles."""
    permission_result = MagicMock()
    permission_result.all.return_value = [(row.name, row) for row in permission_rows]
    role_result = MagicMock()
    role_result.scalars.return_value.all.return_value = role_rows

    db = MagicMock()
    db.execute.side_effect = [MagicMock(), permission_result, role_result]
    return db


# Real ORM instances, not stand-ins: the seeder assigns these onto
# RoleModel.permissions, and that instrumented list rejects anything that isn't a
# mapped object.
def _all_permission_rows() -> list[PermissionModel]:
    return [PermissionModel(name=permission.value) for permission in Permission]


def _fully_linked_role(role: Role) -> RoleModel:
    role_row = RoleModel(name=role.value)
    role_row.permissions = [
        PermissionModel(name=permission.value)
        for permission in ROLE_PERMISSIONS.get(role, frozenset())
    ]
    return role_row


class SeedRbacDefaultsTests(unittest.TestCase):
    def test_empty_database_creates_every_permission_and_role(self) -> None:
        db = _db([], [])

        seed_rbac_defaults(db)

        self.assertEqual(db.add.call_count, len(Permission) + len(Role))
        db.commit.assert_called_once()

    def test_existing_role_is_topped_up_with_missing_baseline_permissions(self) -> None:
        role = Role.TEST_LEAD
        baseline = ROLE_PERMISSIONS.get(role, frozenset())
        existing_role = RoleModel(name=role.value)
        db = _db(_all_permission_rows(), [existing_role])

        seed_rbac_defaults(db)

        self.assertEqual(len(existing_role.permissions), len(baseline))
        # Only the two roles that don't exist yet are added; no new permissions.
        self.assertEqual(db.add.call_count, len(Role) - 1)
        db.commit.assert_called_once()

    def test_existing_role_removes_stale_permissions_no_longer_in_baseline(self) -> None:
        role = Role.TEST_LEAD
        stale = PermissionModel(name=Permission.USER_MANAGE.value)
        existing_role = _fully_linked_role(role)
        existing_role.permissions.append(stale)
        db = _db(_all_permission_rows(), [existing_role])

        seed_rbac_defaults(db)

        baseline_names = {p.value for p in ROLE_PERMISSIONS.get(role, frozenset())}
        linked_names = {p.name for p in existing_role.permissions}
        self.assertEqual(linked_names, baseline_names)
        self.assertNotIn(Permission.USER_MANAGE.value, linked_names)

    def test_existing_role_currently_loses_extra_permissions_beyond_baseline(self) -> None:
        role = Role.TEST_ENGINEER
        extra = PermissionModel(name="custom:permission")
        existing_role = _fully_linked_role(role)
        existing_role.permissions.append(extra)
        db = _db(_all_permission_rows(), [existing_role])

        seed_rbac_defaults(db)

        self.assertNotIn(extra, existing_role.permissions)

    def test_fully_seeded_database_changes_nothing(self) -> None:
        db = _db(_all_permission_rows(), [_fully_linked_role(role) for role in Role])

        seed_rbac_defaults(db)

        db.add.assert_not_called()
        db.commit.assert_called_once()

    def test_failure_rolls_back_and_reraises(self) -> None:
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            seed_rbac_defaults(db)

        db.rollback.assert_called_once()
        db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
