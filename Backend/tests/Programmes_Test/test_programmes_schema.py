"""Tests for programme request and response schemas."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace

from pydantic import ValidationError

from app.schemas.programmes import (
    ProgrammeCreateRequest,
    ProgrammeDetailResponse,
    ProgrammeResponse,
    ProgrammeUpdateRequest,
    ProjectAssociationResponse,
    _normalize_required_text,
)


class ProgrammeSchemaTests(unittest.TestCase):
    """Verify programme schema serialization."""

    def test_programme_response_includes_all_fields(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        programme = SimpleNamespace(
            id=101,
            client_id=202,
            name="Modernisation",
            description="Claims modernisation programme.",
            status="active",
            created_at=ts,
            last_modified=ts,
        )

        response = ProgrammeResponse.model_validate(programme)

        self.assertEqual(response.name, "Modernisation")
        self.assertEqual(response.status, "active")
        self.assertEqual(response.description, "Claims modernisation programme.")
        self.assertEqual(response.created_at, ts)
        self.assertEqual(response.last_modified, ts)

    def test_programme_response_optional_fields_default_none(self) -> None:
        programme = SimpleNamespace(
            id=101,
            client_id=202,
            name="Modernisation",
            description=None,
            status=None,
            created_at=None,
            last_modified=None,
        )
        response = ProgrammeResponse.model_validate(programme)
        self.assertIsNone(response.description)
        self.assertIsNone(response.status)
        self.assertIsNone(response.created_at)
        self.assertIsNone(response.last_modified)

    def test_programme_detail_response_validation(self) -> None:
        data = {
            "id": "11111111-1111-1111-1111-111111111111",
            "client_id": "22222222-2222-2222-2222-222222222222",
            "name": "Full Detail",
            "status": "active",
            "projects": [
                {
                    "id": "33333333-3333-3333-3333-333333333333",
                    "name": "Sub Project",
                    "status": "active",
                }
            ],
        }
        response = ProgrammeDetailResponse.model_validate(data)
        self.assertEqual(response.name, "Full Detail")
        self.assertEqual(len(response.projects), 1)
        self.assertEqual(response.projects[0].name, "Sub Project")

    def test_programme_detail_response_includes_timestamps(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        data = {
            "id": 1,
            "client_id": 2,
            "name": "X",
            "status": "active",
            "projects": [],
            "created_at": ts,
            "last_modified": ts,
        }
        response = ProgrammeDetailResponse.model_validate(data)
        self.assertEqual(response.created_at, ts)
        self.assertEqual(response.last_modified, ts)

    def test_programme_detail_response_ignores_extra_fields(self) -> None:
        response = ProgrammeDetailResponse(
            id=1, client_id=1, name="X", status="active", projects=[]
        )
        self.assertEqual(response.name, "X")
        self.assertEqual(response.status, "active")
        self.assertEqual(response.projects, [])

    def test_project_association_response_defaults(self) -> None:
        data = {"id": 500, "name": "Simple Proj", "status": "onhold"}
        response = ProjectAssociationResponse.model_validate(data)
        self.assertEqual(response.status, "onhold")
        self.assertIsNone(response.description)
        self.assertIsNone(response.start_date)

    def test_project_association_response_includes_timestamps(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        data = {
            "id": 500,
            "name": "Simple Proj",
            "status": "active",
            "created_at": ts,
            "last_modified": ts,
        }
        response = ProjectAssociationResponse.model_validate(data)
        self.assertEqual(response.created_at, ts)
        self.assertEqual(response.last_modified, ts)

    def test_project_association_response_start_date(self) -> None:
        data = {"id": 500, "name": "Proj", "status": "active", "start_date": date(2026, 6, 1)}
        response = ProjectAssociationResponse.model_validate(data)
        self.assertEqual(response.start_date, date(2026, 6, 1))

    # ── ProgrammeUpdateRequest ──────────────────────────────────────────────

    def test_update_request_accepts_partial_fields(self) -> None:
        req = ProgrammeUpdateRequest(name="New Name")
        self.assertEqual(req.name, "New Name")
        self.assertIsNone(req.description)
        self.assertIsNone(req.status)

    def test_update_request_rejects_blank_name(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            ProgrammeUpdateRequest(name="   ")

    def test_update_request_allows_none_name(self) -> None:
        req = ProgrammeUpdateRequest(name=None)
        self.assertIsNone(req.name)

    def test_update_request_normalizes_name(self) -> None:
        req = ProgrammeUpdateRequest(name="  Trimmed  ")
        self.assertEqual(req.name, "Trimmed")

    def test_update_request_normalizes_description_to_none(self) -> None:
        req = ProgrammeUpdateRequest(description="   ")
        self.assertIsNone(req.description)

    def test_update_request_normalizes_description(self) -> None:
        req = ProgrammeUpdateRequest(description="  Some desc  ")
        self.assertEqual(req.description, "Some desc")

    def test_update_request_accepts_valid_status(self) -> None:
        req = ProgrammeUpdateRequest(status="active")
        self.assertEqual(req.status, "active")

    def test_update_request_normalizes_status_case(self) -> None:
        req = ProgrammeUpdateRequest(status="ACTIVE")
        self.assertEqual(req.status, "active")

    def test_update_request_rejects_invalid_status(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            ProgrammeUpdateRequest(status="unknown")

    def test_update_request_allows_none_status(self) -> None:
        req = ProgrammeUpdateRequest(status=None)
        self.assertIsNone(req.status)

    def test_update_request_rejects_archived_status(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            ProgrammeUpdateRequest(status="archived")

    # ── ProgrammeCreateRequest ──────────────────────────────────────────────

    def test_create_programme_rejects_none_name(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ProgrammeCreateRequest(
                client_id="11111111-1111-1111-1111-111111111111",
                name=None,
            )
        self.assertIn("Input should be a valid string", str(context.exception))

    def test_normalize_required_text_rejects_none(self) -> None:
        with self.assertRaises(ValueError) as context:
            _normalize_required_text(None, "programme name")
        self.assertEqual(str(context.exception), "programme name is required")

    def test_normalize_required_text_rejects_blank(self) -> None:
        with self.assertRaises(ValueError) as context:
            _normalize_required_text("   ", "programme name")
        self.assertEqual(str(context.exception), "programme name is required")

    def test_normalize_required_text_returns_value(self) -> None:
        result = _normalize_required_text("  valid  ", "programme name")
        self.assertEqual(result, "valid")

    def test_create_programme_rejects_blank_name(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ProgrammeCreateRequest(
                client_id="11111111-1111-1111-1111-111111111111",
                name="   ",
            )
        self.assertIn("programme name is required", str(context.exception))

    def test_create_programme_normalizes_description(self) -> None:
        payload = ProgrammeCreateRequest(
            client_id="11111111-1111-1111-1111-111111111111",
            name="Modernisation",
            description="  Claims programme  ",
        )
        self.assertEqual(payload.description, "Claims programme")

    def test_create_programme_normalizes_empty_description_to_none(self) -> None:
        payload = ProgrammeCreateRequest(
            client_id="11111111-1111-1111-1111-111111111111",
            name="Modernisation",
            description="   ",
        )
        self.assertIsNone(payload.description)

    def test_create_programme_keeps_none_description(self) -> None:
        payload = ProgrammeCreateRequest(
            client_id="11111111-1111-1111-1111-111111111111",
            name="Modernisation",
            description=None,
        )
        self.assertIsNone(payload.description)

    def test_update_request_keeps_none_description(self) -> None:
        req = ProgrammeUpdateRequest(description=None)
        self.assertIsNone(req.description)
