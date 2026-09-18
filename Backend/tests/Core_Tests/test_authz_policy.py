from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.components.authorizer import (
    ROLE_PERMISSIONS,
    AuthenticatedUser,
    DbAuthorizer,
    Permission,
    Role,
    get_authorizer,
    parse_role,
)
from app.components.authorizer.policy import _EXCLUDED_TEST_LEAD_PERMISSIONS

_UID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _user(role: str) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=_UID,
        name="Test User",
        email="test.user@example.com",
        role=role,
        is_active=True,
    )


class TestParseRole:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Test Lead", Role.TEST_LEAD),
            ("test lead", Role.TEST_LEAD),
            ("  TEST LEAD  ", Role.TEST_LEAD),
            ("Test Manager", Role.TEST_MANAGER),
            ("Test Engineer", Role.TEST_ENGINEER),
        ],
    )
    def test_known_roles_parse_with_casing_drift(self, raw: str, expected: Role) -> None:
        assert parse_role(raw) is expected

    @pytest.mark.parametrize("raw", [None, "", "   ", "Admin", "Viewer", "test-lead"])
    def test_unknown_roles_return_none(self, raw: str | None) -> None:
        assert parse_role(raw) is None


class TestRolePermissionsBaseline:
    def test_every_role_has_a_permission_set(self) -> None:
        assert set(ROLE_PERMISSIONS) == set(Role)

    def test_test_manager_has_every_permission(self) -> None:
        assert ROLE_PERMISSIONS[Role.TEST_MANAGER] == frozenset(Permission)

    def test_test_lead_permissions_exclude_admin_operations(self) -> None:
        assert (
            ROLE_PERMISSIONS[Role.TEST_LEAD]
            == frozenset(Permission) - _EXCLUDED_TEST_LEAD_PERMISSIONS
        )

    def test_only_test_manager_can_manage_users(self) -> None:
        for role, permissions in ROLE_PERMISSIONS.items():
            expected = role is Role.TEST_MANAGER
            assert (Permission.USER_MANAGE in permissions) is expected

    def test_test_engineer_scope(self) -> None:
        engineer = ROLE_PERMISSIONS[Role.TEST_ENGINEER]
        assert Permission.TESTCASE_GENERATE in engineer
        assert Permission.JIRA_PULL in engineer
        assert Permission.PROJECT_READ in engineer
        assert Permission.STORY_REQUEST_APPROVAL in engineer
        assert Permission.CLIENT_CREATE not in engineer
        assert Permission.STORY_APPROVE not in engineer
        assert Permission.USER_MANAGE not in engineer
        assert Permission.TEAM_READ in engineer
        assert Permission.TEAM_AVAILABLE_USERS not in engineer
        assert Permission.TEAM_ADD not in engineer
        assert Permission.TEAM_REMOVE not in engineer
        assert Permission.TESTCASE_UPDATE in engineer


class TestDbAuthorizer:
    def test_has_permission_reflects_resolved_set(self) -> None:
        db = MagicMock()
        with patch(
            "app.components.authorizer.policy.get_permissions_for_role",
            return_value=frozenset({"project:read", "project:create"}),
        ) as mock_resolve:
            authorizer = DbAuthorizer(db)
            user = _user("Test Lead")

            assert authorizer.has_permission(user, Permission.PROJECT_CREATE) is True
            assert authorizer.has_permission(user, Permission.CLIENT_CREATE) is False

        mock_resolve.assert_called_with(db, "Test Lead")

    def test_permissions_for_delegates_to_role_lookup(self) -> None:
        db = MagicMock()
        with patch(
            "app.components.authorizer.policy.get_permissions_for_role",
            return_value=frozenset({"jira:pull"}),
        ):
            assert DbAuthorizer(db).permissions_for(_user("Test Engineer")) == frozenset(
                {"jira:pull"}
            )

    def test_factory_returns_db_authorizer(self) -> None:
        assert isinstance(get_authorizer(MagicMock()), DbAuthorizer)
