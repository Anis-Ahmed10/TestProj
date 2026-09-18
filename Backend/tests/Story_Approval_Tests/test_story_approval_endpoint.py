"""Tests for story approval API routes."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

from app.api.v1.endpoints.story_approvals import (
    decide_approval,
    get_review_queue,
    list_project_approvals,
    submit_for_approval,
)
from app.core.exceptions import AppException
from app.schemas.story_approval import (
    ReviewQueueCounts,
    ReviewQueueResponse,
    StoryApprovalDecisionRequest,
    StoryApprovalDecisionResponse,
    StoryApprovalRecord,
    StoryApprovalSubmitRequest,
    StoryApprovalSubmitResponse,
)

_DUMMY_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
_DUMMY_PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
_DUMMY_STORY_ID = "STORY-42"
_DUMMY_APPROVAL_ID = UUID("33333333-3333-3333-3333-333333333333")


def _make_approval_record(**overrides):
    """Return a StoryApprovalRecord with sensible defaults."""
    from datetime import datetime, timezone

    defaults = {
        "id": _DUMMY_APPROVAL_ID,
        "user_story_id": _DUMMY_STORY_ID,
        "project_id": _DUMMY_PROJECT_ID,
        "submitted_by": _DUMMY_USER_ID,
        "reviewer_email": "reviewer@example.com",
        "status": "pending",
        "submitted_at": datetime.now(timezone.utc),
        "decided_at": None,
    }
    defaults.update(overrides)
    return StoryApprovalRecord(**defaults)


class SubmitForApprovalEndpointTests(unittest.TestCase):
    """Verify submit_for_approval endpoint response shape."""

    def test_submit_returns_data_on_success(self) -> None:
        record = _make_approval_record()
        mock_data = StoryApprovalSubmitResponse(
            submitted_count=1,
            skipped_count=0,
            approval_records=[record],
        )
        payload = StoryApprovalSubmitRequest(
            epics=[
                {
                    "epicId": "EPIC-1",
                    "epicTitle": "Epic 1",
                    "user_stories": [
                        {
                            "storyId": _DUMMY_STORY_ID,
                            "storyTitle": "Title",
                            "description": "desc",
                            "acceptanceCriteria": "ac",
                            "issue_type": "story",
                        }
                    ],
                }
            ],
            project_id=_DUMMY_PROJECT_ID,
            reviewer_emails=["reviewer@example.com"],
        )
        service = SimpleNamespace(
            db=object(),
            submit_for_approval=Mock(return_value=mock_data),
        )

        response = submit_for_approval(payload, service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Stories submitted for approval successfully")
        self.assertEqual(response.data, mock_data)
        service.submit_for_approval.assert_called_once_with(service.db, payload, _DUMMY_USER_ID)

    def test_submit_wraps_unexpected_failure(self) -> None:
        payload = StoryApprovalSubmitRequest(
            epics=[
                {
                    "epicId": "EPIC-1",
                    "epicTitle": "Epic 1",
                    "user_stories": [
                        {
                            "storyId": _DUMMY_STORY_ID,
                            "storyTitle": "Title",
                            "description": "desc",
                            "acceptanceCriteria": "ac",
                            "issue_type": "story",
                        }
                    ],
                }
            ],
            project_id=_DUMMY_PROJECT_ID,
            reviewer_emails=["reviewer@example.com"],
        )
        service = SimpleNamespace(
            db=object(),
            submit_for_approval=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            submit_for_approval(payload, service, _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "APPROVAL_SUBMIT_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    def test_submit_reraises_app_exception(self) -> None:
        expected = AppException(
            code="APPROVAL_SUBMIT_FAILED", message="duplicate", status_code=409
        )
        payload = StoryApprovalSubmitRequest(
            epics=[
                {
                    "epicId": "EPIC-1",
                    "epicTitle": "Epic 1",
                    "user_stories": [
                        {
                            "storyId": _DUMMY_STORY_ID,
                            "storyTitle": "Title",
                            "description": "desc",
                            "acceptanceCriteria": "ac",
                            "issue_type": "story",
                        }
                    ],
                }
            ],
            project_id=_DUMMY_PROJECT_ID,
            reviewer_emails=["reviewer@example.com"],
        )
        service = SimpleNamespace(
            db=object(),
            submit_for_approval=Mock(side_effect=expected),
        )

        with self.assertRaises(AppException) as context:
            submit_for_approval(payload, service, _DUMMY_USER_ID)

        self.assertIs(context.exception, expected)


class DecideApprovalEndpointTests(unittest.TestCase):
    """Verify decide_approval endpoint response shape."""

    _CURRENT_USER = SimpleNamespace(id=_DUMMY_USER_ID, email="reviewer@example.com")

    def test_decide_returns_updated_record(self) -> None:
        from datetime import datetime, timezone

        mock_data = StoryApprovalDecisionResponse(
            id=_DUMMY_APPROVAL_ID,
            user_story_id=_DUMMY_STORY_ID,
            status="approved",
            decided_at=datetime.now(timezone.utc),
        )
        payload = StoryApprovalDecisionRequest(decision="approved")
        service = SimpleNamespace(
            db=object(),
            decide_approval=Mock(return_value=mock_data),
        )

        response = decide_approval(_DUMMY_APPROVAL_ID, payload, service, self._CURRENT_USER)

        self.assertEqual(response.message, "Approval decision recorded successfully")
        self.assertEqual(response.data, mock_data)
        # Both identities are forwarded: the id is recorded, the email is what gets checked.
        service.decide_approval.assert_called_once_with(
            service.db,
            _DUMMY_APPROVAL_ID,
            "approved",
            decided_by=_DUMMY_USER_ID,
            decided_by_email="reviewer@example.com",
        )

    def test_decide_wraps_unexpected_failure(self) -> None:
        payload = StoryApprovalDecisionRequest(decision="rejected")
        service = SimpleNamespace(
            db=object(),
            decide_approval=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            decide_approval(_DUMMY_APPROVAL_ID, payload, service, self._CURRENT_USER)

        self.assertEqual(context.exception.code, "APPROVAL_DECIDE_FAILED")
        self.assertEqual(context.exception.status_code, 500)

    def test_decide_reraises_app_exception(self) -> None:
        expected = AppException(code="APPROVAL_NOT_FOUND", message="missing", status_code=404)
        payload = StoryApprovalDecisionRequest(decision="approved")
        service = SimpleNamespace(
            db=object(),
            decide_approval=Mock(side_effect=expected),
        )

        with self.assertRaises(AppException) as context:
            decide_approval(_DUMMY_APPROVAL_ID, payload, service, self._CURRENT_USER)

        self.assertIs(context.exception, expected)


class ListProjectApprovalsEndpointTests(unittest.TestCase):
    """Verify list_project_approvals endpoint response shape."""

    def test_list_project_returns_data_on_success(self) -> None:
        records = [_make_approval_record()]
        service = SimpleNamespace(
            db=object(),
            list_project_approvals=Mock(return_value=records),
        )

        response = list_project_approvals(_DUMMY_PROJECT_ID, service, _DUMMY_USER_ID)

        self.assertEqual(response.message, "Project approvals retrieved successfully")
        self.assertEqual(response.data, records)
        service.list_project_approvals.assert_called_once_with(service.db, _DUMMY_PROJECT_ID)

    def test_list_project_wraps_unexpected_failure(self) -> None:
        service = SimpleNamespace(
            db=object(),
            list_project_approvals=Mock(side_effect=RuntimeError("boom")),
        )

        with self.assertRaises(AppException) as context:
            list_project_approvals(_DUMMY_PROJECT_ID, service, _DUMMY_USER_ID)

        self.assertEqual(context.exception.code, "APPROVAL_LIST_FAILED")
        self.assertEqual(context.exception.status_code, 500)


class GetReviewQueueEndpointTests(unittest.TestCase):
    """Verify get_review_queue endpoint scoping and response shape."""

    def test_review_queue_uses_current_user_email(self) -> None:
        queue = ReviewQueueResponse(stories=[], counts=ReviewQueueCounts(pending=1))
        service = SimpleNamespace(
            db=object(),
            get_review_queue=Mock(return_value=queue),
        )
        current_user = SimpleNamespace(email="reviewer@example.com")

        response = get_review_queue(
            service, current_user, status="pending", project_id=None, epic_id=None
        )

        self.assertEqual(response.message, "Review queue retrieved successfully")
        self.assertEqual(response.data, queue)
        service.get_review_queue.assert_called_once_with(
            service.db,
            "reviewer@example.com",
            status="pending",
            project_id=None,
            epic_id=None,
            search=None,
            page=1,
            page_size=20,
        )

    def test_review_queue_wraps_unexpected_failure(self) -> None:
        service = SimpleNamespace(
            db=object(),
            get_review_queue=Mock(side_effect=RuntimeError("boom")),
        )
        current_user = SimpleNamespace(email="reviewer@example.com")

        with self.assertRaises(AppException) as context:
            get_review_queue(service, current_user, status=None, project_id=None, epic_id=None)

        self.assertEqual(context.exception.code, "APPROVAL_LIST_FAILED")
        self.assertEqual(context.exception.status_code, 500)
