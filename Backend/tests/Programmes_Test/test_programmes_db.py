"""Tests for the programme database helpers."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, DatabaseOperationException
from app.database.programmes_db import (
    _read_sql_file,
    _row_to_programme,
    check_programme_name_exists,
    count_active_projects_by_programme,
    create_programme_entry,
    delete_programme_entry,
    get_client_by_id,
    get_programme,
    get_programme_by_id,
)
from app.models.clients_models import Client
from app.models.programmes_models import Programme


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

    def scalar_one(self):
        return self._scalar_value

    def scalar(self):
        return self._scalar_value


class _FakeDB:
    def __init__(self, result: _FakeResult, get_result=None) -> None:
        self.result = result
        self.get_result = get_result
        self.calls = []
        self.added = None
        self.refreshed = None
        self.committed = False
        self.rolled_back = False

    def execute(self, query, params=None):
        self.calls.append((query, params))
        return self.result

    def get(self, model, key):
        self.calls.append(("get", model, key))
        return self.get_result

    def add(self, model):
        self.added = model

    def commit(self):
        self.committed = True

    def refresh(self, model):
        self.refreshed = model

    def rollback(self):
        self.rolled_back = True


class _RaisingDB(_FakeDB):
    def __init__(self, error: Exception) -> None:
        super().__init__(_FakeResult())
        self.error = error

    def execute(self, query, params=None):
        self.calls.append((query, params))
        raise self.error


def _programme_row(**overrides):
    created_at = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    last_modified = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
    base = {
        "id": 101,
        "client_id": 202,
        "name": "Modernisation",
        "description": "Claims modernisation programme.",
        "status": "active",
        "created_at": created_at,
        "last_modified": last_modified,
    }
    base.update(overrides)
    return base


def _client(**overrides):
    base = {
        "id": 202,
        "status": "active",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class ProgrammeDatabaseTests(unittest.TestCase):
    """Verify SQL-backed programme helper behavior."""

    def test_programme_insert_sql_includes_status(self) -> None:
        content = _read_sql_file("programme_insert.sql")

        self.assertIn("INSERT INTO programmes", content)
        self.assertIn(":status", content)

    def test_programme_name_exists_sql_checks_name_per_client(self) -> None:
        content = _read_sql_file("check_programme_name_exists.sql")

        self.assertIn("client_id = :client_id", content)
        self.assertIn("LOWER(name) = LOWER(:name)", content)
        self.assertIn("status != 'archived'", content)

    def test_row_to_programme_populates_status(self) -> None:
        programme = _row_to_programme(_programme_row(status="archived"))

        self.assertIsInstance(programme, Programme)
        self.assertEqual(programme.status, "archived")

    def test_get_programme_by_id_uses_sql_and_maps_row(self) -> None:
        db = _FakeDB(_FakeResult(row=_programme_row()))

        with patch("app.database.programmes_db._read_sql_file", return_value="SELECT 1") as reader:
            programme = get_programme_by_id(db, 101)

        self.assertEqual(programme.name, "Modernisation")
        self.assertEqual(db.calls[0][1], {"programme_id": 101})
        reader.assert_called_once_with("get_programme_by_id.sql")

    def test_get_programme_by_id_returns_none_when_row_missing(self) -> None:
        db = _FakeDB(_FakeResult(row=None))

        with patch("app.database.programmes_db._read_sql_file", return_value="SELECT 1"):
            programme = get_programme_by_id(db, 101)

        self.assertIsNone(programme)

    def test_get_programme_helper_success(self) -> None:
        db = _FakeDB(_FakeResult(row=_programme_row()))
        with patch("app.database.programmes_db._read_sql_file", return_value="SELECT 1"):
            programme = get_programme(db, 101)
        self.assertEqual(programme.id, 101)

    def test_get_programme_helper_raises_app_exception(self) -> None:
        db = _FakeDB(_FakeResult(row=None))
        with patch("app.database.programmes_db._read_sql_file", return_value="SELECT 1"):
            with self.assertRaises(AppException) as context:
                get_programme(db, 101)

        self.assertEqual(context.exception.code, "PROGRAMME_NOT_FOUND")
        self.assertEqual(context.exception.status_code, 404)

    def test_get_programme_by_id_wraps_lookup_failure(self) -> None:
        db = _RaisingDB(RuntimeError("db down"))

        with patch("app.database.programmes_db._read_sql_file", return_value="SELECT 1"):
            with self.assertRaises(DatabaseOperationException) as context:
                get_programme_by_id(db, 101)

        self.assertIn("Unable to fetch programme: 101", str(context.exception))

    def test_create_programme_entry_uses_sql_and_commits(self) -> None:
        db = _FakeDB(_FakeResult(row=_programme_row(id=102, name="Payments")))

        with patch("app.database.programmes_db._read_sql_file", return_value="INSERT 1") as reader:
            programme = create_programme_entry(
                db,
                client_id=202,
                name="  Payments  ",
                description="  Payments programme  ",
            )

        self.assertTrue(db.committed)
        self.assertEqual(programme.name, "Payments")
        self.assertEqual(db.calls[0][1]["status"], "active")
        reader.assert_called_once_with("programme_insert.sql")

    def test_create_programme_entry_rolls_back_and_reraises_integrity_error(self) -> None:
        error = IntegrityError("statement", "params", Exception("duplicate"))
        db = _RaisingDB(error)

        with patch("app.database.programmes_db._read_sql_file", return_value="INSERT 1"):
            with self.assertRaises(IntegrityError):
                create_programme_entry(
                    db,
                    client_id=202,
                    name="Payments",
                    description=None,
                )

        self.assertTrue(db.rolled_back)

    def test_create_programme_entry_wraps_unexpected_failure(self) -> None:
        db = _RaisingDB(RuntimeError("db down"))

        with patch("app.database.programmes_db._read_sql_file", return_value="INSERT 1"):
            with self.assertRaises(DatabaseOperationException) as context:
                create_programme_entry(
                    db,
                    client_id=202,
                    name="Payments",
                    description=None,
                )

        self.assertTrue(db.rolled_back)
        self.assertIn("Unable to create programme: Payments", str(context.exception))

    def test_check_programme_name_exists_returns_bool(self) -> None:
        db = _FakeDB(_FakeResult(scalar_value=1))

        with patch("app.database.programmes_db._read_sql_file", return_value="SELECT 1") as reader:
            exists = check_programme_name_exists(db, client_id=202, name="  Modernisation  ")

        self.assertTrue(exists)
        self.assertEqual(db.calls[0][1], {"client_id": 202, "name": "Modernisation"})
        reader.assert_called_once_with("check_programme_name_exists.sql")

    def test_check_programme_name_exists_wraps_failure(self) -> None:
        db = _RaisingDB(RuntimeError("db down"))

        with patch("app.database.programmes_db._read_sql_file", return_value="SELECT 1"):
            with self.assertRaises(DatabaseOperationException) as context:
                check_programme_name_exists(db, client_id=202, name="Modernisation")

        self.assertIn("Unable to check programme name: Modernisation", str(context.exception))

    def test_count_active_projects_by_programme_uses_sql(self) -> None:
        db = _FakeDB(_FakeResult(scalar_value=3))

        with patch("app.database.programmes_db._read_sql_file", return_value="SELECT 1") as reader:
            count = count_active_projects_by_programme(db, 101)

        self.assertEqual(count, 3)
        reader.assert_called_once_with("programme_count_active_projects.sql")

    def test_count_active_projects_by_programme_returns_zero_for_none(self) -> None:
        db = _FakeDB(_FakeResult(scalar_value=None))

        with patch("app.database.programmes_db._read_sql_file", return_value="SELECT 1"):
            count = count_active_projects_by_programme(db, 101)

        self.assertEqual(count, 0)

    def test_count_active_projects_by_programme_wraps_failure(self) -> None:
        db = _RaisingDB(RuntimeError("db down"))

        with patch("app.database.programmes_db._read_sql_file", return_value="SELECT 1"):
            with self.assertRaises(DatabaseOperationException) as context:
                count_active_projects_by_programme(db, 101)

        self.assertIn("Unable to check active projects for programme: 101", str(context.exception))

    def test_delete_programme_entry_soft_deletes_and_returns_row(self) -> None:
        programme = _row_to_programme(_programme_row())
        db = _FakeDB(_FakeResult(), get_result=programme)

        archived = delete_programme_entry(db, 101)

        self.assertTrue(db.committed)
        self.assertEqual(archived.status, "archived")
        self.assertIs(db.added, archived)
        self.assertIs(db.refreshed, archived)
        self.assertEqual(db.calls[0], ("get", Programme, 101))

    def test_delete_programme_entry_raises_not_found_when_row_missing(self) -> None:
        db = _FakeDB(_FakeResult(), get_result=None)

        with self.assertRaises(AppException) as context:
            delete_programme_entry(db, 101)

        self.assertEqual(context.exception.code, "PROGRAMME_NOT_FOUND")
        self.assertFalse(db.committed)

    def test_delete_programme_entry_raises_not_found_when_already_archived(self) -> None:
        programme = _row_to_programme(_programme_row(status="archived"))
        db = _FakeDB(_FakeResult(), get_result=programme)

        with self.assertRaises(AppException) as context:
            delete_programme_entry(db, 101)

        self.assertEqual(context.exception.code, "PROGRAMME_NOT_FOUND")
        self.assertFalse(db.committed)

    def test_delete_programme_entry_rolls_back_and_wraps_unexpected_failure(self) -> None:
        programme = _row_to_programme(_programme_row())
        db = _FakeDB(_FakeResult(), get_result=programme)
        db.commit = lambda: (_ for _ in ()).throw(RuntimeError("db down"))

        with self.assertRaises(DatabaseOperationException) as context:
            delete_programme_entry(db, 101)

        self.assertTrue(db.rolled_back)
        self.assertIn("Unable to delete programme: 101", str(context.exception))

    def test_sql_read_errors_are_wrapped(self) -> None:
        _read_sql_file.cache_clear()

        with patch("pathlib.Path.read_text", side_effect=OSError("missing file")):
            with self.assertRaises(DatabaseOperationException) as context:
                _read_sql_file("programme_insert.sql")

        self.assertIn("Unable to read SQL file: programme_insert.sql", str(context.exception))

    def test_get_client_by_id_returns_client_when_active(self) -> None:
        client = _client(status="active")
        db = _FakeDB(_FakeResult(), get_result=client)

        result = get_client_by_id(db, 202)

        self.assertIs(result, client)
        self.assertEqual(db.calls[0], ("get", Client, 202))

    def test_get_client_by_id_returns_none_when_missing(self) -> None:
        db = _FakeDB(_FakeResult(), get_result=None)

        result = get_client_by_id(db, 202)

        self.assertIsNone(result)

    def test_get_client_by_id_returns_none_when_archived(self) -> None:
        client = _client(status="archived")
        db = _FakeDB(_FakeResult(), get_result=client)

        result = get_client_by_id(db, 202)

        self.assertIsNone(result)

    # ── update_programme_entry ──────────────────────────────────────────────

    def test_update_programme_entry_updates_name_and_commits(self) -> None:
        from app.database.programmes_db import update_programme_entry

        programme = _row_to_programme(_programme_row())
        db = _FakeDB(_FakeResult(), get_result=programme)

        updated = update_programme_entry(db, 101, name="New Name")

        self.assertEqual(updated.name, "New Name")
        self.assertTrue(db.committed)
        self.assertIs(db.refreshed, updated)

    def test_update_programme_entry_updates_description(self) -> None:
        from app.database.programmes_db import update_programme_entry

        programme = _row_to_programme(_programme_row())
        db = _FakeDB(_FakeResult(), get_result=programme)

        updated = update_programme_entry(db, 101, description="New Desc")

        self.assertEqual(updated.description, "New Desc")
        self.assertTrue(db.committed)

    def test_update_programme_entry_updates_status(self) -> None:
        from app.database.programmes_db import update_programme_entry

        programme = _row_to_programme(_programme_row())
        db = _FakeDB(_FakeResult(), get_result=programme)

        updated = update_programme_entry(db, 101, status="onhold")

        self.assertEqual(updated.status, "onhold")
        self.assertTrue(db.committed)

    def test_update_programme_entry_raises_not_found_when_missing(self) -> None:
        from app.database.programmes_db import update_programme_entry

        db = _FakeDB(_FakeResult(), get_result=None)

        with self.assertRaises(AppException) as context:
            update_programme_entry(db, 101, name="X")

        self.assertEqual(context.exception.code, "PROGRAMME_NOT_FOUND")

    def test_update_programme_entry_raises_not_found_when_archived(self) -> None:
        from app.database.programmes_db import update_programme_entry

        programme = _row_to_programme(_programme_row(status="archived"))
        db = _FakeDB(_FakeResult(), get_result=programme)

        with self.assertRaises(AppException) as context:
            update_programme_entry(db, 101, name="X")

        self.assertEqual(context.exception.code, "PROGRAMME_NOT_FOUND")

    def test_update_programme_entry_rolls_back_on_failure(self) -> None:
        from app.database.programmes_db import update_programme_entry

        programme = _row_to_programme(_programme_row())
        db = _FakeDB(_FakeResult(), get_result=programme)
        db.commit = lambda: (_ for _ in ()).throw(RuntimeError("db down"))

        with self.assertRaises(DatabaseOperationException):
            update_programme_entry(db, 101, name="X")

        self.assertTrue(db.rolled_back)

    # ── list_all_programmes ─────────────────────────────────────────────────

    def _make_programme_row(self, programme, project_count=0):
        """Helper to create a row tuple matching list_all_programmes output."""
        from types import SimpleNamespace

        return SimpleNamespace(Programme=programme, project_count=project_count)

    def test_list_all_programmes_returns_non_archived(self) -> None:
        from unittest.mock import MagicMock

        from app.database.programmes_db import list_all_programmes

        programme = _row_to_programme(_programme_row())
        row = self._make_programme_row(programme, project_count=2)
        mock_db = MagicMock()
        mock_db.execute.return_value.all.return_value = [row]

        result = list_all_programmes(mock_db)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].Programme.name, "Modernisation")

    def test_list_all_programmes_returns_empty_list(self) -> None:
        from unittest.mock import MagicMock

        from app.database.programmes_db import list_all_programmes

        mock_db = MagicMock()
        mock_db.execute.return_value.all.return_value = []

        result = list_all_programmes(mock_db)

        self.assertEqual(result, [])

    def test_list_all_programmes_wraps_failure(self) -> None:
        from unittest.mock import MagicMock

        from app.database.programmes_db import list_all_programmes

        mock_db = MagicMock()
        mock_db.execute.side_effect = RuntimeError("db down")

        with self.assertRaises(DatabaseOperationException) as context:
            list_all_programmes(mock_db)

        self.assertIn("Unable to list all programmes", str(context.exception))

    def test_list_all_programmes_filters_by_client_id(self) -> None:
        from unittest.mock import MagicMock

        from app.database.programmes_db import list_all_programmes

        programme = _row_to_programme(_programme_row(client_id=202))
        row = self._make_programme_row(programme, project_count=1)
        mock_db = MagicMock()
        mock_db.execute.return_value.all.return_value = [row]

        result = list_all_programmes(mock_db, client_id=202)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].Programme.client_id, 202)

    def test_list_all_programmes_no_filter_returns_all(self) -> None:
        from unittest.mock import MagicMock

        from app.database.programmes_db import list_all_programmes

        p1 = _row_to_programme(_programme_row(id=1, client_id=202))
        p2 = _row_to_programme(_programme_row(id=2, client_id=303))
        rows = [
            self._make_programme_row(p1, project_count=0),
            self._make_programme_row(p2, project_count=3),
        ]
        mock_db = MagicMock()
        mock_db.execute.return_value.all.return_value = rows

        result = list_all_programmes(mock_db, client_id=None)

        self.assertEqual(len(result), 2)

    def test_get_programme_with_details_returns_row(self) -> None:
        from unittest.mock import MagicMock
        from uuid import uuid4

        from app.database.programmes_db import get_programme_with_details_db

        programme_id = uuid4()
        fake_programme = MagicMock()
        mock_db = MagicMock()
        mock_db.execute.return_value.first.return_value = (fake_programme, 3, "Jane Doe")

        result = get_programme_with_details_db(mock_db, programme_id)

        self.assertEqual(result, (fake_programme, 3, "Jane Doe"))

    def test_get_programme_with_details_returns_none_when_missing(self) -> None:
        from unittest.mock import MagicMock
        from uuid import uuid4

        from app.database.programmes_db import get_programme_with_details_db

        mock_db = MagicMock()
        mock_db.execute.return_value.first.return_value = None

        result = get_programme_with_details_db(mock_db, uuid4())

        self.assertIsNone(result)

    def test_get_programme_with_details_wraps_unexpected_failure(self) -> None:
        from unittest.mock import MagicMock
        from uuid import uuid4

        from app.core.exceptions import AppException
        from app.database.programmes_db import get_programme_with_details_db

        mock_db = MagicMock()
        mock_db.execute.side_effect = RuntimeError("db down")

        with self.assertRaises(AppException):
            get_programme_with_details_db(mock_db, uuid4())
