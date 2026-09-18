"""Tests for the users API route."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

from app.api.v1.endpoints.users import list_approval_users, list_users
from app.core.exceptions import AppException
from app.schemas.users import ProjectApprover, UserSummary

_DUMMY_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
_DUMMY_PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")


def _make_user_summary(**overrides):
    defaults = {
        "id": _DUMMY_USER_ID,
        "name": "Alice",
        "email": "alice@example.com",
        "role": "Manager",
    }
    defaults.update(overrides)
    return UserSummary(**defaults)


class ListApprovalUsersEndpointTests(unittest.TestCase):
    """Verify list_approval_users endpoint response shape."""

    def test_returns_data_on_success(self) -> None:
        records = [
            ProjectApprover(role_label="Project Manager", name="Pat", email="pat@example.com")
        ]
        service = SimpleNamespace(db=object(), list_approval_users=Mock(return_value=records))

        response = list_approval_users(service, _DUMMY_USER_ID, _DUMMY_PROJECT_ID)

        self.assertEqual(response.message, "Approval users retrieved successfully")
        self.assertEqual(response.data, records)
        service.list_approval_users.assert_called_once_with(service.db, _DUMMY_PROJECT_ID)

    def test_wraps_unexpected_failure(self) -> None:
        service = SimpleNamespace(
            db=object(), list_approval_users=Mock(side_effect=RuntimeError("boom"))
        )

        with self.assertRaises(AppException) as context:
            list_approval_users(service, _DUMMY_USER_ID, _DUMMY_PROJECT_ID)

        self.assertEqual(context.exception.code, "APPROVAL_USERS_LIST_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    def test_reraises_app_exception(self) -> None:
        expected = AppException(code="USERS_LIST_FAILED", message="nope", status_code=503)
        service = SimpleNamespace(db=object(), list_approval_users=Mock(side_effect=expected))

        with self.assertRaises(AppException) as context:
            list_approval_users(service, _DUMMY_USER_ID, _DUMMY_PROJECT_ID)

        self.assertIs(context.exception, expected)


class ListAllUsersEndpointTests(unittest.TestCase):
    """Verify list_users endpoint response shape."""

    def test_returns_data_on_success(self) -> None:
        records = [_make_user_summary()]
        service = SimpleNamespace(db=object(), list_users=Mock(return_value=records))

        response = list_users(service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Users List retrieved successfully")
        self.assertEqual(response.data, records)
        service.list_users.assert_called_once_with(service.db)

    def test_returns_empty_list(self) -> None:
        service = SimpleNamespace(db=object(), list_users=Mock(return_value=[]))

        response = list_users(service, _DUMMY_USER_ID)

        self.assertEqual(response.data, [])

    def test_reraises_app_exception(self) -> None:
        expected = AppException(code="USERS_LIST_FAILED", message="nope", status_code=503)
        service = SimpleNamespace(db=object(), list_users=Mock(side_effect=expected))

        with self.assertRaises(AppException) as context:
            list_users(service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)


if __name__ == "__main__":
    unittest.main()


class ApprovalUsersRouteGuardTests(unittest.TestCase):
    """The route takes a project_id, so it must be scoped like every other one.

    Matched by endpoint identity on the module's own router rather than by path
    off api_router: the path string and the aggregation are incidental to what
    is being asserted, and api_router includes this router twice.
    """

    @staticmethod
    def _approval_users_route():
        from app.api.v1.endpoints.users import router

        return next(
            route
            for route in router.routes
            if getattr(route, "endpoint", None) is list_approval_users
        )

    def test_route_requires_a_visible_project(self) -> None:
        from app.api.dependencies import require_visible_project

        dependencies = self._approval_users_route().dependant.dependencies
        guards = [dependency.call for dependency in dependencies]

        self.assertIn(require_visible_project, guards)

        guard = next(d for d in dependencies if d.call is require_visible_project)
        self.assertEqual([param.name for param in guard.query_params], ["project_id"])
