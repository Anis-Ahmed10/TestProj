"""Tests for Pydantic schemas for project teams."""

from __future__ import annotations

import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.schemas.teams import AddTeamMembersPayload, TeamMemberResponse


class TeamsSchemaTests(unittest.TestCase):
    """Test validation and defaults of Teams schemas."""

    # -------------------------
    # AddTeamMembersPayload
    # -------------------------
    def test_add_team_members_payload_valid(self) -> None:
        uid1 = uuid4()
        uid2 = uuid4()

        payload = AddTeamMembersPayload(user_ids=[uid1, uid2])

        self.assertEqual(payload.user_ids, [uid1, uid2])

    def test_add_team_members_payload_invalid_type(self) -> None:
        # invalid UUID string
        with self.assertRaises(ValidationError):
            AddTeamMembersPayload(user_ids=["not-a-uuid"])

    def test_add_team_members_payload_empty_list(self) -> None:
        payload = AddTeamMembersPayload(user_ids=[])

        self.assertEqual(payload.user_ids, [])

    # -------------------------
    # TeamMemberResponse
    # -------------------------
    def test_team_member_response_valid(self) -> None:
        uid = uuid4()

        data = {
            "id": uid,
            "user_id": uid,
            "name": "John Doe",
            "email": "john@example.com",
        }

        response = TeamMemberResponse(**data)

        self.assertEqual(response.id, uid)
        self.assertEqual(response.user_id, uid)
        self.assertEqual(response.name, "John Doe")
        self.assertEqual(response.email, "john@example.com")

    def test_team_member_response_defaults(self) -> None:
        uid = uuid4()

        response = TeamMemberResponse(
            id=uid,
            user_id=uid,
            name="Jane Doe",
            email="jane@example.com",
        )

        self.assertEqual(response.role, "Team Member")
        self.assertEqual(response.hours_this_sprint, 0)
        self.assertEqual(response.status, "Active")

    def test_team_member_response_override_defaults(self) -> None:
        uid = uuid4()

        response = TeamMemberResponse(
            id=uid,
            user_id=uid,
            name="Jane Doe",
            email="jane@example.com",
            role="Admin",
            hours_this_sprint=10,
            status="Inactive",
        )

        self.assertEqual(response.role, "Admin")
        self.assertEqual(response.hours_this_sprint, 10)
        self.assertEqual(response.status, "Inactive")

    def test_team_member_response_missing_required_fields(self) -> None:
        with self.assertRaises(ValidationError):
            TeamMemberResponse(name="Missing fields")

    def test_team_member_response_from_attributes(self) -> None:
        # Simulate ORM object
        class FakeUser:
            def __init__(self):
                self.id = uuid4()
                self.user_id = uuid4()
                self.name = "ORM User"
                self.email = "orm@example.com"

        obj = FakeUser()

        response = TeamMemberResponse.model_validate(obj)

        self.assertEqual(response.name, "ORM User")
        self.assertEqual(response.email, "orm@example.com")


if __name__ == "__main__":
    unittest.main()
