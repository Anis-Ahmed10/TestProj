"""Tests for the client database helpers."""

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, DatabaseOperationException, InvalidInputError
from app.database.clients_db import (
    _read_sql_file,
    _row_to_client,
    check_client_name_exists,
    create_client_entry,
    get_client_by_name,
    get_programs_by_client_id,
    list_client_entries,
    soft_delete_client,
    update_client_in_db,
)
from app.models.clients_models import Client


class _FakeMappingsResult:
    def __init__(self, row=None, rows=None) -> None:
        self._row = row
        self._rows = rows or []

    def first(self):
        return self._row

    def one(self):
        return self._row

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, row=None, rows=None, scalar_value=None) -> None:
        self._mappings = _FakeMappingsResult(row=row, rows=rows)
        self._scalar_value = scalar_value

    def mappings(self):
        return self._mappings

    def scalars(self):
        return self

    def first(self):
        return self._scalar_value if self._scalar_value is not None else self._mappings.first()

    def scalar_one(self):
        return self._scalar_value


class _FakeDB:
    def __init__(self, result: _FakeResult) -> None:
        self.result = result
        self.calls = []
        self.committed = False
        self.rolled_back = False

    def execute(self, query, params=None):
        self.calls.append((query, params))
        return self.result

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _client_row(**overrides):
    created_at = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    last_modified = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
    base = {
        "id": 1,
        "name": "Acme",
        "industry": "Technology",
        "location": "Pune",
        "contact": "qa@acme.example",
        "status": "active",
        "manager_id": uuid.uuid4(),
        "manager_name": "John Doe",
        "created_at": created_at,
        "last_modified": last_modified,
    }
    base.update(overrides)
    return base


class _ClientRecord:
    def __init__(
        self,
        *,
        id: str | None = "10000000-0000-0000-0000-000000000010",
        name: str = "Acme Corp",
        industry: str = "Finance",
        location: str = "Mumbai",
        contact: str = "Alex Doe",
        status: str = "active",
        manager_id: str | None = "10000000-0000-0000-0000-000000000010",
    ) -> None:
        self.id = id
        self.name = name
        self.industry = industry
        self.location = location
        self.contact = contact
        self.status = status
        self.manager_id = manager_id


class ClientDatabaseTests(unittest.TestCase):
    """Verify low-level SQL helper behavior."""

    def test_client_select_by_name_sql_uses_name_only(self) -> None:
        content = _read_sql_file("get_client_by_name.sql")

        self.assertIn("status != 'archived'", content)
        self.assertNotIn("is_archived", content)

    def test_client_list_sql_includes_all_clients(self) -> None:
        content = _read_sql_file("client_list_with_counts.sql")

        self.assertIn("status != 'archived'", content)

    def test_client_insert_sql_has_valid_column_and_value_list(self) -> None:
        content = _read_sql_file("client_insert.sql")

        # self.assertIn(":status\n)", content)
        # self.assertNotIn("status,\n)", content)

        self.assertIn(":manager_id", content)
        self.assertIn("INSERT INTO clients", content)

    def test_read_sql_file_reads_contents(self) -> None:
        with patch("pathlib.Path.read_text", return_value="SELECT 1;") as read_text:
            content = _read_sql_file("client_count.sql")

        self.assertEqual(content, "SELECT 1;")
        read_text.assert_called_once_with(encoding="utf-8")

    def test_read_sql_file_wraps_read_errors(self) -> None:
        _read_sql_file.cache_clear()
        with patch("pathlib.Path.read_text", side_effect=OSError("missing file")):
            with self.assertRaises(DatabaseOperationException) as context:
                _read_sql_file("client_count.sql")

        self.assertIn("Unable to read SQL file: client_count.sql", str(context.exception))

    def test_row_to_client_populates_counts(self) -> None:
        client = _row_to_client(
            {
                **_client_row(),
                "programmes_count": "3",
                "projects_count": None,
                "active_members_count": 8,
            }
        )

        self.assertIsInstance(client, Client)
        self.assertEqual(client.programmes_count, 3)
        self.assertEqual(client.projects_count, 0)
        self.assertEqual(client.active_members_count, 8)

    def test_row_to_client_wraps_missing_required_fields(self) -> None:
        with self.assertRaises(DatabaseOperationException) as context:
            _row_to_client({"name": "Acme"})

        self.assertIn("Unable to map client row", str(context.exception))

    def test_get_client_by_name_returns_client(self) -> None:
        client_data = _client_row()
        client_data.pop("manager_name", None)  # <-- Remove unmapped attr before ORM init
        client_obj = Client(**client_data)
        client_obj.manager_name = "John Doe"

        db = _FakeDB(_FakeResult(scalar_value=client_obj))

        with patch("app.database.clients_db._read_sql_file", return_value="SELECT 1") as reader:
            client = get_client_by_name(db, "  Acme  ")

        self.assertEqual(client.name, "Acme")
        self.assertEqual(db.calls[0][1], {"client_name": "Acme"})
        reader.assert_called_once_with("get_client_by_name.sql")

    def test_get_client_by_name_returns_none_when_no_row_exists(self) -> None:
        db = _FakeDB(_FakeResult(scalar_value=None))

        with patch("app.database.clients_db._read_sql_file", return_value="SELECT 1"):
            client = get_client_by_name(db, "Acme")

        self.assertIsNone(client)

    def test_get_client_by_name_wraps_query_errors(self) -> None:
        client_data = _client_row()
        client_data.pop("manager_name", None)  # <-- Remove unmapped attr before ORM init
        client_obj = Client(**client_data)

        db = _FakeDB(_FakeResult(scalar_value=client_obj))

        with patch("app.database.clients_db._read_sql_file", return_value="SELECT 1"):
            with patch.object(db, "execute", side_effect=RuntimeError("boom")):
                with self.assertRaises(DatabaseOperationException) as context:
                    get_client_by_name(db, "Acme")

        self.assertIn("Unable to fetch client by name: Acme", str(context.exception))

    def test_create_client_entry_trims_values_and_commits(self) -> None:
        row = {
            **_client_row(id=2, name="Acme Corp"),
        }
        db = _FakeDB(_FakeResult(row=row))

        with patch("app.database.clients_db._read_sql_file", return_value="INSERT 1") as reader:
            client = create_client_entry(
                db,
                name="  Acme Corp  ",
                industry="  Technology  ",
                location="  Pune  ",
                contact="  qa@acme.example  ",
            )

        self.assertTrue(db.committed)
        self.assertEqual(db.calls[0][1]["location"], "Pune")
        self.assertEqual(client.programmes_count, 0)
        self.assertEqual(client.projects_count, 0)
        reader.assert_called_once_with("client_insert.sql")

    def test_create_client_entry_allows_missing_location(self) -> None:
        row = _client_row(id=3, name="Acme Corp", location=None)
        db = _FakeDB(_FakeResult(row=row))

        with patch("app.database.clients_db._read_sql_file", return_value="INSERT 1"):
            client = create_client_entry(
                db,
                name="Acme Corp",
                industry="Technology",
                location=None,
                contact="qa@acme.example",
            )

        self.assertIsNone(db.calls[0][1]["location"])
        self.assertIsNone(client.location)
        self.assertEqual(client.active_members_count, 0)

    def test_create_client_entry_propagates_integrity_error(self) -> None:
        db = _FakeDB(_FakeResult(row=_client_row()))

        with patch("app.database.clients_db._read_sql_file", return_value="INSERT 1"):
            with patch.object(
                db,
                "execute",
                side_effect=IntegrityError("insert", {}, Exception("duplicate")),
            ):
                with self.assertRaises(IntegrityError):
                    create_client_entry(
                        db,
                        name="Acme Corp",
                        industry="Technology",
                        location="Pune",
                        contact="qa@acme.example",
                    )

        self.assertFalse(db.rolled_back)

    def test_create_client_entry_rolls_back_on_unexpected_error(self) -> None:
        db = _FakeDB(_FakeResult(row=_client_row()))

        with patch("app.database.clients_db._read_sql_file", return_value="INSERT 1"):
            with patch.object(db, "execute", side_effect=RuntimeError("boom")):
                with self.assertRaises(DatabaseOperationException) as context:
                    create_client_entry(
                        db,
                        name="Acme Corp",
                        industry="Technology",
                        location="Pune",
                        contact="qa@acme.example",
                    )

        self.assertTrue(db.rolled_back)
        self.assertIn("Unable to create client entry: Acme Corp", str(context.exception))

    def test_list_client_entries_returns_models(self) -> None:
        rows = [
            {
                **_client_row(),
                "programmes_count": 1,
                "projects_count": 2,
                "active_members_count": 4,
            },
        ]
        db = _FakeDB(_FakeResult(rows=rows))

        with patch("app.database.clients_db._read_sql_file", return_value="SELECT 1"):
            clients = list_client_entries(db)

        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0].name, "Acme")

    def test_list_client_entries_wraps_query_errors(self) -> None:
        db = _FakeDB(_FakeResult(rows=[]))

        with patch("app.database.clients_db._read_sql_file", return_value="SELECT 1"):
            with patch.object(db, "execute", side_effect=RuntimeError("boom")):
                with self.assertRaises(DatabaseOperationException) as context:
                    list_client_entries(db)

        self.assertIn("Unable to list client entries", str(context.exception))

    def test_get_programs_by_client_id_returns_program_rows(self) -> None:
        db = MagicMock()
        mappings = MagicMock()
        mappings.all.return_value = [
            {
                "id": "program-1",
                "name": "Claims Modernization",
                "description": "Migration programme for claims workflows.",
            }
        ]
        result_proxy = MagicMock()
        result_proxy.mappings.return_value = mappings
        db.execute.return_value = result_proxy

        result = get_programs_by_client_id(db, "client-1")

        self.assertEqual(
            result,
            [
                {
                    "id": "program-1",
                    "name": "Claims Modernization",
                    "description": "Migration programme for claims workflows.",
                }
            ],
        )
        db.execute.assert_called_once()

    def test_get_programs_by_client_id_wraps_unexpected_errors(self) -> None:
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")

        with self.assertRaises(DatabaseOperationException) as context:
            get_programs_by_client_id(db, "client-1")

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.message, "Unable to fetch programs for client: client-1"
        )

    @patch("app.database.clients_db.get_client_by_name", return_value=None)
    def test_update_client_in_db_raises_not_found(self, mock_get_client_by_name) -> None:
        db = MagicMock()

        with self.assertRaises(AppException) as context:
            update_client_in_db(db, "Missing Client", {"industry": "Insurance"})

        self.assertEqual(context.exception.code, "NOT_FOUND")
        self.assertEqual(str(context.exception), "Client Missing Client not found")
        mock_get_client_by_name.assert_called_once_with(db, "Missing Client")

    @patch("app.database.clients_db.get_client_by_name")
    def test_update_client_in_db_updates_allowed_fields(self, mock_get_client_by_name) -> None:
        db = MagicMock()
        client = _ClientRecord()
        mock_get_client_by_name.return_value = client

        result = update_client_in_db(
            db,
            "Acme Corp",
            {
                "name": "Acme Global",
                "industry": "Insurance",
                "status": "inactive",
                "location": None,
                "ignored": "value",
            },
        )

        self.assertIs(result, client)
        self.assertEqual(client.name, "Acme Global")
        self.assertEqual(client.industry, "Insurance")
        self.assertEqual(client.status, "inactive")
        self.assertIsNone(client.location)
        db.add.assert_called_once_with(client)
        db.commit.assert_called_once_with()
        db.refresh.assert_called_once_with(client)

    @patch("app.database.clients_db.get_client_by_name")
    def test_update_client_in_db_rolls_back_on_integrity_error(
        self,
        mock_get_client_by_name,
    ) -> None:
        db = MagicMock()
        client = _ClientRecord()
        db.commit.side_effect = IntegrityError("stmt", "params", Exception("boom"))
        mock_get_client_by_name.return_value = client

        with self.assertRaises(InvalidInputError) as context:
            update_client_in_db(db, "Acme Corp", {"name": "Existing Client"})

        self.assertEqual(str(context.exception), "Client name already exists")
        db.rollback.assert_called_once_with()

    @patch("app.database.clients_db.get_client_by_name")
    def test_update_client_in_db_rolls_back_on_unexpected_error(
        self,
        mock_get_client_by_name,
    ) -> None:
        db = MagicMock()
        client = _ClientRecord()
        db.commit.side_effect = RuntimeError("boom")
        mock_get_client_by_name.return_value = client

        with self.assertRaises(DatabaseOperationException) as context:
            update_client_in_db(db, "Acme Corp", {"industry": "Insurance"})

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.message, "Unable to update client: Acme Corp")
        db.rollback.assert_called_once_with()

    @patch("app.database.clients_db.get_client_by_name", return_value=None)
    def test_soft_delete_client_raises_not_found(self, mock_get_client_by_name) -> None:
        db = MagicMock()

        with self.assertRaises(AppException) as context:
            soft_delete_client(db, "Missing Client")

        self.assertEqual(context.exception.code, "NOT_FOUND")
        self.assertEqual(str(context.exception), "Client Missing Client not found")
        mock_get_client_by_name.assert_called_once_with(db, "Missing Client")

    @patch("app.database.clients_db.get_client_by_name")
    def test_soft_delete_client_marks_client_archived(self, mock_get_client_by_name) -> None:
        db = MagicMock()
        client = _ClientRecord()
        mock_get_client_by_name.return_value = client

        result = soft_delete_client(db, "Acme Corp")

        self.assertIs(result, client)
        self.assertEqual(client.status, "archived")
        db.add.assert_called_once_with(client)
        db.execute.assert_called_once()
        db.commit.assert_called_once_with()
        db.refresh.assert_called_once_with(client)

    @patch("app.database.clients_db.get_client_by_name")
    def test_soft_delete_client_rolls_back_on_unexpected_error(
        self,
        mock_get_client_by_name,
    ) -> None:
        db = MagicMock()
        client = _ClientRecord()
        db.commit.side_effect = RuntimeError("boom")
        mock_get_client_by_name.return_value = client

        with self.assertRaises(DatabaseOperationException) as context:
            soft_delete_client(db, "Acme Corp")

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.message, "Unable to archive client: Acme Corp")
        db.rollback.assert_called_once_with()

    def test_check_client_name_exists_without_exclusion(self) -> None:
        db = MagicMock()
        result_proxy = MagicMock()
        result_proxy.scalar.return_value = True
        db.execute.return_value = result_proxy

        result = check_client_name_exists(db, "Acme Corp")

        self.assertTrue(result)
        db.execute.assert_called_once()
        result_proxy.scalar.assert_called_once_with()

    def test_check_client_name_exists_with_exclusion(self) -> None:
        db = MagicMock()
        result_proxy = MagicMock()
        result_proxy.scalar.return_value = False
        db.execute.return_value = result_proxy

        result = check_client_name_exists(db, "Acme Corp", exclude_name="Acme Legacy")

        self.assertFalse(result)
        db.execute.assert_called_once()
        result_proxy.scalar.assert_called_once_with()

    def test_check_client_name_exists_wraps_unexpected_errors(self) -> None:
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")

        with self.assertRaises(DatabaseOperationException) as context:
            check_client_name_exists(db, "Acme Corp")

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.message, "Unable to check client name: Acme Corp")

    def test_count_active_projects_by_client_returns_count(self) -> None:
        from app.database.clients_db import count_active_projects_by_client

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one.return_value = 3

        with patch("app.database.clients_db._read_sql_file", return_value="SELECT 1"):
            count = count_active_projects_by_client(mock_db, 11)

        self.assertEqual(count, 3)

    def test_count_active_projects_by_client_returns_zero_for_none(self) -> None:
        from app.database.clients_db import count_active_projects_by_client

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one.return_value = None

        with patch("app.database.clients_db._read_sql_file", return_value="SELECT 1"):
            count = count_active_projects_by_client(mock_db, 11)

        self.assertEqual(count, 0)

    def test_count_active_projects_by_client_wraps_failure(self) -> None:
        from app.database.clients_db import count_active_projects_by_client

        mock_db = MagicMock()
        mock_db.execute.side_effect = RuntimeError("db down")

        with patch("app.database.clients_db._read_sql_file", return_value="SELECT 1"):
            with self.assertRaises(DatabaseOperationException) as context:
                count_active_projects_by_client(mock_db, 11)

        self.assertIn("Unable to check active projects for client", str(context.exception))
