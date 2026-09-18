"""Integration test: the create_project endpoint logs the client name."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from app.api.v1.endpoints.projects import create_project
from app.models.clients_models import Client
from app.schemas.projects import ProjectCreateRequest

_CLIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
_PROGRAMME_ID = UUID("22222222-2222-2222-2222-222222222222")
_NOW = datetime(2026, 7, 6, 10, 30, tzinfo=timezone.utc)


class _FakeMappingsResult:
    def __init__(self, row) -> None:
        self._row = row

    def first(self):
        return self._row


class _FakeExecuteResult:
    def __init__(self, row) -> None:
        self._row = row

    def mappings(self):
        return _FakeMappingsResult(self._row)


class _FakeDb:
    def __init__(self, client: Client, programme_row: dict) -> None:
        self._client = client
        self._programme_row = programme_row

    def get(self, model, entity_id):
        if model is Client and entity_id == _CLIENT_ID:
            return self._client
        return None

    def execute(self, _query, _params):
        return _FakeExecuteResult(self._programme_row)


def test_create_project_logs_client_name() -> None:
    client = Client(
        id=_CLIENT_ID,
        name="Acme Corp",
        industry="Technology",
        location="Pune",
        contact="qa@acme.example",
        status="active",
    )
    programme_row = {
        "id": _PROGRAMME_ID,
        "client_id": _CLIENT_ID,
        "name": "Modernisation",
        "description": None,
        "status": "active",
        "created_at": _NOW,
        "last_modified": _NOW,
    }
    db = _FakeDb(client, programme_row)
    service = SimpleNamespace(db=db, create_project=Mock(return_value=Mock()))
    payload = ProjectCreateRequest(programme_id=_PROGRAMME_ID, name="Migration")

    with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
        create_project(payload, service, uuid.UUID("00000000-0000-0000-0000-000000000001"))

    assert mock_create_log.call_args.kwargs["client_name"] == "Acme Corp"
