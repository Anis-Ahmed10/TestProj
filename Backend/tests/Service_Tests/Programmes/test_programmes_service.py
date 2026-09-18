"""Tests for programme business rules."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from app.core.exceptions import AppException
from app.schemas.programmes import ProgrammeCreateRequest, ProgrammeUpdateRequest
from app.services.programmes import ProgrammesService


class ProgrammeServiceTests(unittest.TestCase):
    """Verify programme duplicate-name handling."""

    def setUp(self) -> None:
        self.service = ProgrammesService(db=object())
        self.current_user_id = uuid4()

    @patch("app.services.programmes.get_visible_client_ids", return_value=None)
    @patch("app.services.programmes.get_client_by_id", return_value=SimpleNamespace(id=1))
    @patch("app.services.programmes.check_programme_name_exists", return_value=True)
    @patch("app.services.programmes.create_programme_entry")
    def test_create_programme_rejects_duplicate_name_in_same_client(
        self,
        mock_create_programme_entry,
        mock_check_programme_name_exists,
        mock_get_client_by_id,
        mock_get_visible,
    ) -> None:
        payload = ProgrammeCreateRequest(
            client_id="11111111-1111-1111-1111-111111111111",
            name="Modernisation",
            description="Claims modernisation programme.",
        )

        with self.assertRaises(AppException) as context:
            self.service.create_programme(self.service.db, payload, self.current_user_id)

        self.assertEqual(context.exception.code, "PROGRAMME_ALREADY_EXISTS")
        self.assertEqual(context.exception.status_code, HTTPStatus.CONFLICT)
        mock_get_client_by_id.assert_called_once_with(self.service.db, payload.client_id)
        mock_check_programme_name_exists.assert_called_once_with(
            self.service.db,
            client_id=payload.client_id,
            name="Modernisation",
        )
        mock_create_programme_entry.assert_not_called()

    @patch("app.services.programmes.get_client_by_id", return_value=None)
    def test_create_programme_rejects_missing_client(self, mock_get_client_by_id) -> None:
        payload = ProgrammeCreateRequest(
            client_id="11111111-1111-1111-1111-111111111111",
            name="Modernisation",
            description="Claims modernisation programme.",
        )

        with self.assertRaises(AppException) as context:
            self.service.create_programme(self.service.db, payload, self.current_user_id)

        self.assertEqual(context.exception.code, "CLIENT_NOT_FOUND")
        self.assertEqual(context.exception.status_code, HTTPStatus.NOT_FOUND)
        mock_get_client_by_id.assert_called_once_with(self.service.db, payload.client_id)

    @patch("app.services.programmes.get_visible_client_ids", return_value=None)
    @patch("app.services.programmes.get_client_by_id", return_value=SimpleNamespace(id=2))
    @patch("app.services.programmes.check_programme_name_exists", return_value=False)
    @patch("app.services.programmes.create_programme_entry")
    @patch("app.services.programmes.get_programme_with_details_db")
    def test_create_programme_allows_same_name_for_different_client_context(
        self,
        mock_get_details,
        mock_create_programme_entry,
        mock_check_programme_name_exists,
        mock_get_client_by_id,
        mock_get_visible,
    ) -> None:
        payload = ProgrammeCreateRequest(
            client_id="22222222-2222-2222-2222-222222222222",
            name="Modernisation",
            description="Claims modernisation programme.",
        )
        ts = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
        created_programme = SimpleNamespace(
            id=UUID("10000000-0000-0000-0000-000000000000"),
            client_id=payload.client_id,
            name="Modernisation",
            description="Claims modernisation programme.",
            status="active",
            created_at=ts,
            last_modified=ts,
        )
        mock_create_programme_entry.return_value = created_programme
        mock_get_details.return_value = (created_programme, 0, "John Doe")

        response = self.service.create_programme(self.service.db, payload, self.current_user_id)

        self.assertEqual(response.name, "Modernisation")
        self.assertEqual(response.manager_name, "John Doe")
        mock_get_client_by_id.assert_called_once_with(self.service.db, payload.client_id)

    @patch("app.services.programmes.get_visible_client_ids", return_value=None)
    @patch("app.services.programmes.get_client_by_id", return_value=SimpleNamespace(id=2))
    @patch("app.services.programmes.check_programme_name_exists", return_value=False)
    @patch("app.services.programmes.create_programme_entry")
    def test_create_programme_reraises_app_exception_from_create(
        self,
        mock_create_programme_entry,
        mock_check_programme_name_exists,
        mock_get_client_by_id,
        mock_get_visible,
    ) -> None:
        payload = ProgrammeCreateRequest(
            client_id="22222222-2222-2222-2222-222222222222",
            name="Modernisation",
            description=None,
        )
        expected = AppException(code="CUSTOM", message="custom", status_code=409)
        mock_create_programme_entry.side_effect = expected

        with self.assertRaises(AppException) as context:
            self.service.create_programme(self.service.db, payload, self.current_user_id)

        self.assertIs(context.exception, expected)
        mock_get_client_by_id.assert_called_once_with(self.service.db, payload.client_id)
        mock_check_programme_name_exists.assert_called_once()

    @patch("app.services.programmes.get_visible_client_ids", return_value=None)
    @patch("app.services.programmes.get_client_by_id", return_value=SimpleNamespace(id=2))
    @patch("app.services.programmes.check_programme_name_exists", return_value=False)
    @patch("app.services.programmes.create_programme_entry", side_effect=RuntimeError("db down"))
    def test_create_programme_wraps_unexpected_create_failure(
        self,
        mock_create_programme_entry,
        mock_check_programme_name_exists,
        mock_get_client_by_id,
        mock_get_visible,
    ) -> None:
        payload = ProgrammeCreateRequest(
            client_id="22222222-2222-2222-2222-222222222222",
            name="Modernisation",
            description=None,
        )

        with self.assertRaises(AppException) as context:
            self.service.create_programme(self.service.db, payload, self.current_user_id)

        self.assertEqual(context.exception.code, "PROGRAMME_CREATE_FAILED")
        self.assertEqual(context.exception.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        mock_get_client_by_id.assert_called_once_with(self.service.db, payload.client_id)

    @patch("app.services.programmes.get_visible_client_ids", return_value=None)
    @patch("app.services.programmes.get_client_by_id", return_value=SimpleNamespace(id=2))
    @patch("app.services.programmes.check_programme_name_exists", return_value=False)
    @patch("app.services.programmes.create_programme_entry")
    @patch("app.services.programmes.get_programme_with_details_db", return_value=None)
    def test_create_programme_fallback_when_details_returns_none(
        self,
        mock_get_details,
        mock_create_programme_entry,
        mock_check_programme_name_exists,
        mock_get_client_by_id,
        mock_get_visible,
    ) -> None:
        payload = ProgrammeCreateRequest(
            client_id="22222222-2222-2222-2222-222222222222",
            name="Modernisation",
            description="Claims modernisation programme.",
        )
        ts = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
        created_programme = SimpleNamespace(
            id=UUID("10000000-0000-0000-0000-000000000000"),
            client_id=payload.client_id,
            name="Modernisation",
            description="Claims modernisation programme.",
            status="active",
            created_at=ts,
            last_modified=ts,
        )
        mock_create_programme_entry.return_value = created_programme

        response = self.service.create_programme(self.service.db, payload, self.current_user_id)

        self.assertEqual(response.name, "Modernisation")

    @patch("app.services.programmes.get_visible_client_ids")
    @patch("app.services.programmes.get_client_by_id", return_value=SimpleNamespace(id=2))
    def test_create_programme_raises_forbidden_when_client_not_visible(
        self, mock_get_client_by_id, mock_get_visible
    ) -> None:
        payload = ProgrammeCreateRequest(
            client_id="22222222-2222-2222-2222-222222222222", name="Modernisation"
        )
        mock_get_visible.return_value = {uuid4()}  # payload.client_id not in this set

        with self.assertRaises(AppException) as context:
            self.service.create_programme(self.service.db, payload, self.current_user_id)

        self.assertEqual(context.exception.code, "FORBIDDEN")
        self.assertEqual(context.exception.status_code, HTTPStatus.FORBIDDEN)

    @patch("app.services.programmes.get_visible_project_ids", return_value=None)
    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.list_projects_by_programme_id")
    @patch("app.services.programmes.get_programme_with_details_db")
    def test_get_programme_details_returns_projects_for_programme(
        self,
        mock_get_details,
        mock_list_projects_by_programme_id,
        mock_vis_progs,
        mock_vis_projs,
    ) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        client_id = UUID("22222222-2222-2222-2222-222222222222")
        ts = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)
        programme = SimpleNamespace(
            id=programme_id,
            client_id=client_id,
            name="Modernisation",
            description="Claims modernisation programme.",
            status="active",
            created_at=ts,
            last_modified=ts,
        )
        project = SimpleNamespace(
            id=UUID("33333333-3333-3333-3333-333333333333"),
            programme_id=programme_id,
            name="Migration",
            description="Migration workstream.",
            status="active",
            start_date=date(2026, 6, 1),
            lead_id=None,
            lead_name=None,
            created_at=ts,
            last_modified=ts,
        )
        # Mock returns 3-tuple: (programme, project_count, manager_name)
        mock_get_details.return_value = (programme, 1, None)
        mock_list_projects_by_programme_id.return_value = [project]

        response = self.service.get_programme_details(
            self.service.db, programme_id, self.current_user_id
        )

        self.assertEqual(response.id, programme_id)
        self.assertEqual(response.client_id, client_id)
        self.assertEqual(len(response.projects), 1)
        self.assertEqual(response.projects[0].name, "Migration")
        self.assertIsNone(response.manager_name)
        mock_get_details.assert_called_once_with(self.service.db, programme_id)
        mock_list_projects_by_programme_id.assert_called_once_with(
            self.service.db,
            programme_id,
        )

    @patch("app.services.programmes.count_visible_projects_by_programme")
    @patch("app.services.programmes.get_visible_project_ids")
    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.list_all_programmes")
    def test_list_programmes_scopes_project_count_for_lead_or_engineer(
        self,
        mock_list_all_programmes,
        mock_get_vis_progs,
        mock_get_vis_projs,
        mock_count_visible_projects,
    ) -> None:
        prog1_id = UUID("11111111-1111-1111-1111-111111111111")
        prog2_id = UUID("22222222-2222-2222-2222-222222222222")
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)

        def _programme(pid):
            return SimpleNamespace(
                id=pid,
                client_id=UUID("33333333-3333-3333-3333-333333333333"),
                name=f"Programme {pid}",
                description=None,
                status="active",
                created_at=ts,
                last_modified=ts,
            )

        mock_list_all_programmes.return_value = [
            SimpleNamespace(Programme=_programme(prog1_id), project_count=5),
            SimpleNamespace(Programme=_programme(prog2_id), project_count=5),
        ]

        visible_project_ids = {uuid4(), uuid4()}
        mock_get_vis_projs.return_value = visible_project_ids
        mock_count_visible_projects.return_value = {prog1_id: 2, prog2_id: 0}

        result = self.service.list_programmes(self.service.db, self.current_user_id)

        self.assertEqual(len(result), 2)
        by_id = {r.id: r for r in result}
        self.assertEqual(by_id[prog1_id].project_count, 2)
        self.assertEqual(by_id[prog2_id].project_count, 0)
        mock_count_visible_projects.assert_called_once_with(self.service.db, visible_project_ids)

    @patch("app.services.programmes.get_programme_with_details_db")
    @patch("app.services.programmes.get_visible_programme_ids")
    def test_get_programme_details_raises_forbidden_when_access_denied(
        self, mock_get_vis_progs, mock_get_details
    ) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_get_details.return_value = (SimpleNamespace(id=programme_id), 0, None)
        mock_get_vis_progs.return_value = {UUID("88888888-8888-8888-8888-888888888888")}

        with self.assertRaises(AppException) as context:
            self.service.get_programme_details(self.service.db, programme_id, self.current_user_id)

        self.assertEqual(context.exception.code, "FORBIDDEN")
        self.assertEqual(context.exception.status_code, HTTPStatus.FORBIDDEN)

    @patch("app.services.programmes.get_programme_with_details_db", return_value=None)
    def test_get_programme_details_raises_when_programme_missing(
        self,
        mock_get_details,
    ) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")

        with self.assertRaises(AppException) as context:
            self.service.get_programme_details(self.service.db, programme_id, self.current_user_id)

        self.assertEqual(context.exception.status_code, 404)
        mock_get_details.assert_called_once_with(self.service.db, programme_id)

    @patch(
        "app.services.programmes.get_programme_with_details_db",
        side_effect=RuntimeError("db down"),
    )
    def test_get_programme_details_wraps_unexpected_failure(
        self,
        mock_get_programme,
    ) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")

        with self.assertRaises(AppException) as context:
            self.service.get_programme_details(self.service.db, programme_id, self.current_user_id)

        self.assertEqual(context.exception.code, "PROGRAMME_DETAILS_FETCH_FAILED")
        self.assertEqual(context.exception.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    @patch("app.services.programmes.get_visible_project_ids", return_value=None)
    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.list_projects_by_programme_id", return_value=[])
    @patch("app.services.programmes.get_programme_with_details_db")
    def test_get_programme_details_resolves_manager_name(
        self,
        mock_get_details,
        mock_list_projects,
        mock_vis_progs,
        mock_vis_projs,
    ) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        client_id = UUID("22222222-2222-2222-2222-222222222222")
        ts = datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc)

        programme = SimpleNamespace(
            id=programme_id,
            client_id=client_id,
            name="Modernisation",
            description=None,
            status="active",
            created_at=ts,
            last_modified=ts,
        )
        mock_get_details.return_value = (programme, 0, "Alice Manager")

        response = self.service.get_programme_details(
            self.service.db, programme_id, self.current_user_id
        )

        self.assertEqual(response.manager_name, "Alice Manager")
        mock_get_details.assert_called_once_with(self.service.db, programme_id)

    @patch("app.services.programmes.get_programme")
    def test_delete_programme_raises_when_programme_missing(
        self,
        mock_get_programme,
    ) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_get_programme.side_effect = AppException(
            code="PROGRAMME_NOT_FOUND", status_code=404, message="err"
        )

        with self.assertRaises(AppException) as context:
            self.service.delete_programme(self.service.db, programme_id, self.current_user_id)

        self.assertEqual(context.exception.code, "PROGRAMME_NOT_FOUND")

        self.assertEqual(context.exception.status_code, HTTPStatus.NOT_FOUND)
        mock_get_programme.assert_called_once_with(self.service.db, programme_id)

    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.count_active_projects_by_programme", return_value=2)
    @patch("app.services.programmes.get_programme")
    @patch("app.services.programmes.delete_programme_entry")
    def test_delete_programme_blocks_when_active_projects_exist(
        self,
        mock_delete_programme_entry,
        mock_get_programme,
        mock_count_active_projects_by_programme,
        mock_get_vis_progs,
    ) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_get_programme.return_value = SimpleNamespace(id=programme_id)

        with self.assertRaises(AppException) as context:
            self.service.delete_programme(self.service.db, programme_id, self.current_user_id)

        self.assertEqual(context.exception.code, "PROGRAMME_DELETE_BLOCKED")
        self.assertEqual(context.exception.status_code, HTTPStatus.CONFLICT)
        mock_count_active_projects_by_programme.assert_called_once_with(
            self.service.db,
            programme_id,
        )
        mock_delete_programme_entry.assert_not_called()

    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.count_active_projects_by_programme", return_value=0)
    @patch("app.services.programmes.get_programme")
    @patch("app.services.programmes.delete_programme_entry")
    def test_delete_programme_returns_deleted_programme_payload(
        self,
        mock_delete_programme_entry,
        mock_get_programme,
        mock_count_active_projects_by_programme,
        mock_get_vis_progs,
    ) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_get_programme.return_value = SimpleNamespace(id=programme_id, name="Modernisation")
        mock_delete_programme_entry.return_value = SimpleNamespace(
            id=programme_id,
            name="Modernisation",
        )

        response = self.service.delete_programme(
            self.service.db, programme_id, self.current_user_id
        )

        self.assertEqual(
            response,
            {
                "deleted_programme_id": str(programme_id),
                "deleted_programme_name": "Modernisation",
            },
        )
        mock_count_active_projects_by_programme.assert_called_once_with(
            self.service.db,
            programme_id,
        )
        mock_delete_programme_entry.assert_called_once_with(self.service.db, programme_id)

    @patch("app.services.programmes.get_programme", side_effect=RuntimeError("db down"))
    def test_delete_programme_wraps_unexpected_failure(
        self,
        mock_get_programme,
    ) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")

        with self.assertRaises(AppException) as context:
            self.service.delete_programme(self.service.db, programme_id, self.current_user_id)

        self.assertEqual(context.exception.code, "PROGRAMME_DELETE_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    @patch("app.services.programmes.get_visible_programme_ids")
    @patch("app.services.programmes.get_programme")
    def test_delete_programme_raises_forbidden_when_access_denied(
        self,
        mock_get_programme,
        mock_get_vis_progs,
    ) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_get_programme.return_value = SimpleNamespace(id=programme_id)
        mock_get_vis_progs.return_value = {UUID("88888888-8888-8888-8888-888888888888")}

        with self.assertRaises(AppException) as context:
            self.service.delete_programme(self.service.db, programme_id, self.current_user_id)

        self.assertEqual(context.exception.code, "FORBIDDEN")
        self.assertEqual(context.exception.status_code, HTTPStatus.FORBIDDEN)

    # ── list_programmes ─────────────────────────────────────────────────────

    @patch("app.services.programmes.get_visible_project_ids", return_value=None)
    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.list_all_programmes")
    def test_list_programmes_returns_all_active(
        self,
        mock_list_all_programmes,
        mock_get_vis_progs,
        mock_get_vis_projs,
    ) -> None:
        ts = datetime(2026, 5, 26, tzinfo=timezone.utc)
        programme = SimpleNamespace(
            id=1,
            client_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Modernisation",
            description="Desc",
            status="active",
            created_at=ts,
            last_modified=ts,
        )
        row = SimpleNamespace(Programme=programme, project_count=2)
        mock_list_all_programmes.return_value = [row]

        result = self.service.list_programmes(self.service.db, self.current_user_id)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Modernisation")
        self.assertEqual(result[0].project_count, 2)
        mock_list_all_programmes.assert_called_once_with(self.service.db, client_id=None)
        mock_get_vis_progs.assert_called_once_with(self.service.db, self.current_user_id)

    @patch("app.services.programmes.get_visible_project_ids", return_value=None)
    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.list_all_programmes", return_value=[])
    def test_list_programmes_returns_empty_list(
        self, mock_list, mock_get_vis_progs, mock_get_vis_projs
    ) -> None:
        result = self.service.list_programmes(
            self.service.db, self.current_user_id, client_id=None
        )
        self.assertEqual(result, [])

    @patch("app.services.programmes.list_all_programmes")
    def test_list_programmes_reraises_app_exception(self, mock_list) -> None:
        expected = AppException(code="CUSTOM", message="custom", status_code=500)
        mock_list.side_effect = expected

        with self.assertRaises(AppException) as context:
            self.service.list_programmes(self.service.db, self.current_user_id, client_id=None)

        self.assertIs(context.exception, expected)

    @patch("app.services.programmes.list_all_programmes", side_effect=RuntimeError("db down"))
    def test_list_programmes_wraps_unexpected_failure(self, _) -> None:
        with self.assertRaises(AppException) as context:
            self.service.list_programmes(self.service.db, self.current_user_id, client_id=None)

        self.assertEqual(context.exception.code, "PROGRAMME_LIST_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    # ── update_programme ────────────────────────────────────────────────────

    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.get_programme")
    @patch("app.services.programmes.check_programme_name_exists", return_value=False)
    @patch("app.services.programmes.update_programme_entry")
    @patch("app.services.programmes.get_programme_with_details_db")
    def test_update_programme_returns_updated_detail(
        self,
        mock_get_details,
        mock_update_entry,
        mock_check_exists,
        mock_get_programme,
        mock_get_vis_progs,
    ) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        prog_id = UUID("11111111-1111-1111-1111-111111111111")
        existing = SimpleNamespace(
            id=prog_id,
            client_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Old Name",
            description="Old Desc",
            status="active",
            created_at=ts,
            last_modified=ts,
        )
        updated_prog = SimpleNamespace(
            id=prog_id,
            client_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="New Name",
            description="Old Desc",
            status="active",
            created_at=ts,
            last_modified=ts,
        )

        mock_get_programme.return_value = existing
        mock_get_details.return_value = (updated_prog, 2, "Alice Manager")

        payload = ProgrammeUpdateRequest(name="New Name")
        response = self.service.update_programme(
            self.service.db, prog_id, payload, self.current_user_id
        )

        self.assertEqual(response.name, "New Name")
        self.assertEqual(response.manager_name, "Alice Manager")
        self.assertEqual(response.project_count, 2)
        mock_update_entry.assert_called_once()

    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.get_programme")
    @patch("app.services.programmes.check_programme_name_exists", return_value=False)
    @patch("app.services.programmes.update_programme_entry")
    @patch("app.services.programmes.get_programme_with_details_db")
    def test_update_programme_skips_name_check_when_name_unchanged(
        self,
        mock_get_details,
        mock_update_entry,
        mock_check,
        mock_get_programme,
        mock_get_vis_progs,
    ) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        programme = SimpleNamespace(
            id=programme_id,
            client_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Same Name",
            description=None,
            status="active",
            created_at=ts,
            last_modified=ts,
        )
        mock_get_programme.return_value = programme
        mock_get_details.return_value = (programme, 0, None)

        self.service.update_programme(
            self.service.db,
            programme_id,
            ProgrammeUpdateRequest(name="Same Name"),
            self.current_user_id,
        )

        mock_check.assert_not_called()

    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.check_programme_name_exists", return_value=True)
    @patch("app.services.programmes.get_programme")
    def test_update_programme_rejects_duplicate_name(
        self, mock_get_programme, mock_check, mock_get_vis_progs
    ) -> None:
        from app.schemas.programmes import ProgrammeUpdateRequest

        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        programme = SimpleNamespace(
            id=programme_id,
            client_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Old Name",
            description=None,
            status="active",
        )
        mock_get_programme.return_value = programme

        with self.assertRaises(AppException) as context:
            self.service.update_programme(
                self.service.db,
                programme_id,
                ProgrammeUpdateRequest(name="Duplicate"),
                self.current_user_id,
            )

        self.assertEqual(context.exception.code, "PROGRAMME_ALREADY_EXISTS")

    @patch("app.services.programmes.get_programme", side_effect=RuntimeError("db down"))
    def test_update_programme_wraps_unexpected_failure(self, _) -> None:
        from app.schemas.programmes import ProgrammeUpdateRequest

        with self.assertRaises(AppException) as context:
            self.service.update_programme(
                self.service.db,
                UUID("11111111-1111-1111-1111-111111111111"),
                ProgrammeUpdateRequest(name="X"),
                self.current_user_id,
            )
        self.assertEqual(context.exception.code, "PROGRAMME_UPDATE_FAILED")

    @patch("app.services.programmes.get_programme")
    def test_update_programme_reraises_app_exception(self, mock_get_programme) -> None:
        from app.schemas.programmes import ProgrammeUpdateRequest

        expected = AppException(code="PROGRAMME_NOT_FOUND", message="missing", status_code=404)
        mock_get_programme.side_effect = expected

        with self.assertRaises(AppException) as context:
            self.service.update_programme(
                self.service.db,
                UUID("11111111-1111-1111-1111-111111111111"),
                ProgrammeUpdateRequest(name="X"),
                self.current_user_id,
            )

        self.assertIs(context.exception, expected)

    @patch("app.services.programmes.get_visible_project_ids", return_value=None)
    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.list_all_programmes")
    def test_list_programmes_filters_by_client_id(
        self, mock_list_all_programmes, mock_get_vis_progs, mock_get_vis_projs
    ) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        client_id = UUID("22222222-2222-2222-2222-222222222222")
        programme = SimpleNamespace(
            id=1,
            client_id=client_id,
            name="Modernisation",
            description=None,
            status="active",
            created_at=ts,
            last_modified=ts,
        )
        row = SimpleNamespace(Programme=programme, project_count=0)
        mock_list_all_programmes.return_value = [row]

        result = self.service.list_programmes(
            self.service.db, self.current_user_id, client_id=client_id
        )

        self.assertEqual(len(result), 1)
        mock_list_all_programmes.assert_called_once_with(self.service.db, client_id=client_id)

    @patch("app.services.programmes.get_visible_project_ids", return_value=None)
    @patch("app.services.programmes.get_visible_programme_ids")
    @patch("app.services.programmes.list_all_programmes")
    def test_list_programmes_filters_by_visible_programme_ids(
        self,
        mock_list_all_programmes,
        mock_get_vis_progs,
        mock_get_vis_projs,
    ) -> None:
        prog1_id = UUID("11111111-1111-1111-1111-111111111111")
        prog2_id = UUID("22222222-2222-2222-2222-222222222222")

        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        prog1 = SimpleNamespace(
            id=prog1_id,
            client_id=UUID("33333333-3333-3333-3333-333333333333"),
            name="P1",
            description=None,
            status="active",
            created_at=ts,
            last_modified=ts,
        )
        prog2 = SimpleNamespace(
            id=prog2_id,
            client_id=UUID("33333333-3333-3333-3333-333333333333"),
            name="P2",
            description=None,
            status="active",
            created_at=ts,
            last_modified=ts,
        )

        mock_list_all_programmes.return_value = [
            SimpleNamespace(Programme=prog1, project_count=1),
            SimpleNamespace(Programme=prog2, project_count=1),
        ]

        mock_get_vis_progs.return_value = {prog1_id}

        result = self.service.list_programmes(self.service.db, self.current_user_id)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, prog1_id)

    @patch("app.services.programmes.get_visible_programme_ids", return_value=None)
    @patch("app.services.programmes.get_programme")
    @patch("app.services.programmes.check_programme_name_exists", return_value=False)
    @patch("app.services.programmes.update_programme_entry")
    @patch("app.services.programmes.get_programme_with_details_db", return_value=None)
    def test_update_programme_raises_not_found_when_details_returns_none(
        self,
        mock_get_details,
        mock_update_entry,
        mock_check_exists,
        mock_get_programme,
        mock_get_vis_progs,
    ) -> None:
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        prog_id = UUID("11111111-1111-1111-1111-111111111111")
        existing = SimpleNamespace(
            id=prog_id,
            client_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Old Name",
            description="Old Desc",
            status="active",
            created_at=ts,
            last_modified=ts,
        )
        mock_get_programme.return_value = existing
        payload = ProgrammeUpdateRequest(name="New Name")

        with self.assertRaises(AppException) as context:
            self.service.update_programme(self.service.db, prog_id, payload, self.current_user_id)

        self.assertEqual(context.exception.code, "PROGRAMME_NOT_FOUND")
        self.assertEqual(context.exception.status_code, 404)

    @patch("app.services.programmes.get_visible_programme_ids")
    @patch("app.services.programmes.get_programme")
    def test_update_programme_raises_forbidden_when_access_denied(
        self, mock_get_programme, mock_get_vis_progs
    ) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_get_programme.return_value = SimpleNamespace(
            id=programme_id,
            name="Old Name",
            client_id=UUID("22222222-2222-2222-2222-222222222222"),
        )
        mock_get_vis_progs.return_value = {UUID("88888888-8888-8888-8888-888888888888")}

        with self.assertRaises(AppException) as context:
            self.service.update_programme(
                self.service.db,
                programme_id,
                ProgrammeUpdateRequest(name="New Name"),
                self.current_user_id,
            )

        self.assertEqual(context.exception.code, "FORBIDDEN")
        self.assertEqual(context.exception.status_code, HTTPStatus.FORBIDDEN)
