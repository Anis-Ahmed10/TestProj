"""Tests for project business rules."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import patch as _patch
from uuid import UUID, uuid4

from app.core.exceptions import AppException
from app.schemas.projects import ProjectCreateRequest, ProjectUpdateRequest
from app.services.projects import ProjectsService


class ProjectServiceTests(unittest.TestCase):
    """Verify project duplicate-name handling."""

    def setUp(self) -> None:
        self.service = ProjectsService(db=object())
        self.current_user_id = uuid4()

    @patch("app.services.projects.check_project_name_exists")
    @patch("app.services.projects.create_project_entry")
    @patch("app.services.projects.get_programme")
    def test_create_project_rejects_missing_programme(
        self,
        mock_get_programme,
        mock_create_project_entry,
        mock_check_project_name_exists,
    ) -> None:
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
            description="Migration workstream.",
        )
        mock_get_programme.side_effect = AppException(
            code="PROGRAMME_NOT_FOUND", status_code=404, message="err"
        )

        with self.assertRaises(AppException) as context:
            self.service.create_project(self.service.db, payload, self.current_user_id)

        self.assertEqual(context.exception.code, "PROGRAMME_NOT_FOUND")
        self.assertEqual(context.exception.status_code, HTTPStatus.NOT_FOUND)
        mock_get_programme.assert_called_once_with(self.service.db, payload.programme_id)
        mock_check_project_name_exists.assert_not_called()
        mock_create_project_entry.assert_not_called()

    @patch("app.services.projects.get_visible_programme_ids", return_value=None)
    @patch("app.services.projects.check_project_name_exists", return_value=True)
    @patch("app.services.projects.create_project_entry")
    @patch("app.services.projects.get_programme")
    def test_create_project_rejects_duplicate_name_in_same_programme(
        self,
        mock_get_programme,
        mock_create_project_entry,
        mock_check_project_name_exists,
        mock_get_visible,
    ) -> None:
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
            description="Migration workstream.",
        )
        mock_get_programme.return_value = SimpleNamespace(id=1)

        with self.assertRaises(AppException) as context:
            self.service.create_project(self.service.db, payload, self.current_user_id)

        self.assertEqual(context.exception.code, "PROJECT_ALREADY_EXISTS")
        self.assertEqual(context.exception.status_code, HTTPStatus.CONFLICT)
        mock_check_project_name_exists.assert_called_once_with(
            self.service.db,
            programme_id=payload.programme_id,
            name="Migration",
        )
        mock_create_project_entry.assert_not_called()

    @patch("app.services.projects.get_visible_programme_ids", return_value=None)
    @patch("app.services.projects.check_project_name_exists", return_value=False)
    @patch("app.services.projects.create_project_entry")
    @patch("app.services.projects.get_programme")
    def test_create_project_allows_same_name_for_other_programme_context(
        self,
        mock_get_programme,
        mock_create_project_entry,
        mock_check_project_name_exists,
        mock_get_visible,
    ) -> None:
        payload = ProjectCreateRequest(
            programme_id="22222222-2222-2222-2222-222222222222",
            name="Migration",
            description="Migration workstream.",
        )
        created_project = SimpleNamespace(
            id=10,
            programme_id=payload.programme_id,
            name="Migration",
            description="Migration workstream.",
            status="Active",
            start_date=None,
            lead_id=None,
            lead_name="Unassigned",
            created_at=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
            last_modified=datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc),
        )
        mock_create_project_entry.return_value = created_project
        mock_get_programme.return_value = SimpleNamespace(id=2)

        response = self.service.create_project(self.service.db, payload, self.current_user_id)

        self.assertEqual(response.name, "Migration")
        mock_check_project_name_exists.assert_called_once_with(
            self.service.db,
            programme_id=payload.programme_id,
            name="Migration",
        )
        mock_create_project_entry.assert_called_once_with(
            self.service.db,
            programme_id=payload.programme_id,
            name="Migration",
            description="Migration workstream.",
            status="active",
            lead_id=None,
            start_date=None,
        )

    @patch("app.services.projects.get_visible_programme_ids", return_value=None)
    @patch("app.services.projects.check_project_name_exists", return_value=False)
    @patch("app.services.projects.create_project_entry")
    @patch("app.services.projects.get_programme", return_value=SimpleNamespace(id=2))
    def test_create_project_reraises_app_exception_from_create(
        self,
        mock_get_programme,
        mock_create_project_entry,
        mock_check_project_name_exists,
        mock_get_visible,
    ) -> None:
        payload = ProjectCreateRequest(
            programme_id="22222222-2222-2222-2222-222222222222",
            name="Migration",
            description=None,
        )
        expected = AppException(code="CUSTOM", message="custom", status_code=409)
        mock_create_project_entry.side_effect = expected

        with self.assertRaises(AppException) as context:
            self.service.create_project(self.service.db, payload, self.current_user_id)

        self.assertIs(context.exception, expected)

    @patch("app.services.projects.get_visible_programme_ids", return_value=None)
    @patch("app.services.projects.check_project_name_exists", return_value=False)
    @patch("app.services.projects.create_project_entry", side_effect=RuntimeError("db down"))
    @patch("app.services.projects.get_programme", return_value=SimpleNamespace(id=2))
    def test_create_project_wraps_unexpected_create_failure(
        self,
        mock_get_programme,
        mock_create_project_entry,
        mock_check_project_name_exists,
        mock_get_visible,
    ) -> None:
        payload = ProjectCreateRequest(
            programme_id="22222222-2222-2222-2222-222222222222",
            name="Migration",
            description=None,
        )

        with self.assertRaises(AppException) as context:
            self.service.create_project(self.service.db, payload, self.current_user_id)

        self.assertEqual(context.exception.code, "PROJECT_CREATE_FAILED")
        self.assertEqual(context.exception.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    @patch("app.services.projects.get_visible_project_ids", return_value=None)
    @patch("app.services.projects.list_all_projects")
    def test_list_projects_returns_all_active_projects(
        self,
        mock_list_all_projects,
        mock_get_visible_project_ids,
    ) -> None:
        created_project = SimpleNamespace(
            id=10,
            programme_id="22222222-2222-2222-2222-222222222222",
            name="Migration",
            description="Migration workstream.",
            status="active",
            start_date=None,
            created_at=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
            last_modified=datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc),
            programme_name="Programme A",
            client_id=UUID("33333333-3333-3333-3333-333333333333"),
            client_name="Client A",
        )
        mock_list_all_projects.return_value = [created_project]

        response = self.service.list_projects(self.service.db, self.current_user_id)

        self.assertEqual(len(response), 1)
        self.assertEqual(response[0].name, "Migration")
        self.assertEqual(response[0].programme_name, "Programme A")
        self.assertEqual(response[0].client_id, UUID("33333333-3333-3333-3333-333333333333"))
        self.assertEqual(response[0].client_name, "Client A")
        mock_list_all_projects.assert_called_once_with(self.service.db)
        mock_get_visible_project_ids.assert_called_once_with(self.service.db, self.current_user_id)

    @patch("app.services.projects.get_visible_project_ids", return_value={10})
    @patch("app.services.projects.list_all_projects")
    def test_list_projects_filters_by_visible_ids(
        self,
        mock_list_all_projects,
        mock_get_visible_project_ids,
    ) -> None:
        project_visible = SimpleNamespace(
            id=10,
            programme_id="22222222-2222-2222-2222-222222222222",
            name="Visible Migration",
            description=None,
            status="active",
            start_date=None,
            created_at=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
            last_modified=datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc),
        )
        project_hidden = SimpleNamespace(
            id=99,
            programme_id="22222222-2222-2222-2222-222222222222",
            name="Hidden Project",
            description=None,
            status="active",
            start_date=None,
            created_at=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
            last_modified=datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc),
        )
        mock_list_all_projects.return_value = [project_visible, project_hidden]

        response = self.service.list_projects(self.service.db, self.current_user_id)

        self.assertEqual(len(response), 1)
        self.assertEqual(response[0].name, "Visible Migration")

    @patch("app.services.projects.list_all_projects")
    def test_list_projects_reraises_app_exception(
        self,
        mock_list_all_projects,
    ) -> None:
        expected = AppException(code="CUSTOM", message="custom", status_code=409)
        mock_list_all_projects.side_effect = expected

        with self.assertRaises(AppException) as context:
            self.service.list_projects(self.service.db, self.current_user_id)

        self.assertIs(context.exception, expected)

    @patch("app.services.projects.list_all_projects", side_effect=RuntimeError("db down"))
    def test_list_projects_wraps_unexpected_failure(
        self,
        mock_list_all_projects,
    ) -> None:
        with self.assertRaises(AppException) as context:
            self.service.list_projects(self.service.db, self.current_user_id)

        self.assertEqual(context.exception.code, "PROJECT_LIST_FAILED")
        self.assertEqual(context.exception.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    # ── update_project ──────────────────────────────────────────────────────

    @patch("app.services.projects.get_visible_project_ids", return_value=None)
    @patch("app.services.projects.update_project_entry")
    @patch("app.services.projects.check_project_name_exists", return_value=False)
    @patch("app.services.projects.get_project_by_id")
    def test_update_project_returns_updated_response(
        self, mock_get_project, mock_check, mock_update, mock_get_visible
    ) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        project = SimpleNamespace(
            id=project_id,
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Old Name",
            description=None,
            status="active",
            start_date=None,
            lead_id=None,
            lead_name="Unassigned",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_modified=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        updated = SimpleNamespace(
            id=project_id,
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="New Name",
            description=None,
            status="active",
            start_date=None,
            lead_id=None,
            lead_name="Unassigned",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_modified=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        mock_get_project.return_value = project
        mock_update.return_value = updated

        result = self.service.update_project(
            self.service.db,
            project_id,
            ProjectUpdateRequest(name="New Name"),
            self.current_user_id,
        )

        self.assertEqual(result.name, "New Name")

    @patch("app.services.projects.get_visible_project_ids", return_value=None)
    @patch("app.services.projects.check_project_name_exists", return_value=True)
    @patch("app.services.projects.get_project_by_id")
    def test_update_project_rejects_duplicate_name(
        self, mock_get_project, mock_check, mock_get_visible
    ) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        project = SimpleNamespace(
            id=project_id,
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Old Name",
            description=None,
            status="active",
        )
        mock_get_project.return_value = project

        with self.assertRaises(AppException) as context:
            self.service.update_project(
                self.service.db,
                project_id,
                ProjectUpdateRequest(name="Duplicate"),
                self.current_user_id,
            )

        self.assertEqual(context.exception.code, "PROJECT_ALREADY_EXISTS")

    @patch("app.services.projects.get_project_by_id", return_value=None)
    def test_update_project_raises_not_found(self, _) -> None:
        with self.assertRaises(AppException) as context:
            self.service.update_project(
                self.service.db,
                UUID("11111111-1111-1111-1111-111111111111"),
                ProjectUpdateRequest(name="X"),
                self.current_user_id,
            )
        self.assertEqual(context.exception.code, "PROJECT_NOT_FOUND")

    @patch("app.services.projects.get_project_by_id", side_effect=RuntimeError("db down"))
    def test_update_project_wraps_unexpected_failure(self, _) -> None:
        with self.assertRaises(AppException) as context:
            self.service.update_project(
                self.service.db,
                UUID("11111111-1111-1111-1111-111111111111"),
                ProjectUpdateRequest(name="X"),
                self.current_user_id,
            )
        self.assertEqual(context.exception.code, "PROJECT_UPDATE_FAILED")

    @patch("app.services.projects.get_project_by_id")
    def test_update_project_reraises_app_exception(self, mock_get) -> None:
        expected = AppException(code="PROJECT_NOT_FOUND", message="missing", status_code=404)
        mock_get.side_effect = expected

        with self.assertRaises(AppException) as context:
            self.service.update_project(
                self.service.db,
                UUID("11111111-1111-1111-1111-111111111111"),
                ProjectUpdateRequest(name="X"),
                self.current_user_id,
            )
        self.assertIs(context.exception, expected)

    @patch("app.services.projects.get_visible_project_ids", return_value=None)
    @patch("app.services.projects.check_project_name_exists")
    @patch("app.services.projects.get_project_by_id")
    def test_update_project_skips_name_check_when_unchanged(
        self, mock_get_project, mock_check, mock_get_visible
    ) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        project = SimpleNamespace(
            id=project_id,
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Same Name",
            description=None,
            status="active",
            start_date=None,
            lead_id=None,
            lead_name="Unassigned",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_modified=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        mock_get_project.return_value = project

        with _patch("app.services.projects.update_project_entry", return_value=project):
            self.service.update_project(
                self.service.db,
                project_id,
                ProjectUpdateRequest(name="Same Name"),
                self.current_user_id,
            )

        mock_check.assert_not_called()

    # ── delete_project ──────────────────────────────────────────────────────

    @patch("app.services.projects.get_visible_project_ids", return_value=None)
    @patch("app.services.projects.soft_delete_project_entry")
    def test_delete_project_returns_deleted_payload(
        self, mock_soft_delete, mock_get_visible
    ) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        deleted = SimpleNamespace(id=project_id, name="Migration")
        mock_soft_delete.return_value = deleted

        result = self.service.delete_project(self.service.db, project_id, self.current_user_id)

        self.assertEqual(result["deleted_project_id"], str(project_id))
        self.assertEqual(result["deleted_project_name"], "Migration")

    @patch("app.services.projects.get_visible_project_ids", return_value=None)
    @patch("app.services.projects.soft_delete_project_entry")
    def test_delete_project_raises_not_found(self, mock_soft_delete, mock_get_visible) -> None:
        mock_soft_delete.side_effect = AppException(
            code="PROJECT_NOT_FOUND",
            message="Project not found",
            status_code=404,
        )
        with self.assertRaises(AppException) as context:
            self.service.delete_project(
                self.service.db, UUID("11111111-1111-1111-1111-111111111111"), self.current_user_id
            )
        self.assertEqual(context.exception.code, "PROJECT_NOT_FOUND")

    @patch("app.services.projects.get_visible_project_ids", return_value=None)
    @patch("app.services.projects.soft_delete_project_entry", side_effect=RuntimeError("db down"))
    def test_delete_project_wraps_unexpected_failure(self, _, mock_get_visible) -> None:
        with self.assertRaises(AppException) as context:
            self.service.delete_project(
                self.service.db, UUID("11111111-1111-1111-1111-111111111111"), self.current_user_id
            )
        self.assertEqual(context.exception.code, "PROJECT_DELETE_FAILED")

    @patch("app.services.projects.get_visible_project_ids", return_value=None)
    @patch("app.services.projects.soft_delete_project_entry")
    def test_delete_project_reraises_app_exception(
        self, mock_soft_delete, mock_get_visible
    ) -> None:
        expected = AppException(code="PROJECT_NOT_FOUND", message="missing", status_code=404)
        mock_soft_delete.side_effect = expected

        with self.assertRaises(AppException) as context:
            self.service.delete_project(
                self.service.db, UUID("11111111-1111-1111-1111-111111111111"), self.current_user_id
            )
        self.assertIs(context.exception, expected)

    @patch("app.services.projects.get_visible_programme_ids", return_value=None)
    @patch("app.services.projects.get_user_by_id")
    @patch("app.services.projects.check_project_name_exists", return_value=False)
    @patch("app.services.projects.get_programme", return_value=SimpleNamespace(id=2))
    def test_create_project_raises_when_lead_not_found(
        self, mock_get_programme, mock_check, mock_get_user, mock_get_visible
    ) -> None:
        mock_get_user.return_value = None
        payload = ProjectCreateRequest(
            programme_id="22222222-2222-2222-2222-222222222222",
            name="Migration",
            lead_id="33333333-3333-3333-3333-333333333333",
        )

        with self.assertRaises(AppException) as context:
            self.service.create_project(self.service.db, payload, self.current_user_id)

        self.assertEqual(context.exception.code, "LEAD_NOT_FOUND")

    @patch("app.services.projects.get_visible_project_ids", return_value=None)
    @patch("app.services.projects.get_user_by_id")
    @patch("app.services.projects.get_project_by_id")
    def test_update_project_raises_when_lead_not_found(
        self, mock_get_project, mock_get_user, mock_get_visible
    ) -> None:

        project_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_get_project.return_value = SimpleNamespace(
            id=project_id,
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            description=None,
            status="active",
        )
        mock_get_user.return_value = None

        with self.assertRaises(AppException) as context:
            self.service.update_project(
                self.service.db,
                project_id,
                ProjectUpdateRequest(lead_id="33333333-3333-3333-3333-333333333333"),
                self.current_user_id,
            )

        self.assertEqual(context.exception.code, "LEAD_NOT_FOUND")

    @patch("app.services.projects.get_visible_project_ids", return_value=None)
    @patch("app.services.projects.update_project_entry")
    @patch("app.services.projects.get_user_by_id")
    @patch("app.services.projects.get_project_by_id")
    def test_update_project_attaches_lead_name_when_lead_found(
        self, mock_get_project, mock_get_user, mock_update, mock_get_visible
    ) -> None:

        project_id = UUID("11111111-1111-1111-1111-111111111111")
        new_lead_id = UUID("33333333-3333-3333-3333-333333333333")
        mock_get_project.return_value = SimpleNamespace(
            id=project_id,
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            description=None,
            status="active",
        )
        mock_get_user.return_value = SimpleNamespace(id=new_lead_id, name="Jane Lead")
        mock_update.return_value = SimpleNamespace(
            id=project_id,
            programme_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Migration",
            description=None,
            status="active",
            start_date=None,
            lead_id=new_lead_id,
            created_at=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
            last_modified=datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc),
        )

        result = self.service.update_project(
            self.service.db,
            project_id,
            ProjectUpdateRequest(lead_id=new_lead_id),
            self.current_user_id,
        )

        self.assertEqual(result.lead_name, "Jane Lead")

    @patch("app.services.projects.get_visible_project_ids")
    @patch("app.services.projects.get_project_by_id")
    def test_update_project_raises_forbidden_when_outside_visible_ids(
        self, mock_get_project, mock_get_visible
    ) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_get_project.return_value = SimpleNamespace(
            id=project_id, programme_id=UUID("22222222-2222-2222-2222-222222222222"), name="X"
        )
        mock_get_visible.return_value = {uuid4()}  # project_id not in this set

        with self.assertRaises(AppException) as context:
            self.service.update_project(
                self.service.db, project_id, ProjectUpdateRequest(name="Y"), self.current_user_id
            )

        self.assertEqual(context.exception.code, "FORBIDDEN")
        self.assertEqual(context.exception.status_code, HTTPStatus.FORBIDDEN)

    @patch("app.services.projects.get_visible_programme_ids", return_value=None)
    @patch("app.services.projects.get_user_by_id")
    @patch("app.services.projects.check_project_name_exists", return_value=False)
    @patch("app.services.projects.create_project_entry")
    @patch("app.services.projects.get_programme", return_value=SimpleNamespace(id=2))
    def test_create_project_with_lead_user_found(
        self,
        mock_get_programme,
        mock_create_project_entry,
        mock_check_project_name_exists,
        mock_get_user_by_id,
        mock_get_visible,
    ) -> None:
        lead_id = UUID("33333333-3333-3333-3333-333333333333")
        payload = ProjectCreateRequest(
            programme_id="22222222-2222-2222-2222-222222222222",
            name="Migration",
            description="Migration workstream.",
            lead_id=lead_id,
        )
        mock_get_user_by_id.return_value = SimpleNamespace(id=lead_id, name="Jane Lead")
        created_project = SimpleNamespace(
            id=10,
            programme_id=payload.programme_id,
            name="Migration",
            description="Migration workstream.",
            status="active",
            start_date=None,
            lead_id=lead_id,
            created_at=datetime(2026, 5, 26, 10, 30, tzinfo=timezone.utc),
            last_modified=datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc),
        )
        mock_create_project_entry.return_value = created_project

        response = self.service.create_project(self.service.db, payload, self.current_user_id)

        self.assertEqual(response.name, "Migration")
        self.assertEqual(response.lead_name, "Jane Lead")
        mock_get_user_by_id.assert_called_once_with(self.service.db, lead_id)

    @patch("app.services.projects.get_visible_programme_ids")
    @patch("app.services.projects.get_programme", return_value=SimpleNamespace(id=2))
    def test_create_project_raises_forbidden_when_programme_not_visible(
        self, mock_get_programme, mock_get_visible
    ) -> None:
        payload = ProjectCreateRequest(
            programme_id="22222222-2222-2222-2222-222222222222", name="Migration"
        )
        mock_get_visible.return_value = {uuid4()}  # payload.programme_id not in this set

        with self.assertRaises(AppException) as context:
            self.service.create_project(self.service.db, payload, self.current_user_id)

        self.assertEqual(context.exception.code, "FORBIDDEN")
        self.assertEqual(context.exception.status_code, HTTPStatus.FORBIDDEN)

    @patch("app.services.projects.get_visible_project_ids")
    def test_delete_project_raises_forbidden_when_outside_visible_ids(
        self, mock_get_visible
    ) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        mock_get_visible.return_value = {uuid4()}  # project_id not in this set

        with self.assertRaises(AppException) as context:
            self.service.delete_project(self.service.db, project_id, self.current_user_id)

        self.assertEqual(context.exception.code, "FORBIDDEN")
        self.assertEqual(context.exception.status_code, HTTPStatus.FORBIDDEN)
