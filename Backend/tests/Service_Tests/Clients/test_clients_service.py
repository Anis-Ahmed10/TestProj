"""Tests for the client management service."""

import unittest
from datetime import UTC, datetime
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.core.exceptions import AppException, InvalidInputError
from app.schemas.clients import ClientUpdate
from app.services.clients import ClientService


class _ClientRecord:
    """Simple client-like object used by service tests."""

    def __init__(
        self,
        *,
        client_id: int = 11,
        name: str = "Acme Corp",
        industry: str = "Finance",
        location: str = "Mumbai",
        contact: str = "Alex Doe",
        status: str = "active",
        manager_id: str | None = None,
    ) -> None:
        timestamp = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)
        self.id = client_id
        self.name = name
        self.industry = industry
        self.location = location
        self.contact = contact
        self.status = status
        self.manager_id = manager_id
        self.created_at = timestamp
        self.last_modified = timestamp


class ClientServiceTests(unittest.TestCase):
    """Verify client detail, update, and archive behavior."""

    def setUp(self) -> None:
        self.service = ClientService(db=object())
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

        self._visible_programme_ids_patcher = patch(
            "app.services.clients.get_visible_programme_ids", return_value=None
        )
        self._visible_programme_ids_patcher.start()
        self.addCleanup(self._visible_programme_ids_patcher.stop)

    @patch("app.services.clients.get_programs_by_client_id", return_value=[])
    @patch("app.services.clients.get_client_by_name")
    def test_get_client_details_trims_client_name(self, mock_get_client_by_name, _) -> None:
        mock_get_client_by_name.return_value = _ClientRecord()

        result = self.service.get_client_details("  Acme Corp  ", self.current_user_id)

        self.assertEqual(result.name, "Acme Corp")
        mock_get_client_by_name.assert_called_once_with(self.service.db, "Acme Corp")

    @patch("app.services.clients.get_programs_by_client_id", return_value=[])
    @patch("app.services.clients.get_client_by_name")
    def test_get_client_details_uses_name_lookup(self, mock_get_client_by_name, _) -> None:
        mock_get_client_by_name.return_value = _ClientRecord()

        result = self.service.get_client_details("Acme Corp", self.current_user_id)

        self.assertEqual(result.name, "Acme Corp")
        self.assertEqual(result.programs, [])
        mock_get_client_by_name.assert_called_once_with(self.service.db, "Acme Corp")

    @patch("app.services.clients.get_programs_by_client_id", return_value=[])
    @patch("app.services.clients.get_client_by_name")
    def test_get_client_details_accepts_uuid_client_id(self, mock_get_client_by_name, _) -> None:
        client_record = _ClientRecord(client_id=uuid4())
        mock_get_client_by_name.return_value = client_record

        result = self.service.get_client_details("Acme Corp", self.current_user_id)

        self.assertEqual(result.id, client_record.id)

    @patch(
        "app.services.clients.get_programs_by_client_id",
        return_value=[
            {
                "id": uuid4(),
                "name": "Claims Modernization",
                "description": "Migration programme for core claims workflows.",
            }
        ],
    )
    @patch("app.services.clients.get_client_by_name")
    def test_get_client_details_returns_associated_programs(
        self,
        mock_get_client_by_name,
        _,
    ) -> None:
        mock_get_client_by_name.return_value = _ClientRecord(client_id=uuid4())

        result = self.service.get_client_details("Acme Corp", self.current_user_id)

        self.assertEqual(len(result.programs), 1)
        self.assertEqual(result.programs[0].name, "Claims Modernization")
        self.assertEqual(
            result.programs[0].description,
            "Migration programme for core claims workflows.",
        )

    @patch("app.services.clients.get_client_by_name", return_value=None)
    def test_get_client_details_raises_not_found(self, mock_get_client_by_name) -> None:
        with self.assertRaises(AppException) as context:
            self.service.get_client_details("Missing Client", self.current_user_id)

        self.assertEqual(context.exception.code, "NOT_FOUND")
        self.assertEqual(context.exception.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(str(context.exception), "Client Missing Client not found")
        mock_get_client_by_name.assert_called_once_with(self.service.db, "Missing Client")

    def test_get_client_details_rejects_blank_client_name(self) -> None:
        with self.assertRaises(InvalidInputError) as context:
            self.service.get_client_details("   ", self.current_user_id)

        self.assertEqual(str(context.exception), "Client name is required")

    @patch("app.services.clients.get_programs_by_client_id", side_effect=RuntimeError("boom"))
    @patch("app.services.clients.get_client_by_name")
    @patch("app.services.clients.logger.exception")
    def test_get_client_details_wraps_unexpected_errors(
        self,
        mock_logger_exception,
        mock_get_client_by_name,
        _,
    ) -> None:
        mock_get_client_by_name.return_value = _ClientRecord()

        with self.assertRaises(AppException) as context:
            self.service.get_client_details("Acme Corp", self.current_user_id)

        self.assertEqual(context.exception.code, "CLIENT_DETAILS_FETCH_FAILED")
        self.assertEqual(str(context.exception), "Failed to fetch client details")
        mock_logger_exception.assert_called_once_with("get_client_details_unexpected_failure")

    @patch("app.services.clients.update_client_in_db")
    @patch("app.services.clients.check_client_name_exists", return_value=True)
    @patch("app.services.clients.get_client_by_name")
    def test_update_client_rejects_duplicate_name(
        self,
        mock_get_client_by_name,
        mock_check_client_name_exists,
        mock_update_client_in_db,
    ) -> None:
        mock_get_client_by_name.return_value = _ClientRecord()

        with self.assertRaises(InvalidInputError) as context:
            self.service.update_client(
                "Acme Corp", ClientUpdate(name="Existing Client"), self.current_user_id
            )

        self.assertEqual(str(context.exception), "Client name already exists")
        mock_check_client_name_exists.assert_called_once_with(
            self.service.db,
            "Existing Client",
            exclude_name="Acme Corp",
        )
        mock_update_client_in_db.assert_not_called()

    @patch("app.services.clients.get_client_by_name", return_value=None)
    def test_update_client_raises_not_found(self, mock_get_client_by_name) -> None:
        with self.assertRaises(AppException) as context:
            self.service.update_client(
                "Missing Client", ClientUpdate(industry="Insurance"), self.current_user_id
            )

        self.assertEqual(context.exception.code, "NOT_FOUND")
        self.assertEqual(str(context.exception), "Client Missing Client not found")
        mock_get_client_by_name.assert_called_once_with(self.service.db, "Missing Client")

    @patch("app.services.clients.get_user_by_id", return_value=None)
    @patch("app.services.clients.update_client_in_db")
    @patch("app.services.clients.check_client_name_exists", return_value=False)
    @patch("app.services.clients.get_client_by_name")
    def test_update_client_uses_current_name_lookup(
        self,
        mock_get_client_by_name,
        mock_check_client_name_exists,
        mock_update_client_in_db,
        mock_get_user_by_id,
    ) -> None:
        current_client = _ClientRecord()
        updated_client = _ClientRecord(name="Acme Global", industry="Insurance")
        mock_get_client_by_name.return_value = current_client
        mock_update_client_in_db.return_value = updated_client

        result = self.service.update_client(
            "Acme Corp",
            ClientUpdate(name="  Acme Global  ", industry="Insurance"),
            self.current_user_id,
        )

        self.assertEqual(result.name, "Acme Global")
        mock_check_client_name_exists.assert_called_once_with(
            self.service.db,
            "Acme Global",
            exclude_name="Acme Corp",
        )
        mock_update_client_in_db.assert_called_once_with(
            self.service.db,
            "Acme Corp",
            {"name": "Acme Global", "industry": "Insurance"},
        )

    @patch("app.services.clients.update_client_in_db")
    @patch("app.services.clients.check_client_name_exists")
    @patch("app.services.clients.get_client_by_name")
    def test_update_client_passes_status_to_db_update(
        self,
        mock_get_client_by_name,
        mock_check_client_name_exists,
        mock_update_client_in_db,
    ) -> None:
        current_client = _ClientRecord()
        updated_client = _ClientRecord(status="inactive")
        mock_get_client_by_name.return_value = current_client
        mock_update_client_in_db.return_value = updated_client

        result = self.service.update_client(
            "Acme Corp", ClientUpdate(status="inactive"), self.current_user_id
        )

        self.assertEqual(result.status, "inactive")
        mock_check_client_name_exists.assert_not_called()
        mock_update_client_in_db.assert_called_once_with(
            self.service.db,
            "Acme Corp",
            {"status": "inactive"},
        )

    @patch("app.services.clients.update_client_in_db")
    @patch("app.services.clients.check_client_name_exists")
    @patch("app.services.clients.get_client_by_name")
    def test_update_client_skips_name_uniqueness_check_when_name_missing(
        self,
        mock_get_client_by_name,
        mock_check_client_name_exists,
        mock_update_client_in_db,
    ) -> None:
        current_client = _ClientRecord()
        mock_get_client_by_name.return_value = current_client
        mock_update_client_in_db.return_value = current_client

        self.service.update_client(
            "Acme Corp", ClientUpdate(industry="Insurance"), self.current_user_id
        )

        mock_check_client_name_exists.assert_not_called()
        mock_update_client_in_db.assert_called_once_with(
            self.service.db,
            "Acme Corp",
            {"industry": "Insurance"},
        )

    @patch("app.services.clients.update_client_in_db")
    @patch("app.services.clients.check_client_name_exists")
    @patch("app.services.clients.get_client_by_name")
    def test_update_client_skips_name_uniqueness_check_when_name_unchanged(
        self,
        mock_get_client_by_name,
        mock_check_client_name_exists,
        mock_update_client_in_db,
    ) -> None:
        current_client = _ClientRecord()
        mock_get_client_by_name.return_value = current_client
        mock_update_client_in_db.return_value = current_client

        self.service.update_client(
            "Acme Corp", ClientUpdate(name="Acme Corp"), self.current_user_id
        )

        mock_check_client_name_exists.assert_not_called()
        mock_update_client_in_db.assert_called_once_with(
            self.service.db,
            "Acme Corp",
            {"name": "Acme Corp"},
        )

    @patch("app.services.clients.get_visible_client_ids")
    @patch("app.services.clients.get_client_by_name")
    def test_update_client_raises_forbidden_when_outside_visible_ids(
        self, mock_get_client_by_name, mock_get_visible
    ) -> None:
        client = _ClientRecord()
        mock_get_client_by_name.return_value = client
        mock_get_visible.return_value = {uuid4()}  # client.id not in this set

        with self.assertRaises(AppException) as context:
            self.service.update_client(
                "Acme Corp", ClientUpdate(industry="Insurance"), self.current_user_id
            )

        self.assertEqual(context.exception.code, "FORBIDDEN")
        self.assertEqual(context.exception.status_code, HTTPStatus.FORBIDDEN)

    @patch("app.services.clients.soft_delete_client")
    @patch("app.services.clients.count_active_projects_by_client", return_value=0)
    @patch("app.services.clients.get_client_by_name")
    @patch("app.services.clients.logger.info")
    def test_archive_client_returns_archived_name(
        self,
        mock_logger_info,
        mock_get_client_by_name,
        mock_count_active_projects,
        mock_soft_delete_client,
    ) -> None:
        client_record = _ClientRecord(name="Acme Corp", status="active")
        mock_get_client_by_name.return_value = client_record
        mock_soft_delete_client.return_value = _ClientRecord(
            name="Acme Corp",
            status="archived",
        )

        result = self.service.archive_client("  Acme Corp  ", self.current_user_id)

        self.assertEqual(result, "Acme Corp")
        mock_get_client_by_name.assert_called_once_with(self.service.db, "Acme Corp")
        mock_count_active_projects.assert_called_once_with(self.service.db, client_record.id)
        mock_soft_delete_client.assert_called_once_with(self.service.db, "Acme Corp")
        mock_logger_info.assert_called_once_with("client_archived")

    @patch("app.services.clients.soft_delete_client")
    @patch("app.services.clients.count_active_projects_by_client", return_value=0)
    @patch("app.services.clients.get_client_by_name", return_value=None)
    @patch("app.services.clients.logger.warning")
    def test_archive_client_reraises_application_errors_with_warning(
        self,
        mock_logger_warning,
        mock_get_client_by_name,
        mock_count_active_projects,
        mock_soft_delete_client,
    ) -> None:
        # get_client_by_name returns None → service raises NOT_FOUND AppException
        with self.assertRaises(AppException) as context:
            self.service.archive_client("  Missing Client  ", self.current_user_id)

        self.assertEqual(context.exception.code, "NOT_FOUND")
        self.assertEqual(str(context.exception), "Client Missing Client not found")
        mock_logger_warning.assert_called_once_with("archive_client_failed")
        mock_soft_delete_client.assert_not_called()

    @patch("app.services.clients.get_visible_client_ids")
    @patch("app.services.clients.get_client_by_name")
    def test_archive_client_raises_forbidden_when_outside_visible_ids(
        self, mock_get_client_by_name, mock_get_visible
    ) -> None:
        client = _ClientRecord()
        mock_get_client_by_name.return_value = client
        mock_get_visible.return_value = {uuid4()}  # client.id not in this set

        with self.assertRaises(AppException) as context:
            self.service.archive_client("Acme Corp", self.current_user_id)

        self.assertEqual(context.exception.code, "FORBIDDEN")
        self.assertEqual(context.exception.status_code, HTTPStatus.FORBIDDEN)

    @patch("app.services.clients.update_client_in_db", side_effect=RuntimeError("boom"))
    @patch("app.services.clients.check_client_name_exists", return_value=False)
    @patch("app.services.clients.get_client_by_name")
    @patch("app.services.clients.logger.exception")
    def test_update_client_wraps_unexpected_errors(
        self,
        mock_logger_exception,
        mock_get_client_by_name,
        mock_check_client_name_exists,
        _,
    ) -> None:
        mock_get_client_by_name.return_value = _ClientRecord()

        with self.assertRaises(AppException) as context:
            self.service.update_client(
                "Acme Corp", ClientUpdate(industry="Insurance"), self.current_user_id
            )

        self.assertEqual(context.exception.code, "CLIENT_UPDATE_FAILED")
        self.assertEqual(str(context.exception), "Failed to update client")
        mock_check_client_name_exists.assert_not_called()
        mock_logger_exception.assert_called_once_with("update_client_unexpected_failure")

    @patch("app.services.clients.soft_delete_client", side_effect=RuntimeError("boom"))
    @patch("app.services.clients.count_active_projects_by_client", return_value=0)
    @patch("app.services.clients.get_client_by_name")
    @patch("app.services.clients.logger.exception")
    def test_archive_client_wraps_unexpected_errors(
        self,
        mock_logger_exception,
        mock_get_client_by_name,
        mock_count_active_projects,
        _,
    ) -> None:
        mock_get_client_by_name.return_value = _ClientRecord(name="Acme Corp")

        with self.assertRaises(AppException) as context:
            self.service.archive_client("Acme Corp", self.current_user_id)

        self.assertEqual(context.exception.code, "CLIENT_ARCHIVE_FAILED")
        self.assertEqual(str(context.exception), "Failed to archive client")
        mock_logger_exception.assert_called_once_with("archive_client_unexpected_failure")

    @patch("app.services.clients.soft_delete_client")
    @patch("app.services.clients.count_active_projects_by_client", return_value=2)
    @patch("app.services.clients.get_client_by_name")
    @patch("app.services.clients.logger.info")
    def test_archive_client_blocked_when_active_projects_exist(
        self,
        mock_logger_info,
        mock_get_client_by_name,
        mock_count_active_projects,
        mock_soft_delete_client,
    ) -> None:
        mock_get_client_by_name.return_value = _ClientRecord(name="Acme Corp")

        with self.assertRaises(AppException) as context:
            self.service.archive_client("Acme Corp", self.current_user_id)

        self.assertEqual(context.exception.code, "CLIENT_DELETE_BLOCKED")
        self.assertEqual(context.exception.status_code, 409)
        mock_logger_info.assert_called_with("client_delete_blocked_active_projects")
        mock_soft_delete_client.assert_not_called()

    @patch("app.services.clients.get_user_by_id")
    @patch("app.services.clients.get_programs_by_client_id", return_value=[])
    @patch("app.services.clients.get_client_by_name")
    def test_get_client_details_resolves_manager_name(
        self,
        mock_get_client_by_name,
        _,
        mock_get_user_by_id,
    ) -> None:
        mgr_id = uuid4()
        mock_get_client_by_name.return_value = _ClientRecord(manager_id=mgr_id)
        mock_get_user_by_id.return_value = SimpleNamespace(name="Manager User")

        result = self.service.get_client_details("Acme Corp", self.current_user_id)

        self.assertEqual(result.manager_name, "Manager User")
        mock_get_user_by_id.assert_called_once_with(self.service.db, mgr_id)

    @patch("app.services.clients.get_user_by_id", return_value=None)
    @patch("app.services.clients.get_programs_by_client_id", return_value=[])
    @patch("app.services.clients.get_client_by_name")
    def test_get_client_details_manager_not_found_returns_none_manager_name(
        self,
        mock_get_client_by_name,
        _,
        mock_get_user_by_id,
    ) -> None:
        mgr_id = uuid4()
        mock_get_client_by_name.return_value = _ClientRecord(manager_id=mgr_id)

        result = self.service.get_client_details("Acme Corp", self.current_user_id)

        self.assertIsNone(result.manager_name)
        mock_get_user_by_id.assert_called_once_with(self.service.db, mgr_id)

    @patch("app.services.clients.get_user_by_id")
    @patch("app.services.clients.update_client_in_db")
    @patch("app.services.clients.get_client_by_name")
    def test_update_client_raises_manager_not_found(
        self,
        mock_get_client_by_name,
        mock_update_client_in_db,
        mock_get_user_by_id,
    ) -> None:
        mgr_id = uuid4()
        mock_get_client_by_name.return_value = _ClientRecord()
        mock_get_user_by_id.return_value = None

        with self.assertRaises(AppException) as context:
            self.service.update_client(
                "Acme Corp", ClientUpdate(manager_id=mgr_id), self.current_user_id
            )

        self.assertEqual(context.exception.code, "MANAGER_NOT_FOUND")
        self.assertEqual(context.exception.status_code, 400)
        mock_update_client_in_db.assert_not_called()

    @patch("app.services.clients.get_user_by_id")
    @patch("app.services.clients.update_client_in_db")
    @patch("app.services.clients.get_client_by_name")
    def test_update_client_with_valid_manager_attaches_manager_name(
        self,
        mock_get_client_by_name,
        mock_update_client_in_db,
        mock_get_user_by_id,
    ) -> None:
        mgr_id = uuid4()
        mock_get_client_by_name.return_value = _ClientRecord()
        mock_get_user_by_id.return_value = SimpleNamespace(name="Alice Manager")
        updated_rec = _ClientRecord(manager_id=mgr_id)
        mock_update_client_in_db.return_value = updated_rec

        result = self.service.update_client(
            "Acme Corp", ClientUpdate(manager_id=mgr_id), self.current_user_id
        )

        self.assertEqual(result.manager_name, "Alice Manager")

    @patch("app.services.clients.get_user_by_id")
    @patch("app.services.clients.update_client_in_db")
    @patch("app.services.clients.get_client_by_name")
    def test_update_client_when_updated_manager_user_missing(
        self,
        mock_get_client_by_name,
        mock_update_client_in_db,
        mock_get_user_by_id,
    ) -> None:
        mgr_id = uuid4()
        mock_get_client_by_name.return_value = _ClientRecord()
        # First call for validation returns manager;
        # second call for updated manager name returns None.
        mock_get_user_by_id.side_effect = [SimpleNamespace(name="Alice Manager"), None]
        updated_rec = _ClientRecord(manager_id=mgr_id)
        mock_update_client_in_db.return_value = updated_rec

        result = self.service.update_client(
            "Acme Corp", ClientUpdate(manager_id=mgr_id), self.current_user_id
        )

        self.assertIsNone(result.manager_name)

    @patch("app.services.clients.get_visible_client_ids")
    @patch("app.services.clients.get_client_by_name")
    def test_get_client_details_raises_forbidden_when_outside_visible_ids(
        self, mock_get_client_by_name, mock_get_visible_client_ids
    ) -> None:
        client = _ClientRecord()
        mock_get_client_by_name.return_value = client
        mock_get_visible_client_ids.return_value = {uuid4()}  # client.id not in this set

        with self.assertRaises(AppException) as context:
            self.service.get_client_details("Acme Corp", self.current_user_id)

        self.assertEqual(context.exception.code, "FORBIDDEN")
        self.assertEqual(context.exception.status_code, HTTPStatus.FORBIDDEN)

    @patch("app.services.clients.get_visible_counts_by_client")
    @patch("app.services.clients.get_programs_by_client_id", return_value=[])
    @patch("app.services.clients.get_client_by_name")
    def test_get_client_details_overrides_counts_with_scoped_counts(
        self, mock_get_client_by_name, _, mock_get_visible_counts
    ) -> None:
        client = _ClientRecord()
        mock_get_client_by_name.return_value = client
        mock_get_visible_counts.return_value = {
            client.id: {"programmes_count": 1, "projects_count": 2, "active_members_count": 3}
        }

        result = self.service.get_client_details("Acme Corp", self.current_user_id)

        self.assertEqual(result.programmes_count, 1)
        self.assertEqual(result.projects_count, 2)
        self.assertEqual(result.active_members_count, 3)

    @patch("app.services.clients.get_visible_programme_ids")
    @patch("app.services.clients.get_programs_by_client_id")
    @patch("app.services.clients.get_client_by_name")
    def test_get_client_details_filters_programs_by_visible_programme_ids(
        self, mock_get_client_by_name, mock_get_programs, mock_get_visible_programmes
    ) -> None:
        visible_id = uuid4()
        hidden_id = uuid4()
        mock_get_client_by_name.return_value = _ClientRecord()
        mock_get_programs.return_value = [
            {"id": visible_id, "name": "Visible Programme", "description": None},
            {"id": hidden_id, "name": "Hidden Programme", "description": None},
        ]
        mock_get_visible_programmes.return_value = {visible_id}

        result = self.service.get_client_details("Acme Corp", self.current_user_id)

        self.assertEqual(len(result.programs), 1)
        self.assertEqual(result.programs[0].name, "Visible Programme")
