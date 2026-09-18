"""Tests for project request and response schemas."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from pydantic import ValidationError

from app.schemas.projects import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
    _normalize_required_text,
)


class ProjectSchemaTests(unittest.TestCase):
    """Verify project schema validation and serialization."""

    def test_project_response_from_attributes(self) -> None:
        last_modified = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
        project = SimpleNamespace(
            id=501,
            programme_id=601,
            name="Migration",
            description="Migration workstream.",
            status="active",
            last_modified=last_modified,
        )
        response = ProjectResponse.model_validate(project)
        self.assertEqual(response.name, "Migration")
        self.assertEqual(response.description, "Migration workstream.")
        self.assertEqual(response.status, "active")

    def test_project_response_optional_fields_default_none(self) -> None:
        project = SimpleNamespace(
            id=501,
            programme_id=601,
            name="Migration",
            description=None,
            status=None,
            last_modified=None,
        )
        response = ProjectResponse.model_validate(project)
        self.assertIsNone(response.description)
        self.assertIsNone(response.status)
        self.assertIsNone(response.programme_name)
        self.assertIsNone(response.client_id)
        self.assertIsNone(response.client_name)

    # ── ProjectUpdateRequest ────────────────────────────────────────────────

    def test_update_request_accepts_partial_fields(self) -> None:
        req = ProjectUpdateRequest(name="New Name")
        self.assertEqual(req.name, "New Name")
        self.assertIsNone(req.description)
        self.assertIsNone(req.status)

    def test_update_request_allows_none_name(self) -> None:
        req = ProjectUpdateRequest(name=None)
        self.assertIsNone(req.name)

    def test_update_request_rejects_blank_name(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectUpdateRequest(name="   ")

    def test_update_request_rejects_name_too_long(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectUpdateRequest(name="x" * 256)

    def test_update_request_normalizes_name(self) -> None:
        req = ProjectUpdateRequest(name="  Trimmed  ")
        self.assertEqual(req.name, "Trimmed")

    def test_update_request_normalizes_description_to_none(self) -> None:
        req = ProjectUpdateRequest(description="   ")
        self.assertIsNone(req.description)

    def test_update_request_normalizes_description(self) -> None:
        req = ProjectUpdateRequest(description="  Some desc  ")
        self.assertEqual(req.description, "Some desc")

    def test_update_request_allows_none_description(self) -> None:
        req = ProjectUpdateRequest(description=None)
        self.assertIsNone(req.description)

    def test_update_request_accepts_valid_status(self) -> None:
        req = ProjectUpdateRequest(status="onhold")
        self.assertEqual(req.status, "onhold")

    def test_update_request_normalizes_status_case(self) -> None:
        req = ProjectUpdateRequest(status="ACTIVE")
        self.assertEqual(req.status, "active")

    def test_update_request_rejects_invalid_status(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectUpdateRequest(status="paused")

    def test_update_request_allows_none_status(self) -> None:
        req = ProjectUpdateRequest(status=None)
        self.assertIsNone(req.status)

    def test_update_request_all_fields(self) -> None:
        req = ProjectUpdateRequest(name="X", description="Desc", status="complete")
        self.assertEqual(req.name, "X")
        self.assertEqual(req.description, "Desc")
        self.assertEqual(req.status, "complete")

    # ── ProjectCreateRequest ────────────────────────────────────────────────

    def test_create_project_rejects_none_name(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ProjectCreateRequest(
                programme_id="11111111-1111-1111-1111-111111111111",
                name=None,
            )
        self.assertIn("Input should be a valid string", str(context.exception))

    def test_normalize_required_text_rejects_none(self) -> None:
        with self.assertRaises(ValueError) as context:
            _normalize_required_text(None, "project name")
        self.assertEqual(str(context.exception), "project name is required")

    def test_normalize_required_text_rejects_blank(self) -> None:
        with self.assertRaises(ValueError) as context:
            _normalize_required_text("   ", "project name")
        self.assertEqual(str(context.exception), "project name is required")

    def test_normalize_required_text_returns_value(self) -> None:
        result = _normalize_required_text("  valid  ", "project name")
        self.assertEqual(result, "valid")

    def test_create_project_rejects_blank_name(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ProjectCreateRequest(
                programme_id="11111111-1111-1111-1111-111111111111",
                name="   ",
            )
        self.assertIn("project name is required", str(context.exception))

    def test_create_project_normalizes_description_values(self) -> None:
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
            description="  Migration workstream  ",
        )
        self.assertEqual(payload.description, "Migration workstream")

    def test_create_project_normalizes_empty_description_to_none(self) -> None:
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
            description="   ",
        )
        self.assertIsNone(payload.description)

    def test_create_project_keeps_none_description(self) -> None:
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
            description=None,
        )
        self.assertIsNone(payload.description)

    def test_create_project_defaults_none_status_to_active(self) -> None:
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
            status=None,
        )
        self.assertEqual(payload.status, "active")

    def test_create_project_defaults_blank_status_to_active(self) -> None:
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
            status="   ",
        )
        self.assertEqual(payload.status, "active")

    def test_create_project_normalizes_valid_status(self) -> None:
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
            status="OnHold",
        )
        self.assertEqual(payload.status, "onhold")

    def test_create_project_normalizes_valid_complete_status(self) -> None:
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
            status="COMPLETE",
        )
        self.assertEqual(payload.status, "complete")

    def test_create_project_rejects_invalid_status(self) -> None:
        with self.assertRaises(ValidationError) as context:
            ProjectCreateRequest(
                programme_id="11111111-1111-1111-1111-111111111111",
                name="Migration",
                status="paused",
            )
        self.assertIn("status must be active, onhold, or complete", str(context.exception))
