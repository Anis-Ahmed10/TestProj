"""Tests for the shared client-name resolution helpers used by audit logging."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.models.clients_models import Client
from app.models.project_models import Project
from app.utils.audit_context import (
    client_name_for_client_id,
    client_name_for_programme_id,
    client_name_for_project_id,
)

_CLIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
_PROGRAMME_ID = UUID("22222222-2222-2222-2222-222222222222")
_PROJECT_ID = UUID("33333333-3333-3333-3333-333333333333")
_NOW = datetime(2026, 7, 6, 10, 30, tzinfo=timezone.utc)


class _FakeMappingsResult:
    def __init__(self, row=None) -> None:
        self._row = row

    def first(self):
        return self._row


class _FakeExecuteResult:
    def __init__(self, row=None) -> None:
        self._row = row

    def mappings(self):
        return _FakeMappingsResult(self._row)


class _FakeDb:
    """Fakes `.get()` for ORM identity lookups (Client/Project) and
    `.execute()` for the raw-SQL programme lookup."""

    def __init__(
        self,
        client: Client | None = None,
        programme_row: dict | None = None,
        project: Project | None = None,
    ) -> None:
        self._client = client
        self._programme_row = programme_row
        self._project = project

    def get(self, model, entity_id):
        if model is Client and entity_id == _CLIENT_ID:
            return self._client
        if model is Project and entity_id == _PROJECT_ID:
            return self._project
        return None

    def execute(self, _query, _params):
        return _FakeExecuteResult(self._programme_row)


def _make_client(**overrides) -> Client:
    base = {
        "id": _CLIENT_ID,
        "name": "Acme Corp",
        "industry": "Technology",
        "location": "Pune",
        "contact": "qa@acme.example",
        "status": "active",
    }
    base.update(overrides)
    return Client(**base)


def _make_programme_row(**overrides) -> dict:
    base = {
        "id": _PROGRAMME_ID,
        "client_id": _CLIENT_ID,
        "name": "Modernisation",
        "description": None,
        "status": "active",
        "created_at": _NOW,
        "last_modified": _NOW,
    }
    base.update(overrides)
    return base


def _make_project(**overrides) -> Project:
    base = {
        "id": _PROJECT_ID,
        "programme_id": _PROGRAMME_ID,
        "name": "Migration",
        "description": None,
        "status": "active",
        "start_date": None,
        "created_at": _NOW,
        "last_modified": _NOW,
    }
    base.update(overrides)
    return Project(**base)


class TestClientNameForClientId:
    def test_returns_client_name(self) -> None:
        db = _FakeDb(client=_make_client())
        assert client_name_for_client_id(db, _CLIENT_ID) == "Acme Corp"

    def test_returns_none_when_client_id_missing(self) -> None:
        db = _FakeDb()
        assert client_name_for_client_id(db, None) is None

    def test_returns_none_when_client_not_found(self) -> None:
        db = _FakeDb(client=None)
        assert client_name_for_client_id(db, _CLIENT_ID) is None

    def test_returns_none_when_client_archived(self) -> None:
        db = _FakeDb(client=_make_client(status="archived"))
        assert client_name_for_client_id(db, _CLIENT_ID) is None


class TestClientNameForProgrammeId:
    def test_resolves_client_name_via_programme(self) -> None:
        db = _FakeDb(client=_make_client(), programme_row=_make_programme_row())
        assert client_name_for_programme_id(db, _PROGRAMME_ID) == "Acme Corp"

    def test_returns_none_when_programme_id_missing(self) -> None:
        db = _FakeDb()
        assert client_name_for_programme_id(db, None) is None

    def test_returns_none_when_programme_not_found(self) -> None:
        db = _FakeDb(client=_make_client(), programme_row=None)
        assert client_name_for_programme_id(db, _PROGRAMME_ID) is None


class TestClientNameForProjectId:
    def test_resolves_client_name_via_project_and_programme(self) -> None:
        db = _FakeDb(
            client=_make_client(),
            programme_row=_make_programme_row(),
            project=_make_project(),
        )
        assert client_name_for_project_id(db, _PROJECT_ID) == "Acme Corp"

    def test_returns_none_when_project_id_missing(self) -> None:
        db = _FakeDb()
        assert client_name_for_project_id(db, None) is None

    def test_returns_none_when_project_not_found(self) -> None:
        db = _FakeDb(project=None)
        assert client_name_for_project_id(db, _PROJECT_ID) is None
