"""Tests for the client service layer."""

import unittest
from datetime import datetime, timezone
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, DatabaseOperationException
from app.schemas.clients import ClientCreateRequest, ClientListResponse
from app.services.clients import ClientService


def _make_client(**overrides):
    created_at = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    last_modified = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
    base = {
        "id": 7,
        "name": "Acme Corp",
        "industry": "Technology",
        "location": "Pune",
        "contact": "qa@acme.example",
        "status": "active",
        "manager_id": uuid4(),
        "manager_name": "Test Manager",
        "programmes_count": 2,
        "projects_count": 4,
        "active_members_count": 6,
        "created_at": created_at,
        "last_modified": last_modified,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class ClientServiceTests(unittest.TestCase):
    """Verify business rules for client operations."""

    def setUp(self) -> None:
        self.db = SimpleNamespace(rollback=Mock())
        self.service = ClientService(self.db)
        self.current_user_id = uuid4()

        self._visible_client_ids_patcher = patch(
            "app.services.clients.get_visible_client_ids", return_value=None
        )
        self._visible_client_ids_patcher.start()
        self.addCleanup(self._visible_client_ids_patcher.stop)

        self._visible_counts_patcher = patch(
            "app.services.clients.get_visible_counts_by_client", return_value=None
        )
        self._visible_counts_patcher.start()
        self.addCleanup(self._visible_counts_patcher.stop)

    def test_constructor_stores_db(self) -> None:
        db = SimpleNamespace()
        service = ClientService(db)

        self.assertIs(service.db, db)

    def test_create_client_rejects_duplicates(self) -> None:
        manager_id = UUID("6e522a00-7199-4575-8da6-80eb789727e5")
        payload = ClientCreateRequest(
            name="Acme Corp",
            industry="Technology",
            location="Pune",
            contact="qa@acme.example",
        )

        with patch("app.services.clients.get_client_by_name", return_value=_make_client()):
            with patch("app.services.clients.create_client_entry") as create_entry:
                with self.assertRaises(AppException) as context:
                    self.service.create_client(self.db, payload, manager_id=manager_id)

        self.assertEqual(context.exception.code, "CLIENT_ALREADY_EXISTS")
        self.assertEqual(context.exception.status_code, HTTPStatus.CONFLICT)
        create_entry.assert_not_called()

    @patch(
        "app.services.clients.get_user_by_id",
        return_value=SimpleNamespace(
            id="6e522a00-7199-4575-8da6-80eb789727e5",
            name="Test Manager",
        ),
    )
    @patch("app.services.clients.get_client_by_name", return_value=None)
    @patch("app.services.clients.create_client_entry")
    def test_create_client_returns_response(
        self,
        mock_create_client_entry,
        mock_get_client_by_name,
        mock_get_user_by_id,
    ) -> None:
        manager_id = uuid4()
        payload = ClientCreateRequest(
            name="  Acme Corp  ",
            industry="  Technology  ",
            location="  Pune  ",
            contact="  qa@acme.example  ",
        )
        created_client = _make_client(id=12, programmes_count=0, projects_count=0)
        mock_create_client_entry.return_value = created_client

        response = self.service.create_client(self.db, payload, manager_id=manager_id)

        self.assertEqual(response.name, "Acme Corp")
        mock_create_client_entry.assert_called_once()
        mock_get_user_by_id.assert_called_once_with(self.db, manager_id)

    def test_create_client_rolls_back_on_integrity_error(self) -> None:
        manager_id = uuid4()
        payload = ClientCreateRequest(
            name="Acme Corp",
            industry="Technology",
            location="Pune",
            contact="qa@acme.example",
        )

        with patch("app.services.clients.get_client_by_name", return_value=None):
            with patch(
                "app.services.clients.create_client_entry",
                side_effect=IntegrityError("insert", {}, Exception("duplicate")),
            ):
                with self.assertRaises(AppException) as context:
                    self.service.create_client(self.db, payload, manager_id=manager_id)

        self.db.rollback.assert_called_once()
        self.assertEqual(context.exception.code, "CLIENT_ALREADY_EXISTS")
        self.assertEqual(context.exception.status_code, HTTPStatus.CONFLICT)

    def test_list_clients_returns_list_response(self) -> None:
        clients = [
            _make_client(id=1, name="Acme One", programmes_count=1, projects_count=2),
            _make_client(id=2, name="Acme Two", programmes_count=0, projects_count=0),
        ]

        with patch(
            "app.services.clients.list_client_entries", return_value=clients
        ) as list_entries:
            response = self.service.list_clients(self.db, self.current_user_id)

        self.assertIsInstance(response, ClientListResponse)
        self.assertEqual(response.total, 2)
        self.assertEqual(response.items[0].name, "Acme One")
        list_entries.assert_called_once_with(self.db)

    def test_list_clients_wraps_database_operation_error(self) -> None:
        with patch(
            "app.services.clients.list_client_entries",
            side_effect=DatabaseOperationException("boom"),
        ):
            with self.assertRaises(AppException) as context:
                self.service.list_clients(self.db, self.current_user_id)

        self.assertEqual(context.exception.code, "CLIENT_LIST_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    def test_list_clients_filters_by_visible_ids(self) -> None:
        visible_client = _make_client(id=1, name="Acme One")
        hidden_client = _make_client(id=2, name="Acme Two")

        with (
            patch(
                "app.services.clients.list_client_entries",
                return_value=[visible_client, hidden_client],
            ),
            patch("app.services.clients.get_visible_client_ids", return_value={visible_client.id}),
        ):
            response = self.service.list_clients(self.db, self.current_user_id)

        self.assertEqual(response.total, 1)
        self.assertEqual(response.items[0].name, "Acme One")

    def test_list_clients_overrides_counts_with_scoped_counts(self) -> None:
        client = _make_client(id=1, name="Acme One", programmes_count=99, projects_count=99)

        with (
            patch("app.services.clients.list_client_entries", return_value=[client]),
            patch("app.services.clients.get_visible_client_ids", return_value=None),
            patch(
                "app.services.clients.get_visible_counts_by_client",
                return_value={
                    client.id: {
                        "programmes_count": 1,
                        "projects_count": 2,
                        "active_members_count": 3,
                    }
                },
            ),
        ):
            response = self.service.list_clients(self.db, self.current_user_id)

        item = response.items[0]
        self.assertEqual(item.programmes_count, 1)
        self.assertEqual(item.projects_count, 2)
        self.assertEqual(item.active_members_count, 3)


class ClientSchemaTests(unittest.TestCase):
    """Verify client schema field validators."""

    def test_client_update_coerce_empty_manager_id_to_none(self) -> None:
        from app.schemas.clients import ClientUpdate

        req_empty = ClientUpdate(manager_id="")
        self.assertIsNone(req_empty.manager_id)

        req_null = ClientUpdate(manager_id="null")
        self.assertIsNone(req_null.manager_id)

        req_none = ClientUpdate(manager_id=None)
        self.assertIsNone(req_none.manager_id)

        valid_uuid = uuid4()
        req_uuid = ClientUpdate(manager_id=valid_uuid)
        self.assertEqual(req_uuid.manager_id, valid_uuid)
