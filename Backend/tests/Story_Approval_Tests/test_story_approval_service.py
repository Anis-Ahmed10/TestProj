"""Tests for story approval business service."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.core.exceptions import AppException
from app.schemas.story_approval import StoryApprovalSubmitRequest
from app.services.story_approval import StoryApprovalService

_DUMMY_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
_DUMMY_PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
_DUMMY_BATCH_ID = UUID("22222222-2222-2222-2222-222222222222")
_DUMMY_STORY_ID_1 = "STORY-1"
_DUMMY_STORY_ID_2 = "STORY-2"
_DUMMY_APPROVAL_ID = UUID("33333333-3333-3333-3333-333333333333")


def _make_approval_record_model(
    story_id=_DUMMY_STORY_ID_1,
    status="pending",
    reviewer_email="reviewer@example.com",
):
    """Return a mock ORM-style object for StoryApprovalRequest."""
    return SimpleNamespace(
        id=_DUMMY_APPROVAL_ID,
        user_story_id=story_id,
        project_id=_DUMMY_PROJECT_ID,
        submitted_by=_DUMMY_USER_ID,
        reviewer_email=reviewer_email,
        submission_batch_id=_DUMMY_BATCH_ID,
        status=status,
        submitted_at=datetime.now(timezone.utc),
        decided_at=None,
        decided_by=None,
    )


def _submit_payload(story_ids, reviewer_emails):
    """Build a StoryApprovalSubmitRequest carrying story content grouped by epic."""
    return StoryApprovalSubmitRequest(
        epics=[
            {
                "epicId": "EPIC-1",
                "epicTitle": "Epic 1",
                "user_stories": [
                    {
                        "storyId": sid,
                        "storyTitle": f"Title {sid}",
                        "description": "desc",
                        "acceptanceCriteria": "ac",
                        "issue_type": "story",
                    }
                    for sid in story_ids
                ],
            }
        ],
        project_id=_DUMMY_PROJECT_ID,
        reviewer_emails=reviewer_emails,
    )


class _PermittedReviewersMixin:
    """Stubs the project approver lookup that submit_for_approval validates against."""

    assigned = [
        ("Project Manager", "Reviewer", "reviewer@example.com"),
        ("Project Lead", "Reviewer One", "reviewer1@example.com"),
        ("Project Lead", "Reviewer Two", "reviewer2@example.com"),
    ]

    def setUp(self) -> None:
        super().setUp()
        patcher = patch("app.services.story_approval.get_project_approvers")
        self.mock_get_approvers = patcher.start()
        self.mock_get_approvers.return_value = list(self.assigned)
        self.addCleanup(patcher.stop)


class SubmitForApprovalServiceTests(_PermittedReviewersMixin, unittest.TestCase):
    """Verify StoryApprovalService.submit_for_approval logic."""

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.get_project_by_id")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_submit_skips_duplicate_pending(
        self,
        mock_bulk_create,
        mock_get_user,
        mock_get_project,
        mock_ses_cls,
    ) -> None:
        mock_bulk_create.return_value = ([], [(_DUMMY_STORY_ID_1, "reviewer@example.com")], [])
        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload([_DUMMY_STORY_ID_1], ["reviewer@example.com"])

        result = service.submit_for_approval(db, payload, _DUMMY_USER_ID)

        self.assertEqual(result.submitted_count, 0)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.approval_records, [])
        self.assertEqual(len(result.skipped_pairs), 1)
        self.assertEqual(result.skipped_pairs[0].user_story_id, _DUMMY_STORY_ID_1)
        self.assertEqual(result.skipped_pairs[0].reviewer_email, "reviewer@example.com")

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.get_project_by_id")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_submit_creates_records_and_sends_email(
        self,
        mock_bulk_create,
        mock_get_user,
        mock_get_project,
        mock_ses_cls,
    ) -> None:
        mock_bulk_create.return_value = ([_make_approval_record_model()], [], [])
        mock_get_user.return_value = SimpleNamespace(name="Test User")
        mock_get_project.return_value = SimpleNamespace(name="Test Project")
        mock_ses_instance = MagicMock()
        mock_ses_instance.send_email.return_value = True
        mock_ses_cls.return_value = mock_ses_instance

        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload([_DUMMY_STORY_ID_1], ["reviewer@example.com"])

        result = service.submit_for_approval(db, payload, _DUMMY_USER_ID)

        self.assertEqual(result.submitted_count, 1)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(len(result.approval_records), 1)
        mock_bulk_create.assert_called_once()
        call_kwargs = mock_bulk_create.call_args.kwargs
        self.assertEqual(call_kwargs["project_id"], _DUMMY_PROJECT_ID)
        self.assertEqual(call_kwargs["submitted_by"], _DUMMY_USER_ID)
        self.assertEqual(call_kwargs["reviewer_emails"], ["reviewer@example.com"])
        submitted_story_ids = [
            story["storyId"]
            for epic in call_kwargs["epics_payload"]
            for story in epic["user_stories"]
        ]
        self.assertEqual(submitted_story_ids, [_DUMMY_STORY_ID_1])
        mock_ses_instance.send_email.assert_called_once()
        call_kwargs = mock_ses_instance.send_email.call_args.kwargs
        self.assertEqual(call_kwargs["recipients"], ["reviewer@example.com"])

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.get_project_by_id")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_submit_fans_out_to_multiple_reviewers_with_one_email(
        self,
        mock_bulk_create,
        mock_get_user,
        mock_get_project,
        mock_ses_cls,
    ) -> None:
        mock_bulk_create.return_value = (
            [
                _make_approval_record_model(reviewer_email="reviewer1@example.com"),
                _make_approval_record_model(reviewer_email="reviewer2@example.com"),
            ],
            [],
            [],
        )
        mock_get_user.return_value = SimpleNamespace(name="Test User")
        mock_get_project.return_value = SimpleNamespace(name="Test Project")
        mock_ses_instance = MagicMock()
        mock_ses_instance.send_email.return_value = True
        mock_ses_cls.return_value = mock_ses_instance

        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload(
            [_DUMMY_STORY_ID_1], ["reviewer1@example.com", "reviewer2@example.com"]
        )

        result = service.submit_for_approval(db, payload, _DUMMY_USER_ID)

        self.assertEqual(result.submitted_count, 2)
        self.assertEqual(result.skipped_count, 0)
        mock_ses_instance.send_email.assert_called_once()
        call_kwargs = mock_ses_instance.send_email.call_args.kwargs
        self.assertEqual(
            call_kwargs["recipients"],
            ["reviewer1@example.com", "reviewer2@example.com"],
        )

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.get_project_by_id")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_submit_skips_only_the_reviewer_already_pending(
        self,
        mock_bulk_create,
        mock_get_user,
        mock_get_project,
        mock_ses_cls,
    ) -> None:
        # reviewer1 already has a pending request for this story; reviewer2 does not
        mock_bulk_create.return_value = (
            [_make_approval_record_model(reviewer_email="reviewer2@example.com")],
            [(_DUMMY_STORY_ID_1, "reviewer1@example.com")],
            [],
        )
        mock_get_user.return_value = SimpleNamespace(name="Test User")
        mock_get_project.return_value = SimpleNamespace(name="Test Project")
        mock_ses_instance = MagicMock()
        mock_ses_instance.send_email.return_value = True
        mock_ses_cls.return_value = mock_ses_instance

        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload(
            [_DUMMY_STORY_ID_1], ["reviewer1@example.com", "reviewer2@example.com"]
        )

        result = service.submit_for_approval(db, payload, _DUMMY_USER_ID)

        self.assertEqual(result.submitted_count, 1)
        self.assertEqual(result.skipped_count, 1)

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.get_project_by_id")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_submit_succeeds_when_ses_fails(
        self,
        mock_bulk_create,
        mock_get_user,
        mock_get_project,
        mock_ses_cls,
    ) -> None:
        mock_bulk_create.return_value = ([_make_approval_record_model()], [], [])
        mock_get_user.return_value = SimpleNamespace(name="Test User")
        mock_get_project.return_value = SimpleNamespace(name="Test Project")
        mock_ses_instance = MagicMock()
        mock_ses_instance.send_email.return_value = False
        mock_ses_cls.return_value = mock_ses_instance

        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload([_DUMMY_STORY_ID_1], ["reviewer@example.com"])

        result = service.submit_for_approval(db, payload, _DUMMY_USER_ID)

        self.assertEqual(result.submitted_count, 1)
        self.assertEqual(len(result.approval_records), 1)

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.get_project_by_id")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_submit_logs_warning_when_failed_story_ids_present(
        self,
        mock_bulk_create,
        mock_get_user,
        mock_get_project,
        mock_ses_cls,
    ) -> None:
        mock_bulk_create.return_value = ([], [], ["FAILED-STORY-1"])
        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload([_DUMMY_STORY_ID_1], ["reviewer@example.com"])

        result = service.submit_for_approval(db, payload, _DUMMY_USER_ID)

        self.assertEqual(result.failed_story_ids, ["FAILED-STORY-1"])

    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_submit_rejects_reviewer_not_assigned_to_project(self, mock_bulk_create) -> None:
        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload([_DUMMY_STORY_ID_1], ["outsider@example.com"])

        with self.assertRaises(AppException) as ctx:
            service.submit_for_approval(db, payload, _DUMMY_USER_ID)

        self.assertEqual(ctx.exception.code, "APPROVAL_INVALID_REVIEWER")
        self.assertEqual(ctx.exception.status_code, 400)
        mock_bulk_create.assert_not_called()

    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_submit_rejects_when_project_has_no_approvers(self, mock_bulk_create) -> None:
        self.mock_get_approvers.return_value = []
        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload([_DUMMY_STORY_ID_1], ["reviewer@example.com"])

        with self.assertRaises(AppException) as ctx:
            service.submit_for_approval(db, payload, _DUMMY_USER_ID)

        self.assertEqual(ctx.exception.code, "APPROVAL_NO_APPROVERS")
        self.assertEqual(ctx.exception.status_code, 409)
        mock_bulk_create.assert_not_called()


class SubmitForApprovalErrorTests(_PermittedReviewersMixin, unittest.TestCase):
    """Verify submit_for_approval error handling."""

    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_app_exception_propagates(self, mock_bulk_create) -> None:
        mock_bulk_create.side_effect = AppException(
            code="DATABASE_OPERATION_FAILED", message="db down", status_code=500
        )
        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload([_DUMMY_STORY_ID_1], ["reviewer@example.com"])

        with self.assertRaises(AppException) as ctx:
            service.submit_for_approval(db, payload, _DUMMY_USER_ID)
        self.assertEqual(ctx.exception.code, "DATABASE_OPERATION_FAILED")

    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_unexpected_error_wrapped_as_submit_failed(self, mock_bulk_create) -> None:
        mock_bulk_create.side_effect = RuntimeError("boom")
        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload([_DUMMY_STORY_ID_1], ["reviewer@example.com"])

        with self.assertRaises(AppException) as ctx:
            service.submit_for_approval(db, payload, _DUMMY_USER_ID)
        self.assertEqual(ctx.exception.code, "APPROVAL_SUBMIT_FAILED")
        self.assertEqual(ctx.exception.status_code, 500)


class ListProjectApprovalsServiceTests(unittest.TestCase):
    """Verify StoryApprovalService.list_project_approvals logic."""

    @patch("app.services.story_approval.list_approvals_by_project")
    def test_returns_records(self, mock_list) -> None:
        mock_list.return_value = [_make_approval_record_model()]
        db = MagicMock()
        service = StoryApprovalService(db=db)

        result = service.list_project_approvals(db, _DUMMY_PROJECT_ID)

        self.assertEqual(len(result), 1)
        mock_list.assert_called_once_with(db, _DUMMY_PROJECT_ID)

    @patch("app.services.story_approval.list_approvals_by_project")
    def test_app_exception_propagates(self, mock_list) -> None:
        mock_list.side_effect = AppException(
            code="DATABASE_OPERATION_FAILED", message="db down", status_code=500
        )
        db = MagicMock()
        service = StoryApprovalService(db=db)

        with self.assertRaises(AppException) as ctx:
            service.list_project_approvals(db, _DUMMY_PROJECT_ID)
        self.assertEqual(ctx.exception.code, "DATABASE_OPERATION_FAILED")

    @patch("app.services.story_approval.list_approvals_by_project")
    def test_unexpected_error_wrapped_as_list_failed(self, mock_list) -> None:
        mock_list.side_effect = RuntimeError("boom")
        db = MagicMock()
        service = StoryApprovalService(db=db)

        with self.assertRaises(AppException) as ctx:
            service.list_project_approvals(db, _DUMMY_PROJECT_ID)
        self.assertEqual(ctx.exception.code, "APPROVAL_LIST_FAILED")


class SendNotificationBranchTests(_PermittedReviewersMixin, unittest.TestCase):
    """Cover the best-effort lookup branches of _send_notification."""

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.build_approval_notification")
    @patch("app.services.story_approval.get_project_by_id")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_uses_fallbacks_when_lookups_return_none(
        self,
        mock_bulk_create,
        mock_get_user,
        mock_get_project,
        mock_build,
        mock_ses_cls,
    ) -> None:
        mock_bulk_create.return_value = ([_make_approval_record_model()], [], [])
        mock_get_user.return_value = None
        mock_get_project.return_value = None
        mock_build.return_value = ("subject", "<html>", "text")
        mock_ses_instance = MagicMock()
        mock_ses_instance.send_email.return_value = True
        mock_ses_cls.return_value = mock_ses_instance

        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload([_DUMMY_STORY_ID_1], ["reviewer@example.com"])

        service.submit_for_approval(db, payload, _DUMMY_USER_ID)

        kwargs = mock_build.call_args.kwargs
        self.assertEqual(kwargs["requestor_name"], "Unknown User")
        self.assertEqual(kwargs["project_name"], "N/A")

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.build_approval_notification")
    @patch("app.services.story_approval.get_project_by_id")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.persist_and_create_approval_requests")
    def test_swallows_lookup_exceptions_and_still_sends(
        self,
        mock_bulk_create,
        mock_get_user,
        mock_get_project,
        mock_build,
        mock_ses_cls,
    ) -> None:
        mock_bulk_create.return_value = ([_make_approval_record_model()], [], [])
        mock_get_user.side_effect = RuntimeError("user lookup boom")
        mock_get_project.side_effect = RuntimeError("project lookup boom")
        mock_build.return_value = ("subject", "<html>", "text")
        mock_ses_instance = MagicMock()
        mock_ses_instance.send_email.return_value = False
        mock_ses_cls.return_value = mock_ses_instance

        db = MagicMock()
        service = StoryApprovalService(db=db)
        payload = _submit_payload([_DUMMY_STORY_ID_1], ["reviewer@example.com"])

        result = service.submit_for_approval(db, payload, _DUMMY_USER_ID)

        # Lookup failures must not break submission; fallbacks are used.
        self.assertEqual(result.submitted_count, 1)
        kwargs = mock_build.call_args.kwargs
        self.assertEqual(kwargs["requestor_name"], "Unknown User")
        self.assertEqual(kwargs["project_name"], "N/A")
        mock_ses_instance.send_email.assert_called_once()


class DecideApprovalServiceTests(unittest.TestCase):
    """Verify StoryApprovalService.decide_approval logic."""

    @patch("app.services.story_approval.decide_approval_with_cascade")
    def test_decide_rejects_non_pending(self, mock_decide) -> None:
        mock_decide.side_effect = AppException(
            code="APPROVAL_ALREADY_DECIDED",
            message="Approval request already decided",
            status_code=409,
        )

        db = MagicMock()
        service = StoryApprovalService(db=db)

        with self.assertRaises(AppException) as context:
            service.decide_approval(
                db,
                _DUMMY_APPROVAL_ID,
                "rejected",
                decided_by=_DUMMY_USER_ID,
                decided_by_email="reviewer@example.com",
            )

        self.assertEqual(context.exception.code, "APPROVAL_ALREADY_DECIDED")
        self.assertEqual(context.exception.status_code, 409)

    @patch("app.services.story_approval.get_batch_decision_summary", return_value=None)
    @patch("app.services.story_approval.decide_approval_with_cascade")
    def test_decide_updates_status(self, mock_decide, _mock_summary) -> None:
        decided_record = _make_approval_record_model(status="approved")
        decided_record.decided_at = datetime.now(timezone.utc)
        mock_decide.return_value = decided_record

        db = MagicMock()
        service = StoryApprovalService(db=db)

        result = service.decide_approval(
            db,
            _DUMMY_APPROVAL_ID,
            "approved",
            decided_by=_DUMMY_USER_ID,
            decided_by_email="reviewer@example.com",
        )

        self.assertEqual(result.status, "approved")
        self.assertIsNotNone(result.decided_at)
        # The caller's email must reach the db layer — that's what the reviewer check reads.
        mock_decide.assert_called_once_with(
            db,
            _DUMMY_APPROVAL_ID,
            status="approved",
            decided_by=_DUMMY_USER_ID,
            decided_by_email="reviewer@example.com",
        )

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.get_project_by_id")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.get_batch_decision_summary")
    @patch("app.services.story_approval.decide_approval_with_cascade")
    def test_emails_submitter_once_batch_fully_decided(
        self, mock_decide, mock_summary, mock_user, mock_project, mock_ses
    ) -> None:
        decided = _make_approval_record_model(status="approved")
        decided.decided_at = datetime.now(timezone.utc)
        mock_decide.return_value = decided
        mock_summary.return_value = {
            "submitted_by": _DUMMY_USER_ID,
            "project_id": _DUMMY_PROJECT_ID,
            "approved": ["S-1"],
            "rejected": ["S-2"],
        }
        mock_user.return_value = SimpleNamespace(name="Asha", email="asha@example.com")
        mock_project.return_value = SimpleNamespace(name="Payments")
        send_email = mock_ses.return_value.send_email
        send_email.return_value = True

        service = StoryApprovalService(db=MagicMock())
        service.decide_approval(
            MagicMock(),
            _DUMMY_APPROVAL_ID,
            "approved",
            decided_by=_DUMMY_USER_ID,
            decided_by_email="reviewer@example.com",
        )

        send_email.assert_called_once()
        self.assertEqual(send_email.call_args.kwargs["recipients"], ["asha@example.com"])

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.get_batch_decision_summary", return_value=None)
    @patch("app.services.story_approval.decide_approval_with_cascade")
    def test_no_email_while_batch_still_pending(
        self, mock_decide, _mock_summary, mock_ses
    ) -> None:
        decided = _make_approval_record_model(status="approved")
        decided.decided_at = datetime.now(timezone.utc)
        mock_decide.return_value = decided

        service = StoryApprovalService(db=MagicMock())
        service.decide_approval(
            MagicMock(),
            _DUMMY_APPROVAL_ID,
            "approved",
            decided_by=_DUMMY_USER_ID,
            decided_by_email="reviewer@example.com",
        )

        mock_ses.return_value.send_email.assert_not_called()

    @patch("app.services.story_approval.decide_approval_with_cascade")
    def test_unexpected_error_wrapped_as_decide_failed(self, mock_decide) -> None:
        mock_decide.side_effect = RuntimeError("boom")
        db = MagicMock()
        service = StoryApprovalService(db=db)

        with self.assertRaises(AppException) as ctx:
            service.decide_approval(
                db,
                _DUMMY_APPROVAL_ID,
                "approved",
                decided_by=_DUMMY_USER_ID,
                decided_by_email="reviewer@example.com",
            )
        self.assertEqual(ctx.exception.code, "APPROVAL_DECIDE_FAILED")
        self.assertEqual(ctx.exception.status_code, 500)


def _make_queue_row(**overrides):
    """Return a fake joined Row for the review queue with sensible defaults."""
    defaults = {
        "id": _DUMMY_APPROVAL_ID,
        "user_story_id": _DUMMY_STORY_ID_1,
        "project_id": _DUMMY_PROJECT_ID,
        "status": "pending",
        "submitted_at": datetime.now(timezone.utc),
        "decided_at": None,
        "title": "User Login",
        "description": "As a user, I want to log in, so that I can access my account",
        # Real stored format: both write paths join criteria with ' | '.
        "acceptance_criteria": "Correct credentials redirect | Wrong credentials error",
        "priority": "High",
        "epic_id": "EPIC-AUTH",
        "epic_title": "Authentication",
        "project_name": "Retail Banking Portal",
        "submitted_by_name": "Priya Mehta",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class GetReviewQueueServiceTests(unittest.TestCase):
    """Verify StoryApprovalService.get_review_queue mapping, counts, and error paths."""

    @patch("app.services.story_approval.list_reviewer_queue_facets")
    @patch("app.services.story_approval.count_reviewer_approvals_by_status")
    @patch("app.services.story_approval.list_review_queue_for_reviewer")
    def test_maps_rows_and_counts(self, mock_list, mock_counts, mock_facets) -> None:
        populated = _make_queue_row()
        sparse = _make_queue_row(
            title=None,
            description=None,
            acceptance_criteria=None,
            project_name=None,
            submitted_by_name=None,
            epic_id=None,
            epic_title=None,
        )
        mock_list.return_value = ([populated, sparse], 2)
        mock_counts.return_value = {"pending": 2, "approved": 5}
        mock_facets.return_value = {
            "projects": [{"id": str(_DUMMY_PROJECT_ID), "label": "Retail Banking Portal"}],
            "epics": [{"id": "EPIC-AUTH", "label": "Authentication"}],
        }
        db = MagicMock()
        service = StoryApprovalService(db=db)

        result = service.get_review_queue(db, "reviewer@example.com", status="pending")

        mock_list.assert_called_once_with(
            db,
            "reviewer@example.com",
            status="pending",
            project_id=None,
            epic_id=None,
            search=None,
            limit=20,
            offset=0,
        )
        self.assertEqual(len(result.stories), 2)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.facets.projects[0].label, "Retail Banking Portal")
        self.assertEqual(result.facets.epics[0].id, "EPIC-AUTH")
        self.assertEqual(
            result.stories[0].acceptance_criteria,
            [
                "Correct credentials redirect",
                "Wrong credentials error",
            ],
        )
        # Sparse row falls back to safe defaults.
        self.assertEqual(result.stories[1].title, _DUMMY_STORY_ID_1)
        self.assertEqual(result.stories[1].description, "")
        self.assertEqual(result.stories[1].acceptance_criteria, [])
        self.assertEqual(result.stories[1].project_name, "Unknown project")
        self.assertEqual(result.stories[1].submitted_by, "Unknown")
        self.assertEqual(result.counts.pending, 2)
        self.assertEqual(result.counts.approved, 5)
        self.assertEqual(result.counts.rejected, 0)

    @patch("app.services.story_approval.list_reviewer_queue_facets")
    @patch("app.services.story_approval.count_reviewer_approvals_by_status")
    @patch("app.services.story_approval.list_review_queue_for_reviewer")
    def test_reraises_app_exception(self, mock_list, mock_counts, mock_facets) -> None:
        expected = AppException(code="APPROVAL_LIST_FAILED", message="db down", status_code=503)
        mock_list.side_effect = expected
        service = StoryApprovalService(db=MagicMock())

        with self.assertRaises(AppException) as ctx:
            service.get_review_queue(MagicMock(), "reviewer@example.com")
        self.assertIs(ctx.exception, expected)

    @patch("app.services.story_approval.list_reviewer_queue_facets")
    @patch("app.services.story_approval.count_reviewer_approvals_by_status")
    @patch("app.services.story_approval.list_review_queue_for_reviewer")
    def test_wraps_unexpected_error(self, mock_list, mock_counts, mock_facets) -> None:
        mock_list.side_effect = RuntimeError("boom")
        service = StoryApprovalService(db=MagicMock())

        with self.assertRaises(AppException) as ctx:
            service.get_review_queue(MagicMock(), "reviewer@example.com")
        self.assertEqual(ctx.exception.code, "APPROVAL_LIST_FAILED")
        self.assertEqual(ctx.exception.status_code, 500)


class NotifySubmitterIfBatchCompleteTests(unittest.TestCase):
    """The submitter summary is best-effort: it must never raise into a committed
    decision, and it must stay silent when there is nobody to mail."""

    _SUMMARY = {
        "submitted_by": _DUMMY_USER_ID,
        "project_id": _DUMMY_PROJECT_ID,
        "approved": [_DUMMY_STORY_ID_1],
        "rejected": [],
    }

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.get_batch_decision_summary")
    def test_skips_send_when_submitter_row_missing(
        self, mock_summary, mock_get_user, mock_ses_cls
    ) -> None:
        mock_summary.return_value = dict(self._SUMMARY)
        mock_get_user.return_value = None
        service = StoryApprovalService(db=MagicMock())

        service._notify_submitter_if_batch_complete(MagicMock(), _DUMMY_BATCH_ID)

        mock_ses_cls.assert_not_called()

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.get_batch_decision_summary")
    def test_skips_send_when_submitter_has_no_email(
        self, mock_summary, mock_get_user, mock_ses_cls
    ) -> None:
        mock_summary.return_value = dict(self._SUMMARY)
        mock_get_user.return_value = SimpleNamespace(name="Sam", email="")
        service = StoryApprovalService(db=MagicMock())

        service._notify_submitter_if_batch_complete(MagicMock(), _DUMMY_BATCH_ID)

        mock_ses_cls.assert_not_called()

    @patch("app.services.story_approval.SesEmailService")
    @patch("app.services.story_approval.build_decision_summary_notification")
    @patch("app.services.story_approval.get_project_by_id")
    @patch("app.services.story_approval.get_user_by_id")
    @patch("app.services.story_approval.get_batch_decision_summary")
    def test_logs_but_does_not_raise_when_send_reports_failure(
        self, mock_summary, mock_get_user, mock_get_project, mock_build, mock_ses_cls
    ) -> None:
        mock_summary.return_value = dict(self._SUMMARY)
        mock_get_user.return_value = SimpleNamespace(name="Sam", email="sam@example.com")
        mock_get_project.return_value = SimpleNamespace(name="Apollo")
        mock_build.return_value = ("subject", "<html>", "text")
        mock_ses_instance = MagicMock()
        mock_ses_instance.send_email.return_value = False
        mock_ses_cls.return_value = mock_ses_instance

        service = StoryApprovalService(db=MagicMock())
        service._notify_submitter_if_batch_complete(MagicMock(), _DUMMY_BATCH_ID)

        mock_ses_instance.send_email.assert_called_once()

    @patch("app.services.story_approval.get_batch_decision_summary")
    def test_swallows_unexpected_error(self, mock_summary) -> None:
        mock_summary.side_effect = RuntimeError("boom")
        service = StoryApprovalService(db=MagicMock())

        # No assertion beyond "does not raise" — a mail failure must never undo a
        # decision that has already committed.
        service._notify_submitter_if_batch_complete(MagicMock(), _DUMMY_BATCH_ID)
