"""Tests for Teams API router endpoints."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from app.api.v1.endpoints.projects import (
    add_team_members,
    get_available_users,
    get_team_members,
    remove_team_member,
)
from app.core.exceptions import AppException
from app.schemas.teams import AddTeamMembersPayload, TeamMemberResponse
from app.schemas.users import UserSummary

_DUMMY_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class TeamsEndpointTests(unittest.TestCase):
    """Verify router functions process requests and invoke service methods."""

    def setUp(self) -> None:
        self.mock_service = MagicMock()
        self.project_id = uuid4()
        self.user_id = uuid4()
        self.current_user_id = uuid4()

    def test_get_team_members_endpoint(self) -> None:
        fake_response = [
            TeamMemberResponse(
                id=self.user_id,
                user_id=_DUMMY_USER_ID,
                name="John Doe",
                email="john@example.com",
                hours_this_sprint=5,
                status="Active",
            )
        ]
        self.mock_service.get_project_team_members.return_value = fake_response

        response = get_team_members(
            self.project_id,
            self.mock_service,
            self.current_user_id,
        )

        self.assertTrue(response.success)
        self.assertEqual(response.data, fake_response)
        self.mock_service.get_project_team_members.assert_called_once_with(
            self.project_id, self.current_user_id
        )

    def test_get_available_users_endpoint(self) -> None:
        fake_users = [
            UserSummary(
                id=self.user_id,
                name="Jane Doe",
                email="jane@example.com",
            )
        ]
        self.mock_service.get_available_users.return_value = fake_users

        response = get_available_users(
            self.project_id,
            self.mock_service,
            self.current_user_id,
        )

        self.assertTrue(response.success)
        self.assertEqual(response.data, fake_users)
        self.mock_service.get_available_users.assert_called_once_with(
            self.project_id, self.current_user_id
        )

    def test_add_team_members_endpoint(self) -> None:
        payload = AddTeamMembersPayload(user_ids=[self.user_id])
        self.mock_service.add_members_to_project.return_value = []

        response = add_team_members(
            self.project_id,
            payload,
            self.mock_service,
            self.current_user_id,
        )

        self.assertTrue(response.success)
        self.mock_service.add_members_to_project.assert_called_once_with(
            self.project_id, [self.user_id], self.current_user_id
        )

    def test_remove_team_member_endpoint(self) -> None:
        self.mock_service.remove_member_from_project.return_value = {"removed_user": "John Doe"}

        response = remove_team_member(
            self.project_id,
            self.user_id,
            self.mock_service,
            self.current_user_id,
        )
        self.assertTrue(response.success)
        self.assertIn("removed_user", response.data)
        self.assertEqual(response.data["removed_user"], "John Doe")

        self.mock_service.remove_member_from_project.assert_called_once_with(
            self.project_id, self.user_id, self.current_user_id
        )


class TeamsEndpointForbiddenTests(unittest.TestCase):

    def setUp(self) -> None:
        self.mock_service = MagicMock()
        self.project_id = uuid4()
        self.current_user_id = uuid4()
        self.forbidden = AppException(
            code="FORBIDDEN",
            message="You do not have access to this project.",
            status_code=403,
        )

    def test_get_team_members_reraises_forbidden(self) -> None:
        self.mock_service.get_project_team_members.side_effect = self.forbidden

        with self.assertRaises(AppException) as context:
            get_team_members(self.project_id, self.mock_service, self.current_user_id)

        self.assertIs(context.exception, self.forbidden)

    def test_get_available_users_reraises_forbidden(self) -> None:
        self.mock_service.get_available_users.side_effect = self.forbidden

        with self.assertRaises(AppException) as context:
            get_available_users(self.project_id, self.mock_service, self.current_user_id)

        self.assertIs(context.exception, self.forbidden)

    def test_add_team_members_reraises_forbidden(self) -> None:
        payload = AddTeamMembersPayload(user_ids=[uuid4()])
        self.mock_service.add_members_to_project.side_effect = self.forbidden

        with self.assertRaises(AppException) as context:
            add_team_members(self.project_id, payload, self.mock_service, self.current_user_id)

        self.assertIs(context.exception, self.forbidden)

    def test_remove_team_member_reraises_forbidden(self) -> None:
        self.mock_service.remove_member_from_project.side_effect = self.forbidden

        with self.assertRaises(AppException) as context:
            remove_team_member(self.project_id, uuid4(), self.mock_service, self.current_user_id)

        self.assertIs(context.exception, self.forbidden)


if __name__ == "__main__":
    unittest.main()
