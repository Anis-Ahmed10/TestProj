"""Integration test: the create_programme endpoint logs the client name."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from app.api.v1.endpoints.programmes import create_programme
from app.models.clients_models import Client
from app.schemas.programmes import ProgrammeCreateRequest

_CLIENT_ID = UUID("11111111-1111-1111-1111-111111111111")


class _FakeDb:
    def __init__(self, client: Client) -> None:
        self._client = client

    def get(self, model, entity_id):
        if model is Client and entity_id == _CLIENT_ID:
            return self._client
        return None


def test_create_programme_logs_client_name() -> None:
    client = Client(
        id=_CLIENT_ID,
        name="Acme Corp",
        industry="Technology",
        location="Pune",
        contact="qa@acme.example",
        status="active",
    )
    db = _FakeDb(client)
    service = SimpleNamespace(db=db, create_programme=Mock(return_value=Mock()))
    payload = ProgrammeCreateRequest(client_id=_CLIENT_ID, name="Modernisation")

    with patch("app.utils.audit_log.create_log_entry") as mock_create_log:
        create_programme(payload, service, uuid.UUID("00000000-0000-0000-0000-000000000001"))

    assert mock_create_log.call_args.kwargs["client_name"] == "Acme Corp"
