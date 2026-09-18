"""Tests for programme API routes."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

from app.api.v1.endpoints.programmes import (
    create_programme,
    delete_programme,
    get_programme_details,
    get_programme_projects,
    list_programmes,
    update_programme,
)
from app.core.exceptions import AppException
from app.schemas.programmes import (
    ProgrammeCreateRequest,
    ProgrammeDetailResponse,
    ProgrammeUpdateRequest,
)

_DUMMY_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class ProgrammeEndpointTests(unittest.TestCase):
    """Verify programme endpoint response shape."""

    def test_create_programme_returns_message_only_success(self) -> None:
        payload = ProgrammeCreateRequest(
            client_id="11111111-1111-1111-1111-111111111111",
            name="Modernisation",
            description="Claims modernisation programme.",
        )
        service = SimpleNamespace(
            db=object(),
            create_programme=Mock(return_value=Mock()),
        )

        response = create_programme(payload, service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Programme created successfully")
        service.create_programme.assert_called_once_with(service.db, payload, _DUMMY_USER_ID)
        self.assertIsNotNone(response.data)

    def test_create_programme_wraps_unexpected_failure(self) -> None:
        payload = ProgrammeCreateRequest(
            client_id="11111111-1111-1111-1111-111111111111",
            name="Modernisation",
        )
        service = SimpleNamespace(
            db=object(),
            create_programme=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            create_programme(payload, service, _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "PROGRAMME_CREATE_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    def test_create_programme_reraises_app_exception(self) -> None:
        expected = AppException(code="CUSTOM", message="custom", status_code=409)
        payload = ProgrammeCreateRequest(
            client_id="11111111-1111-1111-1111-111111111111",
            name="Modernisation",
        )
        service = SimpleNamespace(
            db=object(),
            create_programme=Mock(side_effect=expected),
        )

        with self.assertRaises(AppException) as context:
            create_programme(payload, service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)

    # ── list_programmes ─────────────────────────────────────────────────────

    def test_list_programmes_returns_success(self) -> None:
        mock_data = [Mock()]
        service = SimpleNamespace(
            db=object(),
            list_programmes=Mock(return_value=mock_data),
        )

        response = list_programmes(service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Programmes retrieved successfully")
        self.assertEqual(response.data, mock_data)
        service.list_programmes.assert_called_once_with(service.db, _DUMMY_USER_ID, client_id=None)

    def test_list_programmes_wraps_unexpected_failure(self) -> None:
        service = SimpleNamespace(
            db=object(),
            list_programmes=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            list_programmes(service, _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "PROGRAMME_LIST_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    def test_list_programmes_reraises_app_exception(self) -> None:
        expected = AppException(code="CUSTOM", message="custom", status_code=500)
        service = SimpleNamespace(
            db=object(),
            list_programmes=Mock(side_effect=expected),
        )

        with self.assertRaises(AppException) as context:
            list_programmes(service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)

    # ── get_programme_details ───────────────────────────────────────────────

    def test_get_programme_details_returns_programme_with_projects(self) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        payload = ProgrammeDetailResponse(
            id=programme_id,
            client_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Modernisation",
            description="Claims modernisation programme.",
            status="active",
            projects=[],
        )
        service = SimpleNamespace(
            db=object(),
            get_programme_details=Mock(return_value=payload),
        )

        response = get_programme_details(programme_id, service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Programme retrieved successfully")
        self.assertEqual(response.data, payload)
        service.get_programme_details.assert_called_once_with(
            service.db, programme_id, _DUMMY_USER_ID
        )

    def test_get_programme_details_wraps_unexpected_failure(self) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        service = SimpleNamespace(
            db=object(),
            get_programme_details=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            get_programme_details(programme_id, service, _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "PROGRAMME_DETAILS_FETCH_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    def test_get_programme_details_reraises_app_exception(self) -> None:
        expected = AppException(code="PROGRAMME_NOT_FOUND", message="missing", status_code=404)
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        service = SimpleNamespace(
            db=object(),
            get_programme_details=Mock(side_effect=expected),
        )

        with self.assertRaises(AppException) as context:
            get_programme_details(programme_id, service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)

    # ── get_programme_projects ──────────────────────────────────────────────

    def test_get_programme_projects_returns_project_list(self) -> None:
        from unittest.mock import patch

        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        project = SimpleNamespace(
            id=UUID("33333333-3333-3333-3333-333333333333"),
            programme_id=programme_id,
            name="Migration",
            description=None,
            status="active",
            start_date=None,
            created_at=None,
            last_modified=None,
        )
        service = SimpleNamespace(db=object())

        with (
            patch(
                "app.api.v1.endpoints.programmes.list_projects_by_programme_id",
                return_value=[project],
            ),
            patch(
                "app.api.v1.endpoints.programmes.get_visible_project_ids",
                return_value=None,
            ),
        ):
            response = get_programme_projects(programme_id, service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Programme projects retrieved successfully")
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0].name, "Migration")

    def test_get_programme_projects_filters_by_visible_project_ids(self) -> None:
        from unittest.mock import patch

        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        visible_project_id = UUID("33333333-3333-3333-3333-333333333333")
        hidden_project_id = UUID("44444444-4444-4444-4444-444444444444")
        visible_project = SimpleNamespace(
            id=visible_project_id,
            programme_id=programme_id,
            name="Visible",
            description=None,
            status="active",
            start_date=None,
            created_at=None,
            last_modified=None,
        )
        hidden_project = SimpleNamespace(
            id=hidden_project_id,
            programme_id=programme_id,
            name="Hidden",
            description=None,
            status="active",
            start_date=None,
            created_at=None,
            last_modified=None,
        )
        service = SimpleNamespace(db=object())

        with (
            patch(
                "app.api.v1.endpoints.programmes.list_projects_by_programme_id",
                return_value=[visible_project, hidden_project],
            ),
            patch(
                "app.api.v1.endpoints.programmes.get_visible_project_ids",
                return_value={visible_project_id},
            ),
        ):
            response = get_programme_projects(programme_id, service, _DUMMY_USER_ID)

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0].name, "Visible")

    def test_get_programme_projects_wraps_unexpected_failure(self) -> None:
        from unittest.mock import patch

        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        service = SimpleNamespace(db=object())

        with patch(
            "app.api.v1.endpoints.programmes.list_projects_by_programme_id",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(AppException) as context:
                get_programme_projects(programme_id, service, _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "PROGRAMME_PROJECTS_FETCH_FAILED")

    def test_get_programme_projects_reraises_app_exception(self) -> None:
        from unittest.mock import patch

        expected = AppException(code="PROGRAMME_NOT_FOUND", message="missing", status_code=404)
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        service = SimpleNamespace(db=object())

        with patch(
            "app.api.v1.endpoints.programmes.list_projects_by_programme_id",
            side_effect=expected,
        ):
            with self.assertRaises(AppException) as context:
                get_programme_projects(programme_id, service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)

    # ── update_programme ────────────────────────────────────────────────────

    def test_update_programme_returns_updated_detail(self) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        payload = ProgrammeUpdateRequest(name="New Name")
        detail = ProgrammeDetailResponse(
            id=programme_id,
            client_id=UUID("22222222-2222-2222-2222-222222222222"),
            name="New Name",
            status="active",
            projects=[],
        )
        service = SimpleNamespace(
            db=object(),
            update_programme=Mock(return_value=detail),
        )

        response = update_programme(programme_id, payload, service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Programme updated successfully")
        self.assertEqual(response.data, detail)
        service.update_programme.assert_called_once_with(
            service.db, programme_id, payload, _DUMMY_USER_ID
        )

    def test_update_programme_wraps_unexpected_failure(self) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        service = SimpleNamespace(
            db=object(),
            update_programme=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            update_programme(
                programme_id, ProgrammeUpdateRequest(name="X"), service, _DUMMY_USER_ID
            )

        self.assertEqual(context.exception.code, "PROGRAMME_UPDATE_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    def test_update_programme_reraises_app_exception(self) -> None:
        expected = AppException(code="PROGRAMME_NOT_FOUND", message="missing", status_code=404)
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        service = SimpleNamespace(
            db=object(),
            update_programme=Mock(side_effect=expected),
        )

        with self.assertRaises(AppException) as context:
            update_programme(
                programme_id, ProgrammeUpdateRequest(name="X"), service, _DUMMY_USER_ID
            )

        self.assertIs(context.exception, expected)

    # ── delete_programme ────────────────────────────────────────────────────

    def test_delete_programme_returns_success_payload(self) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        deleted = {
            "deleted_programme_id": str(programme_id),
            "deleted_programme_name": "Modernisation",
        }
        service = SimpleNamespace(
            db=object(),
            delete_programme=Mock(return_value=deleted),
        )

        response = delete_programme(programme_id, service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Programme deleted successfully")
        self.assertEqual(response.data, deleted)
        service.delete_programme.assert_called_once_with(service.db, programme_id, _DUMMY_USER_ID)

    def test_delete_programme_wraps_unexpected_failure(self) -> None:
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        service = SimpleNamespace(
            db=object(),
            delete_programme=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            delete_programme(programme_id, service, _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "PROGRAMME_DELETE_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    def test_delete_programme_reraises_app_exception(self) -> None:
        expected = AppException(code="PROGRAMME_NOT_FOUND", message="missing", status_code=404)
        programme_id = UUID("11111111-1111-1111-1111-111111111111")
        service = SimpleNamespace(
            db=object(),
            delete_programme=Mock(side_effect=expected),
        )

        with self.assertRaises(AppException) as context:
            delete_programme(programme_id, service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)

    def test_list_programmes_filters_by_client_id(self) -> None:
        from uuid import UUID

        client_id = UUID("22222222-2222-2222-2222-222222222222")
        mock_data = [Mock()]
        service = SimpleNamespace(
            db=object(),
            list_programmes=Mock(return_value=mock_data),
        )

        response = list_programmes(service, client_id=client_id, current_user_id=_DUMMY_USER_ID)

        self.assertEqual(response.message, "Programmes retrieved successfully")
        service.list_programmes.assert_called_once_with(
            service.db, _DUMMY_USER_ID, client_id=client_id
        )

    def test_list_programmes_no_client_id_returns_all(self) -> None:
        mock_data = [Mock(), Mock()]
        service = SimpleNamespace(
            db=object(),
            list_programmes=Mock(return_value=mock_data),
        )

        response = list_programmes(service, client_id=None, current_user_id=_DUMMY_USER_ID)

        self.assertEqual(len(response.data), 2)
        service.list_programmes.assert_called_once_with(service.db, _DUMMY_USER_ID, client_id=None)
