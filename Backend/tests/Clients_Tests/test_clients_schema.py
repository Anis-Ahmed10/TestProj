"""Tests for client request and response schemas."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from pydantic import ValidationError

from app.schemas.clients import (
    ClientCreateRequest,
    ClientListResponse,
    ClientResponse,
    ClientUpdate,
    _strip_and_validate,
)


class ClientSchemaTests(unittest.TestCase):
    """Verify client schema validation and normalization."""

    def test_strip_and_validate_normalizes_text(self) -> None:
        self.assertEqual(_strip_and_validate("  Acme  ", "name"), "Acme")

    def test_strip_and_validate_rejects_blank_values(self) -> None:
        with self.assertRaises(ValueError):
            _strip_and_validate("   ", "name")

    def test_strip_and_validate_rejects_none(self) -> None:
        with self.assertRaises(ValueError):
            _strip_and_validate(None, "name")

    def test_client_create_request_strips_and_accepts_aliases(self) -> None:
        request = ClientCreateRequest(
            name="  Acme Corp  ",
            industry="  Technology  ",
            location="  Pune  ",
            primaryContact="  qa@acme.example  ",
        )

        self.assertEqual(request.name, "Acme Corp")
        self.assertEqual(request.industry, "Technology")
        self.assertEqual(request.location, "Pune")
        self.assertEqual(request.contact, "qa@acme.example")

    def test_client_create_request_rejects_blank_values(self) -> None:
        with self.assertRaises(ValidationError):
            ClientCreateRequest(
                name="",
                industry="Technology",
                location="Pune",
                contact="qa@acme.example",
            )

    def test_client_update_request_accepts_partial_fields(self) -> None:
        request = ClientUpdate.model_validate({"name": "New Name"})
        self.assertEqual(request.name, "New Name")
        self.assertIsNone(request.industry)
        self.assertIsNone(request.location)

        # Dump should only contain 'name' when exclude_unset=True
        dumped = request.model_dump(exclude_unset=True)
        self.assertIn("name", dumped)
        self.assertNotIn("industry", dumped)

    def test_client_update_rejects_explicit_null_and_blank(self) -> None:
        with self.assertRaises(ValidationError):
            ClientUpdate.model_validate({"name": None})

        with self.assertRaises(ValidationError):
            ClientUpdate.model_validate({"industry": "   "})

    def test_client_response_and_list_response_validate_from_attributes(self) -> None:
        created_at = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
        last_modified = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
        client = SimpleNamespace(
            id=12,
            name="Acme Corp",
            industry="Technology",
            location="Pune",
            contact="qa@acme.example",
            status="active",
            programmes_count=3,
            projects_count=5,
            created_at=created_at,
            active_members_count=9,
            last_modified=last_modified,
        )

        response = ClientResponse.model_validate(client)
        list_response = ClientListResponse(items=[response], total=1)

        self.assertEqual(response.contact, "qa@acme.example")
        self.assertEqual(response.programmes_count, 3)
        self.assertEqual(response.projects_count, 5)
        self.assertEqual(response.active_members_count, 9)
        self.assertEqual(list_response.total, 1)
