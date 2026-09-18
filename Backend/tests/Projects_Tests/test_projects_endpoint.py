"""Tests for project API routes."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from app.api.v1.endpoints.projects import (
    create_project,
    delete_project,
    get_project_user_stories,
    list_projects,
    update_project,
)
from app.core.exceptions import AppException
from app.schemas.projects import ProjectCreateRequest, ProjectResponse, ProjectUpdateRequest

_DUMMY_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
_DUMMY_PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")


class ProjectEndpointTests(unittest.TestCase):
    """Verify project endpoint response shape."""

    def test_create_project_returns_data_on_success(self) -> None:
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
            description="Migration workstream.",
        )
        mock_data = ProjectResponse(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            programme_id=UUID("11111111-1111-1111-1111-111111111111"),
            name="Migration",
        )
        service = SimpleNamespace(
            db=object(),
            create_project=Mock(return_value=mock_data),
        )

        response = create_project(payload, service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Project created successfully")
        self.assertEqual(response.data, mock_data)
        service.create_project.assert_called_once_with(service.db, payload, _DUMMY_USER_ID)

    def test_create_project_wraps_unexpected_failure(self) -> None:
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
        )
        service = SimpleNamespace(
            db=object(),
            create_project=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            create_project(payload, service, _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "PROJECT_CREATE_FAILED")

    def test_create_project_reraises_app_exception(self) -> None:
        expected = AppException(code="PROJECT_NAME_TAKEN", message="duplicate", status_code=409)
        payload = ProjectCreateRequest(
            programme_id="11111111-1111-1111-1111-111111111111",
            name="Migration",
        )
        service = SimpleNamespace(
            db=object(),
            create_project=Mock(side_effect=expected),
        )

        with self.assertRaises(AppException) as context:
            create_project(payload, service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)

    def test_list_projects_returns_data_on_success(self) -> None:
        mock_data = [
            ProjectResponse(
                id=UUID("11111111-1111-1111-1111-111111111111"),
                programme_id=UUID("11111111-1111-1111-1111-111111111111"),
                name="Migration",
            )
        ]
        service = SimpleNamespace(
            db=object(),
            list_projects=Mock(return_value=mock_data),
        )

        response = list_projects(service, _DUMMY_USER_ID)

        self.assertEqual(response.data, mock_data)

    def test_list_projects_wraps_unexpected_failure(self) -> None:
        service = SimpleNamespace(
            db=object(),
            list_projects=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            list_projects(service, _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "PROJECT_LIST_FAILED")

    def test_list_projects_reraises_app_exception(self) -> None:
        expected = AppException(code="X", message="y", status_code=400)
        service = SimpleNamespace(
            db=object(),
            list_projects=Mock(side_effect=expected),
        )

        with self.assertRaises(AppException) as context:
            list_projects(service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)

    def test_update_project_returns_updated_data(self) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        payload = ProjectUpdateRequest(name="Updated")
        mock_data = Mock()
        service = SimpleNamespace(
            db=object(),
            update_project=Mock(return_value=mock_data),
        )

        response = update_project(project_id, payload, service, _DUMMY_USER_ID)

        self.assertEqual(response.data, mock_data)

    def test_update_project_reraises_forbidden(self) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        payload = ProjectUpdateRequest(name="Updated")
        expected = AppException(
            code="FORBIDDEN", message="You do not have access to this project.", status_code=403
        )
        service = SimpleNamespace(db=object(), update_project=Mock(side_effect=expected))

        with self.assertRaises(AppException) as context:
            update_project(project_id, payload, service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)

    def test_update_project_wraps_unexpected_failure(self) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        payload = ProjectUpdateRequest(name="Updated")
        service = SimpleNamespace(
            db=object(),
            update_project=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            update_project(project_id, payload, service, _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "PROJECT_UPDATE_FAILED")

    def test_update_project_reraises_app_exception(self) -> None:
        expected = AppException(code="PROJECT_NOT_FOUND", message="missing", status_code=404)
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        payload = ProjectUpdateRequest(name="Updated")
        service = SimpleNamespace(
            db=object(),
            update_project=Mock(side_effect=expected),
        )

        with self.assertRaises(AppException) as context:
            update_project(project_id, payload, service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)

    def test_delete_project_returns_success_payload(self) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        service = SimpleNamespace(
            db=object(),
            delete_project=Mock(return_value=None),
        )

        response = delete_project(project_id, service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Project deleted successfully")

    def test_delete_project_reraises_forbidden(self) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        expected = AppException(
            code="FORBIDDEN", message="You do not have access to this project.", status_code=403
        )
        service = SimpleNamespace(db=object(), delete_project=Mock(side_effect=expected))

        with self.assertRaises(AppException) as context:
            delete_project(project_id, service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)

    def test_delete_project_wraps_unexpected_failure(self) -> None:
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        service = SimpleNamespace(
            db=object(),
            delete_project=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            delete_project(project_id, service, _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "PROJECT_DELETE_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    def test_delete_project_reraises_app_exception(self) -> None:
        expected = AppException(code="PROJECT_NOT_FOUND", message="missing", status_code=404)
        project_id = UUID("11111111-1111-1111-1111-111111111111")
        service = SimpleNamespace(
            db=object(),
            delete_project=Mock(side_effect=expected),
        )

        with self.assertRaises(AppException) as context:
            delete_project(project_id, service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)


class ProjectUserStoriesEndpointTests(unittest.TestCase):
    """Verify GET /projects/{project_id}/user-stories."""

    @patch("app.api.v1.endpoints.projects.get_visible_project_ids", return_value=None)
    @patch("app.api.v1.endpoints.projects.get_approved_user_stories_by_project")
    def test_returns_mapped_stories_on_success(
        self, mock_get: Mock, mock_get_visible: Mock
    ) -> None:
        story_1 = Mock(story_key="US-1", title="First story", description="desc one")
        story_2 = Mock(story_key="US-2", title="Second story", description="")
        mock_get.return_value = [story_1, story_2]
        db = object()

        response = get_project_user_stories(_DUMMY_PROJECT_ID, db, _DUMMY_USER_ID)

        mock_get.assert_called_once_with(db, _DUMMY_PROJECT_ID)
        self.assertEqual(response.message, "User stories retrieved successfully")
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0].storyId, "US-1")
        self.assertEqual(response.data[0].jiraIssueKey, "US-1")
        self.assertEqual(response.data[0].title, "First story")
        self.assertEqual(response.data[0].description, "desc one")
        self.assertEqual(response.data[1].description, "")

    @patch("app.api.v1.endpoints.projects.get_visible_project_ids", return_value=None)
    @patch("app.api.v1.endpoints.projects.get_approved_user_stories_by_project")
    def test_returns_empty_list_when_no_approved_stories(
        self, mock_get: Mock, mock_get_visible: Mock
    ) -> None:
        mock_get.return_value = []

        response = get_project_user_stories(_DUMMY_PROJECT_ID, object(), _DUMMY_USER_ID)

        self.assertEqual(response.data, [])

    @patch("app.api.v1.endpoints.projects.get_visible_project_ids", return_value=None)
    @patch("app.api.v1.endpoints.projects.get_approved_user_stories_by_project")
    def test_stories_without_a_story_key_are_skipped(
        self, mock_get: Mock, mock_get_visible: Mock
    ) -> None:
        blank = Mock(story_key="", title="No key story", description="")
        valid = Mock(story_key="US-1", title="Has key", description="")
        mock_get.return_value = [blank, valid]

        response = get_project_user_stories(_DUMMY_PROJECT_ID, object(), _DUMMY_USER_ID)

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0].storyId, "US-1")


class ProjectUserStoriesForbiddenTests(unittest.TestCase):
    """Verify the visibility guard on GET /projects/{project_id}/user-stories."""

    @patch("app.api.v1.endpoints.projects.get_visible_project_ids")
    def test_raises_forbidden_when_project_not_visible(self, mock_get_visible: Mock) -> None:
        mock_get_visible.return_value = {UUID("99999999-9999-9999-9999-999999999999")}

        with self.assertRaises(AppException) as context:
            get_project_user_stories(_DUMMY_PROJECT_ID, object(), _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "FORBIDDEN")
        self.assertEqual(context.exception.status_code, 403)

    @patch("app.api.v1.endpoints.projects.get_visible_project_ids", return_value=None)
    @patch("app.api.v1.endpoints.projects.get_approved_user_stories_by_project", return_value=[])
    def test_allows_when_unrestricted(
        self, mock_get_stories: Mock, mock_get_visible: Mock
    ) -> None:
        response = get_project_user_stories(_DUMMY_PROJECT_ID, object(), _DUMMY_USER_ID)
        self.assertEqual(response.data, [])
