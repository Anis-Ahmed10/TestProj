"""Tests for story_approval_db's decision cascade scoping and bulk creation."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, DatabaseOperationException
from app.database.crud_jira_import import ImportSummary
from app.database.story_approval_db import (
    count_reviewer_approvals_by_status,
    decide_approval_with_cascade,
    get_approval_request_by_id,
    get_batch_decision_summary,
    list_approvals_by_project,
    list_review_queue_for_reviewer,
    list_reviewer_queue_facets,
    persist_and_create_approval_requests,
)
from app.models.story_approval_model import StoryApprovalRequest

_DUMMY_PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
_DUMMY_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def _epics_payload(story_ids: list[str]) -> list[dict]:
    """Build a minimal submit payload (one epic) carrying the given story keys."""
    return [
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
    ]


def _bound_value(clauses, column_name):
    """Return the compared value for `column_name == value` in a filter clause list."""
    for clause in clauses:
        left = getattr(clause, "left", None)
        if left is not None and getattr(left, "key", None) == column_name:
            return clause.right.value
    return None


class DecideApprovalCascadeScopeTests(unittest.TestCase):
    """Verify the sibling cascade is scoped to the submission batch, not just the story.

    Without this scoping, two independent submissions of the same story (e.g. from
    different submitters or reviewer sets) would resolve each other's pending
    requests when only one of them is actually decided.
    """

    def test_cascade_filters_by_submission_batch_id(self) -> None:
        approval_id = uuid4()
        batch_id = uuid4()
        record = StoryApprovalRequest(
            id=approval_id,
            user_story_id="STORY-1",
            project_id=uuid4(),
            submitted_by=uuid4(),
            reviewer_email="a@example.com",
            submission_batch_id=batch_id,
            status="pending",
        )

        db = MagicMock()
        lock_query = MagicMock()
        lock_query.filter.return_value = lock_query
        lock_query.with_for_update.return_value = lock_query
        lock_query.first.return_value = record

        cascade_query = MagicMock()
        cascade_query.filter.return_value = cascade_query

        story_query = MagicMock()
        story_query.filter.return_value = story_query

        db.query.side_effect = [lock_query, cascade_query, story_query]

        decider = uuid4()
        decide_approval_with_cascade(
            db,
            approval_id,
            status="approved",
            decided_by=decider,
            decided_by_email="a@example.com",
        )

        # The actual decider is stamped on the decided row and cascaded to siblings.
        self.assertEqual(record.decided_by, decider)
        self.assertEqual(cascade_query.update.call_args.args[0].get("decided_by"), decider)

        cascade_filter_args = cascade_query.filter.call_args.args
        self.assertEqual(
            _bound_value(cascade_filter_args, "submission_batch_id"),
            batch_id,
            "cascade must scope siblings to the deciding row's submission batch",
        )
        self.assertEqual(
            _bound_value(cascade_filter_args, "user_story_id"),
            "STORY-1",
        )
        self.assertEqual(
            _bound_value(story_query.filter.call_args.args, "story_key"),
            "STORY-1",
            "decision must cascade onto the story's own status",
        )
        story_query.update.assert_called_once_with(
            {"status": "approved"}, synchronize_session=False
        )


def _existing_pending_query(rows):
    query = MagicMock()
    query.filter.return_value = query
    query.__iter__.return_value = iter(rows)
    return query


@patch("app.database.story_approval_db.save_epics_and_stories", return_value=ImportSummary())
class PersistAndCreateApprovalRequestsConflictTests(unittest.TestCase):
    """Verify the retry-once-excluding-conflicts behavior on a unique-index race.

    save_epics_and_stories is patched out; these tests focus on the approval-request
    half of the atomic operation. The story-persist half is asserted separately.
    """

    def test_persists_stories_with_deferred_commit_then_creates_requests(self, mock_save) -> None:
        db = MagicMock()
        db.query.return_value = _existing_pending_query([])

        created, skipped, _failed = persist_and_create_approval_requests(
            db,
            epics_payload=_epics_payload(["STORY-1"]),
            project_id=_DUMMY_PROJECT_ID,
            submitted_by=_DUMMY_USER_ID,
            reviewer_emails=["bob@example.com"],
        )

        # Stories are saved first, in the same (deferred) transaction as the inserts.
        mock_save.assert_called_once()
        self.assertIs(mock_save.call_args.kwargs.get("commit"), False)
        self.assertEqual(skipped, [])
        self.assertEqual([r.user_story_id for r in created], ["STORY-1"])
        db.commit.assert_called_once()

    def test_retries_once_and_skips_only_the_pair_that_lost_the_race(self, _mock_save) -> None:
        db = MagicMock()

        first_check = _existing_pending_query([])
        conflicting_row = SimpleNamespace(
            user_story_id="STORY-1", reviewer_email="bob@example.com"
        )
        retry_check = _existing_pending_query([conflicting_row])
        db.query.side_effect = [first_check, retry_check]

        db.commit.side_effect = [IntegrityError("stmt", {}, Exception("dup")), None]

        created, skipped, _failed = persist_and_create_approval_requests(
            db,
            epics_payload=_epics_payload(["STORY-1", "STORY-2"]),
            project_id=_DUMMY_PROJECT_ID,
            submitted_by=_DUMMY_USER_ID,
            reviewer_emails=["bob@example.com"],
        )

        self.assertEqual(skipped, [("STORY-1", "bob@example.com")])
        self.assertEqual([r.user_story_id for r in created], ["STORY-2"])
        db.rollback.assert_called_once()
        self.assertEqual(db.commit.call_count, 2)

    def test_duplicate_reviewers_and_stories_build_one_row_per_pair(self, _mock_save) -> None:
        """A double-submit repeating a reviewer (or a story) must not build duplicate
        rows — they'd violate the pending partial unique index and 500 on retry."""
        db = MagicMock()
        db.query.return_value = _existing_pending_query([])

        created, _skipped, _failed = persist_and_create_approval_requests(
            db,
            epics_payload=_epics_payload(["STORY-1", "STORY-1", "STORY-2"]),
            project_id=_DUMMY_PROJECT_ID,
            submitted_by=_DUMMY_USER_ID,
            reviewer_emails=["bob@example.com", "bob@example.com"],
        )

        pairs = [(r.user_story_id, r.reviewer_email) for r in created]
        self.assertEqual(
            pairs,
            [("STORY-1", "bob@example.com"), ("STORY-2", "bob@example.com")],
        )
        db.commit.assert_called_once()


@patch("app.database.story_approval_db.save_epics_and_stories", return_value=ImportSummary())
class PersistAndCreateApprovalRequestsEdgeCaseTests(unittest.TestCase):
    """Cover the no-new-records, empty-retry, and failure paths."""

    def test_commits_story_upserts_even_when_all_pairs_already_pending(self, _mock_save) -> None:
        db = MagicMock()
        existing_row = SimpleNamespace(user_story_id="STORY-1", reviewer_email="bob@example.com")
        db.query.return_value = _existing_pending_query([existing_row])

        created, skipped, _failed = persist_and_create_approval_requests(
            db,
            epics_payload=_epics_payload(["STORY-1"]),
            project_id=_DUMMY_PROJECT_ID,
            submitted_by=_DUMMY_USER_ID,
            reviewer_emails=["bob@example.com"],
        )

        self.assertEqual(created, [])
        self.assertEqual(skipped, [("STORY-1", "bob@example.com")])
        # Commits once to persist the deferred story upserts, even with no new requests.
        db.commit.assert_called_once()

    def test_retry_with_no_remaining_new_records_still_commits_story_upserts(
        self, _mock_save
    ) -> None:
        db = MagicMock()
        first_check = _existing_pending_query([])
        # On retry, both pairs are now pending, so there is nothing left to insert.
        conflicting_rows = [
            SimpleNamespace(user_story_id="STORY-1", reviewer_email="bob@example.com"),
            SimpleNamespace(user_story_id="STORY-2", reviewer_email="bob@example.com"),
        ]
        retry_check = _existing_pending_query(conflicting_rows)
        db.query.side_effect = [first_check, retry_check]
        db.commit.side_effect = [IntegrityError("stmt", {}, Exception("dup")), None]

        created, skipped, _failed = persist_and_create_approval_requests(
            db,
            epics_payload=_epics_payload(["STORY-1", "STORY-2"]),
            project_id=_DUMMY_PROJECT_ID,
            submitted_by=_DUMMY_USER_ID,
            reviewer_emails=["bob@example.com"],
        )

        self.assertEqual(created, [])
        self.assertEqual(
            sorted(skipped),
            [("STORY-1", "bob@example.com"), ("STORY-2", "bob@example.com")],
        )
        db.rollback.assert_called_once()
        # First commit failed; the retry commits again to persist the re-saved stories.
        self.assertEqual(db.commit.call_count, 2)

    def test_story_that_failed_to_save_gets_no_approval_request(self, mock_save) -> None:
        """The atomic invariant: no approval row may be committed without its
        user_stories row, so stories in summary.failed are excluded."""
        db = MagicMock()
        db.query.return_value = _existing_pending_query([])
        mock_save.return_value = ImportSummary(failed=["STORY-2"])

        created, skipped, failed = persist_and_create_approval_requests(
            db,
            epics_payload=_epics_payload(["STORY-1", "STORY-2"]),
            project_id=_DUMMY_PROJECT_ID,
            submitted_by=_DUMMY_USER_ID,
            reviewer_emails=["bob@example.com"],
        )

        self.assertEqual([r.user_story_id for r in created], ["STORY-1"])
        self.assertEqual(skipped, [])
        self.assertEqual(failed, ["STORY-2"])

    def test_wraps_unexpected_error_in_database_operation_exception(self, _mock_save) -> None:
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")

        with self.assertRaises(DatabaseOperationException):
            persist_and_create_approval_requests(
                db,
                epics_payload=_epics_payload(["STORY-1"]),
                project_id=_DUMMY_PROJECT_ID,
                submitted_by=_DUMMY_USER_ID,
                reviewer_emails=["bob@example.com"],
            )
        db.rollback.assert_called_once()

    def test_renamed_story_gets_approval_request_under_its_new_key(self, mock_save) -> None:

        db = MagicMock()
        db.query.return_value = _existing_pending_query([])
        mock_save.return_value = ImportSummary(
            inserted=["STORY-1_1"],
            renamed=[{"original": "STORY-1", "renamed": "STORY-1_1"}],
        )

        created, skipped, failed = persist_and_create_approval_requests(
            db,
            epics_payload=_epics_payload(["STORY-1"]),
            project_id=_DUMMY_PROJECT_ID,
            submitted_by=_DUMMY_USER_ID,
            reviewer_emails=["bob@example.com"],
        )

        self.assertEqual([r.user_story_id for r in created], ["STORY-1_1"])
        self.assertEqual(skipped, [])
        self.assertEqual(failed, [])


class GetApprovalRequestByIdTests(unittest.TestCase):
    """Cover the single-record lookup helper."""

    def test_returns_record_from_db_get(self) -> None:
        db = MagicMock()
        approval_id = uuid4()
        sentinel = object()
        db.get.return_value = sentinel

        self.assertIs(get_approval_request_by_id(db, approval_id), sentinel)
        db.get.assert_called_once_with(StoryApprovalRequest, approval_id)

    def test_wraps_error_in_database_operation_exception(self) -> None:
        db = MagicMock()
        db.get.side_effect = RuntimeError("boom")

        with self.assertRaises(DatabaseOperationException):
            get_approval_request_by_id(db, uuid4())


class ListApprovalsByProjectTests(unittest.TestCase):
    """Cover the per-project listing helper."""

    def test_returns_ordered_records(self) -> None:
        db = MagicMock()
        query = MagicMock()
        query.filter.return_value = query
        query.order_by.return_value = query
        rows = [object(), object()]
        query.all.return_value = rows
        db.query.return_value = query

        self.assertEqual(list_approvals_by_project(db, _DUMMY_PROJECT_ID), rows)

    def test_wraps_error_in_database_operation_exception(self) -> None:
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")

        with self.assertRaises(DatabaseOperationException):
            list_approvals_by_project(db, _DUMMY_PROJECT_ID)


class DecideApprovalNotFoundAndErrorTests(unittest.TestCase):
    """Cover the not-found, already-decided, and failure paths of decide."""

    def _lock_query_returning(self, record):
        lock_query = MagicMock()
        lock_query.filter.return_value = lock_query
        lock_query.with_for_update.return_value = lock_query
        lock_query.first.return_value = record
        return lock_query

    def test_raises_not_found_when_no_row_exists(self) -> None:
        db = MagicMock()
        db.query.return_value = self._lock_query_returning(None)
        db.get.return_value = None

        with self.assertRaises(AppException) as ctx:
            decide_approval_with_cascade(
                db,
                uuid4(),
                status="approved",
                decided_by=uuid4(),
                decided_by_email="a@example.com",
            )

        self.assertEqual(ctx.exception.code, "APPROVAL_NOT_FOUND")
        self.assertEqual(ctx.exception.status_code, 404)
        db.rollback.assert_called_once()

    def test_raises_already_decided_when_row_not_pending(self) -> None:
        db = MagicMock()
        db.query.return_value = self._lock_query_returning(None)
        db.get.return_value = SimpleNamespace(status="approved")

        with self.assertRaises(AppException) as ctx:
            decide_approval_with_cascade(
                db,
                uuid4(),
                status="rejected",
                decided_by=uuid4(),
                decided_by_email="a@example.com",
            )

        self.assertEqual(ctx.exception.code, "APPROVAL_ALREADY_DECIDED")
        self.assertEqual(ctx.exception.status_code, 409)
        db.rollback.assert_called_once()

    def test_wraps_unexpected_error_in_database_operation_exception(self) -> None:
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")

        with self.assertRaises(DatabaseOperationException):
            decide_approval_with_cascade(
                db,
                uuid4(),
                status="approved",
                decided_by=uuid4(),
                decided_by_email="a@example.com",
            )
        db.rollback.assert_called_once()


class DecideApprovalReviewerOwnershipTests(unittest.TestCase):
    """STORY_APPROVE gates the action, not the row: only the assigned reviewer decides."""

    def _db_holding(self, record):
        """A db whose locked-row query returns `record`; extra queries would be the cascade."""
        db = MagicMock()
        lock_query = MagicMock()
        lock_query.filter.return_value = lock_query
        lock_query.with_for_update.return_value = lock_query
        lock_query.first.return_value = record
        db.query.return_value = lock_query
        return db, lock_query

    def _pending_record(self):
        return StoryApprovalRequest(
            id=uuid4(),
            user_story_id="STORY-1",
            project_id=uuid4(),
            submitted_by=uuid4(),
            reviewer_email="owner@example.com",
            submission_batch_id=uuid4(),
            status="pending",
        )

    def test_rejects_caller_who_is_not_the_assigned_reviewer(self) -> None:
        record = self._pending_record()
        db, lock_query = self._db_holding(record)

        with self.assertRaises(AppException) as ctx:
            decide_approval_with_cascade(
                db,
                record.id,
                status="approved",
                decided_by=uuid4(),
                decided_by_email="intruder@example.com",
            )

        self.assertEqual(ctx.exception.code, "APPROVAL_FORBIDDEN")
        self.assertEqual(ctx.exception.status_code, 403)
        # Nothing settled: not the row, not the siblings, not the story.
        self.assertEqual(record.status, "pending")
        self.assertIsNone(record.decided_by)
        lock_query.update.assert_not_called()
        db.commit.assert_not_called()
        db.rollback.assert_called_once()

    def test_allows_the_assigned_reviewer(self) -> None:
        record = self._pending_record()
        db, _ = self._db_holding(record)
        decider = uuid4()

        decide_approval_with_cascade(
            db,
            record.id,
            status="approved",
            decided_by=decider,
            decided_by_email="owner@example.com",
        )

        self.assertEqual(record.status, "approved")
        self.assertEqual(record.decided_by, decider)
        db.commit.assert_called_once()

    def test_comparison_is_exact_so_case_variant_is_refused(self) -> None:
        """Exact match, like the queue's own filter: you decide only what your queue shows."""
        record = self._pending_record()
        db, _ = self._db_holding(record)

        with self.assertRaises(AppException) as ctx:
            decide_approval_with_cascade(
                db,
                record.id,
                status="approved",
                decided_by=uuid4(),
                decided_by_email="Owner@Example.com",
            )

        self.assertEqual(ctx.exception.status_code, 403)


class ListReviewQueueForReviewerTests(unittest.TestCase):
    """Cover the enriched review-queue join, its optional filters, and error path."""

    def _query_returning(self, rows):
        query = MagicMock()
        query.outerjoin.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query
        query.count.return_value = len(rows)
        query.all.return_value = rows
        return query

    def test_returns_rows_without_filters(self) -> None:
        rows = [SimpleNamespace(id=uuid4())]
        query = self._query_returning(rows)
        db = MagicMock()
        db.query.return_value = query

        result, total = list_review_queue_for_reviewer(db, "reviewer@example.com")

        self.assertEqual(result, rows)
        self.assertEqual(total, 1)

    def test_applies_status_project_epic_and_search_filters(self) -> None:
        rows = [SimpleNamespace(id=uuid4())]
        query = self._query_returning(rows)
        db = MagicMock()
        db.query.return_value = query

        result, _total = list_review_queue_for_reviewer(
            db,
            "reviewer@example.com",
            status="pending",
            project_id=_DUMMY_PROJECT_ID,
            epic_id="EPIC-1",
            search="login",
            limit=20,
            offset=0,
        )

        self.assertEqual(result, rows)
        # base reviewer filter + status + project + epic + search = 5 filter calls
        self.assertEqual(query.filter.call_count, 5)
        query.limit.assert_called_once_with(20)
        query.offset.assert_called_once_with(0)

    def test_wraps_error_in_database_operation_exception(self) -> None:
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")

        with self.assertRaises(DatabaseOperationException):
            list_review_queue_for_reviewer(db, "reviewer@example.com")


class GetBatchDecisionSummaryTests(unittest.TestCase):
    """Cover the batch-complete gate and the approved/rejected split."""

    def _db_returning(self, rows):
        query = MagicMock()
        query.filter.return_value = query
        query.distinct.return_value = query
        query.all.return_value = rows
        db = MagicMock()
        db.query.return_value = query
        return db

    def test_returns_none_while_any_request_pending(self) -> None:
        rows = [
            SimpleNamespace(
                user_story_id="S-1",
                status="approved",
                submitted_by=_DUMMY_USER_ID,
                project_id=_DUMMY_PROJECT_ID,
            ),
            SimpleNamespace(
                user_story_id="S-2",
                status="pending",
                submitted_by=_DUMMY_USER_ID,
                project_id=_DUMMY_PROJECT_ID,
            ),
        ]
        db = self._db_returning(rows)
        self.assertIsNone(get_batch_decision_summary(db, uuid4()))

    def test_returns_none_when_batch_empty(self) -> None:
        db = self._db_returning([])
        self.assertIsNone(get_batch_decision_summary(db, uuid4()))

    def test_splits_approved_and_rejected_once_fully_decided(self) -> None:
        rows = [
            SimpleNamespace(
                user_story_id="S-2",
                status="approved",
                submitted_by=_DUMMY_USER_ID,
                project_id=_DUMMY_PROJECT_ID,
            ),
            SimpleNamespace(
                user_story_id="S-1",
                status="approved",
                submitted_by=_DUMMY_USER_ID,
                project_id=_DUMMY_PROJECT_ID,
            ),
            SimpleNamespace(
                user_story_id="S-3",
                status="rejected",
                submitted_by=_DUMMY_USER_ID,
                project_id=_DUMMY_PROJECT_ID,
            ),
        ]
        db = self._db_returning(rows)

        summary = get_batch_decision_summary(db, uuid4())

        assert summary is not None
        self.assertEqual(summary["approved"], ["S-1", "S-2"])
        self.assertEqual(summary["rejected"], ["S-3"])
        self.assertEqual(summary["submitted_by"], _DUMMY_USER_ID)
        self.assertEqual(summary["project_id"], _DUMMY_PROJECT_ID)

    def test_wraps_error_in_database_operation_exception(self) -> None:
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")

        with self.assertRaises(DatabaseOperationException):
            get_batch_decision_summary(db, uuid4())


class CountReviewerApprovalsByStatusTests(unittest.TestCase):
    """Cover the grouped-count helper and its error path."""

    def test_returns_status_count_map(self) -> None:
        query = MagicMock()
        query.filter.return_value = query
        query.group_by.return_value = query
        query.all.return_value = [("pending", 3), ("approved", 1)]
        db = MagicMock()
        db.query.return_value = query

        result = count_reviewer_approvals_by_status(db, "reviewer@example.com")

        self.assertEqual(result, {"pending": 3, "approved": 1})

    def test_wraps_error_in_database_operation_exception(self) -> None:
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")

        with self.assertRaises(DatabaseOperationException):
            count_reviewer_approvals_by_status(db, "reviewer@example.com")


class ListReviewerQueueFacetsTests(unittest.TestCase):
    """Cover the facet lookup, its label fallbacks, and the error path."""

    def _db_returning(self, projects, epics):
        def chain(rows):
            query = MagicMock()
            query.select_from.return_value = query
            query.join.return_value = query
            query.outerjoin.return_value = query
            query.filter.return_value = query
            query.distinct.return_value = query
            query.all.return_value = rows
            return query

        db = MagicMock()
        db.query.side_effect = [chain(projects), chain(epics)]
        return db

    def test_maps_projects_and_epics(self) -> None:
        db = self._db_returning(
            [(_DUMMY_PROJECT_ID, "Apollo")],
            [("EPIC-1", "Login flow")],
        )

        facets = list_reviewer_queue_facets(db, "reviewer@example.com")

        self.assertEqual(facets["projects"], [{"id": str(_DUMMY_PROJECT_ID), "label": "Apollo"}])
        self.assertEqual(facets["epics"], [{"id": "EPIC-1", "label": "Login flow"}])

    def test_falls_back_on_missing_labels_and_drops_null_ids(self) -> None:
        # A project deleted out from under its approvals still has rows here, so the
        # id must survive with a placeholder label; a null id has nothing to filter by.
        db = self._db_returning(
            [(_DUMMY_PROJECT_ID, None), (None, "Orphaned")],
            [("EPIC-2", None), (None, "No key")],
        )

        facets = list_reviewer_queue_facets(db, "reviewer@example.com")

        self.assertEqual(
            facets["projects"],
            [{"id": str(_DUMMY_PROJECT_ID), "label": "Unknown project"}],
        )
        self.assertEqual(facets["epics"], [{"id": "EPIC-2", "label": "EPIC-2"}])

    def test_wraps_error_in_database_operation_exception(self) -> None:
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")

        with self.assertRaises(DatabaseOperationException):
            list_reviewer_queue_facets(db, "reviewer@example.com")


class PersistAndCreateApprovalRequestsAppExceptionTests(unittest.TestCase):
    """An AppException must roll back but reach the caller with its own status/code.

    Wrapping it in DatabaseOperationException would turn a deliberate 4xx (e.g. an
    unknown project) into an opaque 500.
    """

    @patch("app.database.story_approval_db.save_epics_and_stories")
    def test_rolls_back_and_propagates_unwrapped(self, mock_save) -> None:
        mock_save.side_effect = AppException(
            code="PROJECT_NOT_FOUND", message="No such project", status_code=404
        )
        db = MagicMock()

        with self.assertRaises(AppException) as ctx:
            persist_and_create_approval_requests(
                db,
                epics_payload=_epics_payload(["STORY-1"]),
                project_id=_DUMMY_PROJECT_ID,
                submitted_by=_DUMMY_USER_ID,
                reviewer_emails=["bob@example.com"],
            )

        self.assertNotIsInstance(ctx.exception, DatabaseOperationException)
        self.assertEqual(ctx.exception.code, "PROJECT_NOT_FOUND")
        db.rollback.assert_called_once()
        db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
