"""Unit tests for TeamsService."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.core.exceptions import AppException
from app.services.teams import TeamsService


class TeamsServiceTests(unittest.TestCase):
    """Test business logic for TeamsService."""

    def setUp(self) -> None:
        self.db = MagicMock()
        self.service = TeamsService(self.db)
        self.project_id = uuid4()
        self.user_id = uuid4()
        self.current_user_id = uuid4()

    # -------------------------
    # Access Visibility Guard
    # -------------------------
    @patch("app.services.teams.get_visible_project_ids")
    def test_ensure_project_visible_forbidden_raises_app_exception(self, mock_get_visible):
        mock_get_visible.return_value = {uuid4()}

        with self.assertRaises(AppException) as ctx:
            self.service.get_project_team_members(self.project_id, self.current_user_id)

        self.assertEqual(ctx.exception.code, "FORBIDDEN")
        self.assertEqual(ctx.exception.status_code, 403)

    # -------------------------
    # get_project_team_members
    # -------------------------
    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    @patch("app.services.teams.get_team_members_by_project")
    def test_get_project_team_members_success(self, mock_get_members, mock_get_visible):
        fake_user = SimpleNamespace(
            id=self.user_id,
            email="john@example.com",
            full_name="John Doe",
            is_active=True,
            role="Developer",
        )

        fake_pu = MagicMock()
        fake_pu.hours_this_sprint = 5
        fake_pu.status = "Active"

        mock_get_members.return_value = [(fake_user, fake_pu)]

        result = self.service.get_project_team_members(self.project_id, self.current_user_id)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "John Doe")
        self.assertEqual(result[0].hours_this_sprint, 5)
        mock_get_visible.assert_called_once_with(self.db, self.current_user_id)

    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    @patch("app.services.teams.get_team_members_by_project")
    def test_get_project_team_members_exception(self, mock_get_members, mock_get_visible):
        mock_get_members.side_effect = Exception("DB error")

        with self.assertRaises(AppException) as ctx:
            self.service.get_project_team_members(self.project_id, self.current_user_id)

        self.assertEqual(ctx.exception.code, "TEAM_MEMBERS_FETCH_FAILED")

    # -------------------------
    # get_available_users
    # -------------------------
    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    @patch("app.services.teams.get_available_users_for_project")
    def test_get_available_users_success(self, mock_get_users, mock_get_visible):
        fake_user = SimpleNamespace(
            id=self.user_id, name="Jane Doe", email="jane@example.com", role="Developer"
        )

        mock_get_users.return_value = [fake_user]

        result = self.service.get_available_users(self.project_id, self.current_user_id)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Jane Doe")

    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    @patch("app.services.teams.get_available_users_for_project")
    def test_get_available_users_exception(self, mock_get_users, mock_get_visible):
        mock_get_users.side_effect = Exception("DB error")

        with self.assertRaises(AppException) as ctx:
            self.service.get_available_users(self.project_id, self.current_user_id)

        self.assertEqual(ctx.exception.code, "TEAMS_AVAILABLE_USERS_FAILED")

    # -------------------------
    # add_members_to_project
    # -------------------------
    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    @patch("app.services.teams.get_team_members_by_project", return_value=[])
    @patch.object(TeamsService, "get_project_team_members")
    def test_add_members_success(self, mock_get_members, mock_current_team, mock_get_visible):
        mock_get_members.return_value = ["mocked-response"]

        result = self.service.add_members_to_project(
            self.project_id, [self.user_id], self.current_user_id
        )

        mock_current_team.assert_called_once_with(self.db, self.project_id)
        self.assertEqual(result, ["mocked-response"])
        mock_get_members.assert_called_once_with(self.project_id, self.current_user_id)

    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    def test_add_members_empty_list(self, mock_get_visible):
        result = self.service.add_members_to_project(self.project_id, [], self.current_user_id)

        self.assertEqual(result, [])
        self.db.execute.assert_not_called()
        self.db.commit.assert_not_called()

    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    def test_add_members_ignores_existing_members_not_in_request(self, mock_get_visible) -> None:
        unrelated_member = SimpleNamespace(id=uuid4(), name="Someone Else")
        with (
            patch(
                "app.services.teams.get_team_members_by_project",
                return_value=[(unrelated_member, MagicMock())],
            ),
            patch.object(TeamsService, "get_project_team_members", return_value=["ok"]),
        ):
            result = self.service.add_members_to_project(
                self.project_id, [self.user_id], self.current_user_id
            )

        self.assertEqual(result, ["ok"])
        self.db.commit.assert_called_once()

    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    def test_add_members_exception(self, mock_get_visible):
        self.db.execute.side_effect = Exception("Insert failed")

        with self.assertRaises(AppException) as ctx:
            self.service.add_members_to_project(
                self.project_id, [self.user_id], self.current_user_id
            )

        self.db.rollback.assert_called_once()
        self.assertEqual(ctx.exception.code, "TEAM_MEMBERS_ADD_FAILED")

    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    def test_add_members_fully_overlapping_selection_is_idempotent_noop(
        self, mock_get_visible
    ) -> None:
        """Reopening 'Add Member' with existing selections still ticked, and
        no new person added, must succeed as a no-op — not fail the request."""
        existing_user = SimpleNamespace(id=self.user_id, name="Jane Doe")
        with (
            patch(
                "app.services.teams.get_team_members_by_project",
                return_value=[(existing_user, MagicMock())],
            ),
            patch.object(TeamsService, "get_project_team_members", return_value=["current-team"]),
        ):
            result = self.service.add_members_to_project(
                self.project_id, [self.user_id], self.current_user_id
            )

        self.assertEqual(result, ["current-team"])
        self.db.execute.assert_not_called()
        self.db.commit.assert_not_called()

    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    def test_add_members_does_not_reject_when_one_of_several_already_exists(
        self, mock_get_visible
    ) -> None:
        """Regression test: previously, requesting [existing, new] raised a
        409 and silently dropped the new member. Now it must add only the
        new member and return successfully."""
        already_on_team_id = uuid4()
        new_user_id = uuid4()
        existing_user = SimpleNamespace(id=already_on_team_id, name="Existing Person")

        with (
            patch(
                "app.services.teams.get_team_members_by_project",
                return_value=[(existing_user, MagicMock())],
            ),
            patch.object(
                TeamsService, "get_project_team_members", return_value=["team-with-new-member"]
            ),
        ):
            result = self.service.add_members_to_project(
                self.project_id, [already_on_team_id, new_user_id], self.current_user_id
            )

        self.assertEqual(result, ["team-with-new-member"])
        self.db.commit.assert_called_once()

    # -------------------------
    # remove_member_from_project
    # -------------------------
    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    @patch("app.services.teams.remove_member_from_project")
    def test_remove_member_success(self, mock_remove, mock_get_visible):
        mock_remove.return_value = "John Doe"

        result = self.service.remove_member_from_project(
            self.project_id, self.user_id, self.current_user_id
        )

        self.db.commit.assert_called_once()
        self.assertEqual(result, {"name": "John Doe"})

    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    @patch("app.services.teams.remove_member_from_project")
    def test_remove_member_exception(self, mock_remove, mock_get_visible):
        mock_remove.side_effect = Exception("Delete failed")

        with self.assertRaises(AppException) as ctx:
            self.service.remove_member_from_project(
                self.project_id, self.user_id, self.current_user_id
            )

        self.db.rollback.assert_called_once()
        self.assertEqual(ctx.exception.code, "TEAM_MEMBER_REMOVE_FAILED")

    @patch("app.services.teams.get_visible_project_ids", return_value=None)
    @patch("app.services.teams.remove_member_from_project")
    def test_remove_member_not_found_raises_resource_not_found(
        self, mock_remove, mock_get_visible
    ):
        from app.core.exceptions import ResourceNotFoundError

        mock_remove.return_value = None

        with self.assertRaises(ResourceNotFoundError):
            self.service.remove_member_from_project(
                self.project_id, self.user_id, self.current_user_id
            )

        self.db.rollback.assert_called_once()

    @patch("app.services.teams.get_visible_project_ids")
    def test_remove_member_forbidden_raises_app_exception(self, mock_get_visible):
        mock_get_visible.return_value = {uuid4()}  # self.project_id not in this set

        with self.assertRaises(AppException) as ctx:
            self.service.remove_member_from_project(
                self.project_id, self.user_id, self.current_user_id
            )

        self.assertEqual(ctx.exception.code, "FORBIDDEN")
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
