"""Tests for the project database helpers."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, DatabaseOperationException
from app.database.projects_db import (
    _read_sql_file,
    _row_to_project,
    check_project_name_exists,
    create_project_entry,
    get_project_approvers,
    list_all_projects,
    list_projects_by_programme_id,
    soft_delete_project_entry,
)
from app.models.project_models import Project
from app.schemas.projects import ProjectListRow


class _FakeMappingsResult:
    def __init__(self, row=None, rows=None) -> None:
        self._row = row
        self._rows = rows or []

    def one(self):
        return self._row

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, row=None, rows=None, scalar_value=None) -> None:
        self._mappings = _FakeMappingsResult(row=row, rows=rows)
        self._rows = rows or []
        self._scalar_value = scalar_value

    def mappings(self):
        return self._mappings

    def all(self):
        return self._rows

    def scalar(self):
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


class _RaisingDB(_FakeDB):
    def __init__(self, error: Exception) -> None:
        super().__init__(_FakeResult())
        self.error = error

    def execute(self, query, params=None):
        self.calls.append((query, params))
        raise self.error


def _project_row(**overrides):
    created_at = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    last_modified = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
    base = {
        "id": 501,
        "programme_id": UUID("78911c55-d312-45d6-9f40-11ff2b9ecf6e"),
        "name": "Migration",
        "description": "Migration workstream.",
        "status": "Active",
        "lead_id": UUID("00000000-0000-0000-0000-000000000001"),
        "lead_name": "John Lead",
        "start_date": date(2026, 6, 1),
        "created_at": created_at,
        "last_modified": last_modified,
    }
    base.update(overrides)
    return base


def _all_projects_orm_row(**overrides):
    """Return a fake ORM row matching the shape returned by list_all_projects."""
    created_at = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
    last_modified = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
    project = SimpleNamespace(
        id=overrides.get("id", 504),
        programme_id=overrides.get("programme_id", UUID("78911c55-d312-45d6-9f40-11ff2b9ecf6e")),
        name=overrides.get("name", "AllProjects"),
        description=overrides.get("description", "Test description"),
        status=overrides.get("status", "Active"),
        start_date=overrides.get("start_date", date(2026, 6, 1)),
        lead_id=overrides.get("lead_id", UUID("00000000-0000-0000-0000-000000000001")),
        created_at=overrides.get("created_at", created_at),
        last_modified=overrides.get("last_modified", last_modified),
    )
    return SimpleNamespace(
        Project=project,
        programme_name=overrides.get("programme_name", "Programme A"),
        client_id=overrides.get("client_id", UUID("11111111-1111-1111-1111-111111111111")),
        client_name=overrides.get("client_name", "Client A"),
        lead_name=overrides.get("lead_name", "John Lead"),
    )


class ProjectDatabaseTests(unittest.TestCase):
    """Verify SQL-backed project helper behavior."""

    def test_project_insert_sql_includes_start_date(self) -> None:
        content = _read_sql_file("project_insert.sql")

        self.assertIn(":start_date", content)
        self.assertIn("RETURNING", content)

    def test_sql_read_errors_are_wrapped(self) -> None:
        _read_sql_file.cache_clear()

        with patch("pathlib.Path.read_text", side_effect=OSError("missing file")):
            with self.assertRaises(DatabaseOperationException) as context:
                _read_sql_file("project_insert.sql")

        self.assertIn("Unable to read SQL file: project_insert.sql", str(context.exception))

    def test_project_name_exists_sql_checks_name_per_programme(self) -> None:
        content = _read_sql_file("check_project_name_exists.sql")

        self.assertIn("programme_id = :programme_id", content)
        self.assertIn("LOWER(name) = LOWER(:name)", content)

    def test_project_list_sql_orders_rows(self) -> None:
        content = _read_sql_file("project_list_by_programme_id.sql")

        self.assertIn("ORDER BY p.created_at DESC, p.name ASC", content)

    def test_row_to_project_maps_status(self) -> None:
        project = _row_to_project(_project_row())

        self.assertIsInstance(project, Project)
        self.assertEqual(project.status, "Active")
        self.assertEqual(project.lead_id, UUID("00000000-0000-0000-0000-000000000001"))
        self.assertEqual(getattr(project, "lead_name"), "John Lead")

    def test_create_project_entry_uses_sql_and_commits(self) -> None:
        lead_uid = UUID("00000000-0000-0000-0000-000000000001")
        db = _FakeDB(_FakeResult(row=_project_row(id=502, name="Delivery")))

        with patch("app.database.projects_db._read_sql_file", return_value="INSERT 1") as reader:
            project = create_project_entry(
                db,
                programme_id=UUID("78911c55-d312-45d6-9f40-11ff2b9ecf6e"),
                name="  Delivery  ",
                description="  Delivery project  ",
                lead_id=lead_uid,
                status="Active",
                start_date=date(2026, 6, 1),
            )

        self.assertTrue(db.committed)
        self.assertEqual(project.name, "Delivery")
        self.assertEqual(db.calls[0][1]["status"], "Active")
        self.assertEqual(db.calls[0][1]["lead_id"], lead_uid)
        reader.assert_called_once_with("project_insert.sql")

    def test_create_project_entry_rolls_back_and_reraises_integrity_error(self) -> None:
        error = IntegrityError("statement", "params", Exception("duplicate"))
        db = _RaisingDB(error)

        with patch("app.database.projects_db._read_sql_file", return_value="INSERT 1"):
            with self.assertRaises(IntegrityError):
                create_project_entry(
                    db,
                    programme_id=UUID("78911c55-d312-45d6-9f40-11ff2b9ecf6e"),
                    name="Delivery",
                    description=None,
                )

        self.assertTrue(db.rolled_back)

    def test_create_project_entry_wraps_unexpected_failure(self) -> None:
        db = _RaisingDB(RuntimeError("db down"))

        with patch("app.database.projects_db._read_sql_file", return_value="INSERT 1"):
            with self.assertRaises(DatabaseOperationException) as context:
                create_project_entry(
                    db,
                    programme_id=UUID("78911c55-d312-45d6-9f40-11ff2b9ecf6e"),
                    name="Delivery",
                    description=None,
                )

        self.assertTrue(db.rolled_back)
        self.assertIn("Unable to create project: Delivery", str(context.exception))

    def test_check_project_name_exists_returns_bool(self) -> None:
        db = _FakeDB(_FakeResult(scalar_value=1))

        with patch("app.database.projects_db._read_sql_file", return_value="SELECT 1") as reader:
            exists = check_project_name_exists(
                db, programme_id=UUID("78911c55-d312-45d6-9f40-11ff2b9ecf6e"), name="  Migration  "
            )

        self.assertTrue(exists)
        self.assertEqual(
            db.calls[0][1],
            {"programme_id": UUID("78911c55-d312-45d6-9f40-11ff2b9ecf6e"), "name": "Migration"},
        )
        reader.assert_called_once_with("check_project_name_exists.sql")

    def test_check_project_name_exists_wraps_failure(self) -> None:
        db = _RaisingDB(RuntimeError("db down"))

        with patch("app.database.projects_db._read_sql_file", return_value="SELECT 1"):
            with self.assertRaises(DatabaseOperationException) as context:
                check_project_name_exists(
                    db, programme_id=UUID("78911c55-d312-45d6-9f40-11ff2b9ecf6e"), name="Migration"
                )

        self.assertIn("Unable to check project name: Migration", str(context.exception))

    def test_list_projects_by_programme_id_uses_sql_and_maps_rows(self) -> None:
        rows = [_project_row(id=503, name="Stabilisation")]
        db = _FakeDB(_FakeResult(rows=rows))

        with patch("app.database.projects_db._read_sql_file", return_value="SELECT 1") as reader:
            projects = list_projects_by_programme_id(
                db, UUID("78911c55-d312-45d6-9f40-11ff2b9ecf6e")
            )

        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].name, "Stabilisation")
        reader.assert_called_once_with("project_list_by_programme_id.sql")

    def test_list_projects_by_programme_id_wraps_failure(self) -> None:
        db = _RaisingDB(RuntimeError("db down"))

        with patch("app.database.projects_db._read_sql_file", return_value="SELECT 1"):
            with self.assertRaises(DatabaseOperationException) as context:
                list_projects_by_programme_id(db, UUID("78911c55-d312-45d6-9f40-11ff2b9ecf6e"))

        self.assertIn(
            "Unable to fetch projects for programme: 78911c55-d312-45d6-9f40-11ff2b9ecf6e",
            str(context.exception),
        )

    def test_list_all_projects_maps_rows_to_project_list_row(self) -> None:
        fake_row = _all_projects_orm_row(id=504, name="AllProjects")
        db = _FakeDB(_FakeResult(rows=[fake_row]))

        projects = list_all_projects(db)

        self.assertEqual(len(projects), 1)
        self.assertIsInstance(projects[0], ProjectListRow)
        self.assertEqual(projects[0].name, "AllProjects")
        self.assertEqual(projects[0].programme_name, "Programme A")
        self.assertEqual(projects[0].client_name, "Client A")
        self.assertEqual(projects[0].lead_id, UUID("00000000-0000-0000-0000-000000000001"))
        self.assertEqual(projects[0].lead_name, "John Lead")

    def test_list_all_projects_includes_projects_from_non_active_clients(self) -> None:
        """Only project status is filtered; client and programme status are not."""
        fake_row = _all_projects_orm_row(
            id=505, name="OrphanProject", client_name="Archived Client"
        )
        db = _FakeDB(_FakeResult(rows=[fake_row]))

        projects = list_all_projects(db)

        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].client_name, "Archived Client")

    def test_list_all_projects_returns_empty_list(self) -> None:
        db = _FakeDB(_FakeResult(rows=[]))

        projects = list_all_projects(db)

        self.assertEqual(projects, [])

    def test_list_all_projects_wraps_failure(self) -> None:
        db = _RaisingDB(RuntimeError("db down"))

        with self.assertRaises(DatabaseOperationException) as context:
            list_all_projects(db)

        self.assertIn(
            "Unable to fetch all projects",
            str(context.exception),
        )

    # ── get_project_by_id ───────────────────────────────────────────────────

    def test_get_project_by_id_returns_project_when_active(self) -> None:
        from unittest.mock import MagicMock

        from app.database.projects_db import get_project_by_id

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="active",
        )
        mock_db = MagicMock()
        mock_db.get.return_value = project

        result = get_project_by_id(mock_db, UUID("11111111-1111-1111-1111-111111111111"))

        self.assertIs(result, project)

    def test_get_project_by_id_returns_none_when_missing(self) -> None:
        from unittest.mock import MagicMock

        from app.database.projects_db import get_project_by_id

        mock_db = MagicMock()
        mock_db.get.return_value = None

        result = get_project_by_id(mock_db, UUID("11111111-1111-1111-1111-111111111111"))

        self.assertIsNone(result)

    def test_get_project_by_id_returns_none_when_archived(self) -> None:
        from unittest.mock import MagicMock

        from app.database.projects_db import get_project_by_id

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="archived",
        )
        mock_db = MagicMock()
        mock_db.get.return_value = project

        result = get_project_by_id(mock_db, UUID("11111111-1111-1111-1111-111111111111"))

        self.assertIsNone(result)

    def test_get_project_by_id_wraps_failure(self) -> None:
        from unittest.mock import MagicMock

        from app.database.projects_db import get_project_by_id

        mock_db = MagicMock()
        mock_db.get.side_effect = RuntimeError("db down")

        with self.assertRaises(DatabaseOperationException) as context:
            get_project_by_id(mock_db, UUID("11111111-1111-1111-1111-111111111111"))

        self.assertIn("Unable to fetch project", str(context.exception))

    # ── update_project_entry ────────────────────────────────────────────────

    def test_update_project_entry_updates_name_and_commits(self) -> None:
        from unittest.mock import MagicMock, patch

        from app.database.projects_db import update_project_entry

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Old Name",
            status="active",
        )
        mock_db = MagicMock()
        mock_db.get.return_value = project

        with patch("app.database.projects_db.get_project_by_id", return_value=project):
            updated = update_project_entry(
                mock_db, UUID("11111111-1111-1111-1111-111111111111"), name="New Name"
            )

        self.assertEqual(updated.name, "New Name")
        mock_db.commit.assert_called_once()

    def test_update_project_entry_updates_status(self) -> None:
        from unittest.mock import MagicMock, patch

        from app.database.projects_db import update_project_entry

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="active",
        )
        mock_db = MagicMock()

        with patch("app.database.projects_db.get_project_by_id", return_value=project):
            updated = update_project_entry(
                mock_db, UUID("11111111-1111-1111-1111-111111111111"), status="onhold"
            )

        self.assertEqual(updated.status, "onhold")

    def test_update_project_entry_updates_description(self) -> None:
        from unittest.mock import MagicMock, patch

        from app.database.projects_db import update_project_entry

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="active",
        )
        mock_db = MagicMock()

        with patch("app.database.projects_db.get_project_by_id", return_value=project):
            updated = update_project_entry(
                mock_db, UUID("11111111-1111-1111-1111-111111111111"), description="New Desc"
            )

        self.assertEqual(updated.description, "New Desc")

    def test_update_project_entry_raises_not_found_when_missing(self) -> None:
        from unittest.mock import MagicMock, patch

        from app.core.exceptions import AppException
        from app.database.projects_db import update_project_entry

        mock_db = MagicMock()

        with patch("app.database.projects_db.get_project_by_id", return_value=None):
            with self.assertRaises(AppException) as context:
                update_project_entry(
                    mock_db, UUID("11111111-1111-1111-1111-111111111111"), name="X"
                )

        self.assertEqual(context.exception.code, "PROJECT_NOT_FOUND")

    def test_update_project_entry_rolls_back_on_failure(self) -> None:
        from unittest.mock import MagicMock, patch

        from app.database.projects_db import update_project_entry

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="active",
        )
        mock_db = MagicMock()
        mock_db.commit.side_effect = RuntimeError("db down")

        with patch("app.database.projects_db.get_project_by_id", return_value=project):
            with self.assertRaises(DatabaseOperationException):
                update_project_entry(
                    mock_db, UUID("11111111-1111-1111-1111-111111111111"), name="X"
                )

        mock_db.rollback.assert_called_once()

    # ── soft_delete_project_entry ───────────────────────────────────────────

    def test_soft_delete_project_entry_sets_archived_status(self) -> None:
        from unittest.mock import MagicMock

        from app.database.projects_db import soft_delete_project_entry

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="active",
        )
        mock_db = MagicMock()
        mock_db.get.return_value = project

        result = soft_delete_project_entry(mock_db, UUID("11111111-1111-1111-1111-111111111111"))

        self.assertEqual(result.status, "archived")
        mock_db.commit.assert_called_once()

    def test_soft_delete_project_entry_raises_not_found_when_missing(self) -> None:
        from unittest.mock import MagicMock

        from app.core.exceptions import AppException
        from app.database.projects_db import soft_delete_project_entry

        mock_db = MagicMock()
        mock_db.get.return_value = None

        with self.assertRaises(AppException) as context:
            soft_delete_project_entry(mock_db, UUID("11111111-1111-1111-1111-111111111111"))

        self.assertEqual(context.exception.code, "PROJECT_NOT_FOUND")

    def test_soft_delete_project_entry_raises_not_found_when_already_archived(self) -> None:

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="archived",
        )
        mock_db = MagicMock()
        mock_db.get.return_value = project

        with self.assertRaises(AppException) as context:
            soft_delete_project_entry(mock_db, UUID("11111111-1111-1111-1111-111111111111"))

        self.assertEqual(context.exception.code, "PROJECT_NOT_FOUND")

    def test_soft_delete_project_entry_rolls_back_on_failure(self) -> None:

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="active",
        )
        mock_db = MagicMock()
        mock_db.get.return_value = project
        mock_db.commit.side_effect = RuntimeError("db down")

        with self.assertRaises(DatabaseOperationException):
            soft_delete_project_entry(mock_db, UUID("11111111-1111-1111-1111-111111111111"))

        mock_db.rollback.assert_called_once()

    # ── update_project_jira_config ──────────────────────────────────────────

    def test_update_project_jira_config_updates_url_and_key(self) -> None:
        from unittest.mock import MagicMock, patch

        from app.database.projects_db import update_project_jira_config

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="active",
        )
        mock_db = MagicMock()

        with patch("app.database.projects_db.get_project_by_id", return_value=project):
            updated = update_project_jira_config(
                mock_db,
                UUID("11111111-1111-1111-1111-111111111111"),
                jira_url="https://jira.example.com",
                jira_project_key="PROJ",
            )

        self.assertEqual(updated.jira_url, "https://jira.example.com")
        self.assertEqual(updated.jira_project_key, "PROJ")
        mock_db.add.assert_called_once_with(project)
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(project)

    def test_update_project_jira_config_partial_update(self) -> None:
        from unittest.mock import MagicMock, patch

        from app.database.projects_db import update_project_jira_config

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="active",
            jira_url="https://old.example.com",
            jira_project_key="OLD",
        )
        mock_db = MagicMock()

        with patch("app.database.projects_db.get_project_by_id", return_value=project):
            updated = update_project_jira_config(
                mock_db,
                UUID("11111111-1111-1111-1111-111111111111"),
                jira_url=None,
                jira_project_key="NEW",
            )

        # jira_url untouched since None was passed, jira_project_key updated
        self.assertEqual(updated.jira_url, "https://old.example.com")
        self.assertEqual(updated.jira_project_key, "NEW")

    def test_update_project_jira_config_raises_not_found_when_missing(self) -> None:
        from unittest.mock import MagicMock, patch

        from app.core.exceptions import AppException
        from app.database.projects_db import update_project_jira_config

        mock_db = MagicMock()

        with patch("app.database.projects_db.get_project_by_id", return_value=None):
            with self.assertRaises(AppException) as context:
                update_project_jira_config(
                    mock_db,
                    UUID("11111111-1111-1111-1111-111111111111"),
                    jira_url="https://jira.example.com",
                )

        self.assertEqual(context.exception.code, "PROJECT_NOT_FOUND")

    def test_update_project_jira_config_rolls_back_on_failure(self) -> None:
        from unittest.mock import MagicMock, patch

        from app.database.projects_db import update_project_jira_config

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="active",
        )
        mock_db = MagicMock()
        mock_db.commit.side_effect = RuntimeError("db down")

        with patch("app.database.projects_db.get_project_by_id", return_value=project):
            with self.assertRaises(DatabaseOperationException):
                update_project_jira_config(
                    mock_db,
                    UUID("11111111-1111-1111-1111-111111111111"),
                    jira_url="https://jira.example.com",
                )

        mock_db.rollback.assert_called_once()

    def test_get_configured_jira_urls_for_user_returns_all_urls(self) -> None:
        from app.database.projects_db import get_configured_jira_urls_for_user

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [
            "https://client-a.atlassian.net",
            "https://client-b.atlassian.net",
        ]

        result = get_configured_jira_urls_for_user(
            mock_db, UUID("11111111-1111-1111-1111-111111111111")
        )

        self.assertEqual(
            result, ["https://client-a.atlassian.net", "https://client-b.atlassian.net"]
        )

    def test_get_configured_jira_urls_for_user_returns_empty_when_none_configured(self) -> None:
        from app.database.projects_db import get_configured_jira_urls_for_user

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = get_configured_jira_urls_for_user(
            mock_db, UUID("11111111-1111-1111-1111-111111111111")
        )

        self.assertEqual(result, [])

    def test_get_configured_jira_urls_for_user_wraps_db_errors(self) -> None:
        from app.database.projects_db import get_configured_jira_urls_for_user

        mock_db = MagicMock()
        mock_db.execute.side_effect = RuntimeError("db down")

        with self.assertRaises(DatabaseOperationException):
            get_configured_jira_urls_for_user(
                mock_db, UUID("11111111-1111-1111-1111-111111111111")
            )

    def test_row_to_project_without_lead_name(self) -> None:
        row = {
            "id": UUID("11111111-1111-1111-1111-111111111111"),
            "programme_id": UUID("22222222-2222-2222-2222-222222222222"),
            "name": "Migration",
            "description": None,
            "status": "active",
            "lead_id": None,
            "start_date": None,
            "created_at": "2026-01-01T00:00:00Z",
            "last_modified": "2026-01-01T00:00:00Z",
        }

        project = _row_to_project(row)

        self.assertFalse(hasattr(project, "lead_name"))

    def test_update_project_entry_updates_lead_id(self) -> None:
        from app.database.projects_db import update_project_entry

        project = Project(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            status="active",
        )
        mock_db = MagicMock()
        new_lead_id = UUID("33333333-3333-3333-3333-333333333333")

        with patch("app.database.projects_db.get_project_by_id", return_value=project):
            updated = update_project_entry(
                mock_db,
                UUID("11111111-1111-1111-1111-111111111111"),
                lead_id=new_lead_id,
            )

        self.assertEqual(updated.lead_id, new_lead_id)


class GetProjectApproversTests(unittest.TestCase):
    """Verify how a project's manager and lead are resolved into approvers."""

    project_id = UUID("11111111-1111-1111-1111-111111111111")

    def _db_returning(self, row):
        db = MagicMock()
        db.execute.return_value.first.return_value = row
        return db

    def test_returns_manager_first_then_lead(self) -> None:
        row = SimpleNamespace(
            manager_name="Pat Manager",
            manager_email="pat@example.com",
            lead_name="Lee Lead",
            lead_email="lee@example.com",
        )

        approvers = get_project_approvers(self._db_returning(row), self.project_id)

        self.assertEqual(
            approvers,
            [
                ("Project Manager", "Pat Manager", "pat@example.com"),
                ("Project Lead", "Lee Lead", "lee@example.com"),
            ],
        )

    def test_manager_only_when_no_lead_assigned(self) -> None:
        row = SimpleNamespace(
            manager_name="Pat Manager",
            manager_email="pat@example.com",
            lead_name=None,
            lead_email=None,
        )

        approvers = get_project_approvers(self._db_returning(row), self.project_id)

        self.assertEqual(approvers, [("Project Manager", "Pat Manager", "pat@example.com")])

    def test_deduplicates_when_manager_and_lead_are_the_same_user(self) -> None:
        row = SimpleNamespace(
            manager_name="Pat Manager",
            manager_email="Pat@Example.com",
            lead_name="Pat Manager",
            lead_email="pat@example.com",
        )

        approvers = get_project_approvers(self._db_returning(row), self.project_id)

        self.assertEqual(approvers, [("Project Manager", "Pat Manager", "Pat@Example.com")])

    def test_returns_empty_for_unknown_project(self) -> None:
        approvers = get_project_approvers(self._db_returning(None), self.project_id)

        self.assertEqual(approvers, [])

    def test_drops_an_assignee_whose_role_cannot_approve(self) -> None:
        """Assignment alone is not enough: the decision endpoint requires
        story:approve, so an assignee without it would be offered, emailed and
        shown the request only to be refused 403 on the request assigned to them."""
        import app.models  # noqa: F401
        from app.models.epics_model import Epic  # noqa: F401
        from app.models.user_stories_model import UserStory  # noqa: F401

        db = self._db_returning(None)
        get_project_approvers(db, self.project_id)

        statement = db.execute.call_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))

        self.assertEqual(sql.count("'story:approve'"), 2)
        self.assertIn("role_permissions", sql)

    def test_wraps_query_failure(self) -> None:
        db = MagicMock()
        db.execute.side_effect = RuntimeError("boom")

        with self.assertRaises(DatabaseOperationException):
            get_project_approvers(db, self.project_id)
