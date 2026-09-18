"""Tests for GET /users/roles and PUT /users/{user_id}/role route handlers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

from app.api.v1.endpoints.users import list_roles, update_user_role
from app.core.exceptions import AppException
from app.schemas.users import RoleSummary, UpdateUserRoleRequest, UpdateUserRoleResponse

_DUMMY_USER_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
_DUMMY_ROLE_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
_DUMMY_ROLE_NAME = "Test Manager"


def _make_role_summary(**overrides):
    defaults = {
        "id": _DUMMY_ROLE_ID,
        "name": _DUMMY_ROLE_NAME,
        "description": None,
    }
    defaults.update(overrides)
    return RoleSummary(**defaults)


def _make_update_role_response(**overrides):
    defaults = {
        "id": _DUMMY_USER_ID,
        "name": "Alice",
        "email": "alice@example.com",
        "role": _DUMMY_ROLE_NAME,
    }
    defaults.update(overrides)
    return UpdateUserRoleResponse(**defaults)


# ---------------------------------------------------------------------------
# GET /users/roles
# ---------------------------------------------------------------------------


class ListRolesEndpointTests(unittest.TestCase):
    """Verify list_roles endpoint response shape."""

    def test_returns_data_on_success(self) -> None:
        records = [_make_role_summary()]
        service = SimpleNamespace(db=object(), list_roles=Mock(return_value=records))

        response = list_roles(service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Roles retrieved successfully")
        self.assertEqual(response.data, records)
        service.list_roles.assert_called_once_with(service.db)

    def test_returns_empty_list(self) -> None:
        service = SimpleNamespace(db=object(), list_roles=Mock(return_value=[]))

        response = list_roles(service, _DUMMY_USER_ID)

        self.assertEqual(response.data, [])

    def test_propagates_app_exception(self) -> None:
        expected = AppException(code="ROLES_LIST_FAILED", message="nope", status_code=503)
        service = SimpleNamespace(db=object(), list_roles=Mock(side_effect=expected))

        with self.assertRaises(AppException) as ctx:
            list_roles(service, _DUMMY_USER_ID)

        self.assertIs(ctx.exception, expected)


# ---------------------------------------------------------------------------
# PUT /users/{user_id}/role
# ---------------------------------------------------------------------------


class UpdateUserRoleEndpointTests(unittest.TestCase):
    """Verify update_user_role endpoint response shape."""

    def test_returns_updated_user_on_success(self) -> None:
        updated = _make_update_role_response()
        service = SimpleNamespace(db=object(), update_user_role=Mock(return_value=updated))
        body = UpdateUserRoleRequest(role_name=_DUMMY_ROLE_NAME)

        response = update_user_role(_DUMMY_USER_ID, body, service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "User role updated successfully")
        self.assertEqual(response.data.role, _DUMMY_ROLE_NAME)
        service.update_user_role.assert_called_once_with(
            service.db, _DUMMY_USER_ID, _DUMMY_ROLE_NAME
        )

    def test_propagates_app_exception_when_user_not_found(self) -> None:
        expected = AppException(
            code="UPDATE_USER_ROLE_FAILED", message="user not found", status_code=404
        )
        service = SimpleNamespace(db=object(), update_user_role=Mock(side_effect=expected))
        body = UpdateUserRoleRequest(role_name=_DUMMY_ROLE_NAME)

        with self.assertRaises(AppException) as ctx:
            update_user_role(_DUMMY_USER_ID, body, service, _DUMMY_USER_ID)

        self.assertIs(ctx.exception, expected)

    def test_propagates_app_exception_when_role_not_found(self) -> None:
        expected = AppException(
            code="UPDATE_USER_ROLE_FAILED", message="role not found", status_code=404
        )
        service = SimpleNamespace(db=object(), update_user_role=Mock(side_effect=expected))
        body = UpdateUserRoleRequest(role_name="NonExistent")

        with self.assertRaises(AppException) as ctx:
            update_user_role(_DUMMY_USER_ID, body, service, _DUMMY_USER_ID)

        self.assertIs(ctx.exception, expected)


if __name__ == "__main__":
    unittest.main()
