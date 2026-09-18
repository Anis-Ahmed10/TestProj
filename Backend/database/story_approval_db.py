"""Database access helpers for story approval request records."""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import product
from uuid import UUID, uuid4

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.core.exceptions import AppException, DatabaseOperationException
from app.core.logging import logger
from app.database.crud_jira_import import save_epics_and_stories
from app.models.epics_model import Epic
from app.models.project_models import Project
from app.models.story_approval_model import StoryApprovalRequest
from app.models.user_stories_model import UserStory
from app.models.users_models import User


def _fetch_existing_pending(
    db: Session, user_story_ids: list[str], reviewer_emails: list[str]
) -> set[tuple[str, str]]:
    return {
        (row.user_story_id, row.reviewer_email)
        for row in db.query(
            StoryApprovalRequest.user_story_id,
            StoryApprovalRequest.reviewer_email,
        ).filter(
            StoryApprovalRequest.status == "pending",
            StoryApprovalRequest.user_story_id.in_(user_story_ids),
            StoryApprovalRequest.reviewer_email.in_(reviewer_emails),
        )
    }


def _story_ids_from_epics(epics_payload: list[dict]) -> list[str]:
    """Flatten the submitted epics payload down to its story keys."""
    return [
        story["storyId"]
        for epic in epics_payload
        for story in epic.get("user_stories", [])
        if story.get("storyId")
    ]


def _apply_renames(story_ids: list[str], renamed: list[dict]) -> list[str]:
    if not renamed:
        return story_ids
    rename_map = {r["original"]: r["renamed"] for r in renamed}
    return [rename_map.get(sid, sid) for sid in story_ids]


def _build_pending_records(
    db: Session,
    *,
    project_id: UUID,
    submitted_by: UUID,
    user_story_ids: list[str],
    reviewer_emails: list[str],
    batch_id: UUID,
) -> tuple[list[StoryApprovalRequest], list[tuple[str, str]]]:
    """Build (but do NOT persist) approval-request rows for every (story, reviewer)
    pair that isn't already pending, plus the pairs skipped for being already pending.
    Fetches existing pending pairs in one query rather than one SELECT per pair."""
    existing_pending = _fetch_existing_pending(db, user_story_ids, reviewer_emails)
    # Dedupe both axes (order-preserving) before the cross product: a repeated
    # reviewer email or a story key listed under two epics would otherwise build
    # two identical (story, reviewer) rows in one batch, which the partial unique
    # index rejects — and the retry would rebuild the same duplicates and fail again.
    pairs = list(product(dict.fromkeys(user_story_ids), dict.fromkeys(reviewer_emails)))
    skipped_pairs = [pair for pair in pairs if pair in existing_pending]
    records = [
        StoryApprovalRequest(
            user_story_id=story_id,
            project_id=project_id,
            submitted_by=submitted_by,
            reviewer_email=reviewer_email,
            submission_batch_id=batch_id,
            status="pending",
        )
        for story_id, reviewer_email in pairs
        if (story_id, reviewer_email) not in existing_pending
    ]
    return records, skipped_pairs


def persist_and_create_approval_requests(
    db: Session,
    *,
    epics_payload: list[dict],
    project_id: UUID,
    submitted_by: UUID,
    reviewer_emails: list[str],
) -> tuple[list[StoryApprovalRequest], list[tuple[str, str]], list[str]]:
    """Upsert the submitted stories and create their approval requests atomically.

    save_epics_and_stories runs with commit=False so the story upserts and the
    approval-request inserts share ONE transaction and ONE commit — either both land
    or neither does. This guarantees an approval request can never exist without its
    user_stories row, the invariant the decision cascade (which UPDATEs
    user_stories.status) and the re-import 'already approved' check both rely on.

    The unique partial index on (user_story_id, reviewer_email) WHERE status='pending'
    still guards against a concurrent double-submit. On that conflict we roll back the
    whole unit (stories included), re-check what's now pending, and retry once with
    just the pairs that are still new — re-saving the stories in the retry so the
    both-or-neither guarantee holds across the retry too.

    save_epics_and_stories reports per-story failures instead of raising, so its
    summary.failed keys are excluded from the approval rows built below — otherwise
    a story whose upsert failed would still get an approval request committed in the
    same transaction, i.e. exactly the orphan row this function exists to prevent.

    Returns (created_records, skipped_pairs, failed_story_ids) where skipped_pairs
    already had a pending request and failed_story_ids were dropped because their
    story row could not be saved.
    """

    submitted_story_ids = _story_ids_from_epics(epics_payload)

    # commit() expires every loaded attribute; with all columns defaulted client-side
    # the returned records stay usable without a SELECT per row to read them back.
    db.expire_on_commit = False
    try:
        # Defer the story commit so it shares this transaction with the inserts below.
        summary = save_epics_and_stories(db, epics_payload, project_id=project_id, commit=False)
        failed = set(summary.failed)
        effective_story_ids = _apply_renames(submitted_story_ids, summary.renamed)
        user_story_ids = [sid for sid in effective_story_ids if sid not in failed]

        batch_id = uuid4()
        records, skipped_pairs = _build_pending_records(
            db,
            project_id=project_id,
            submitted_by=submitted_by,
            user_story_ids=user_story_ids,
            reviewer_emails=reviewer_emails,
            batch_id=batch_id,
        )

        try:
            if records:
                db.add_all(records)
            db.commit()
        except IntegrityError:
            db.rollback()
            logger.warning("story_approval_persist_submit_conflict_retry")
            # Re-save the stories too so the retry re-establishes both halves together.
            summary = save_epics_and_stories(
                db, epics_payload, project_id=project_id, commit=False
            )
            failed = set(summary.failed)
            effective_story_ids = _apply_renames(submitted_story_ids, summary.renamed)
            user_story_ids = [sid for sid in effective_story_ids if sid not in failed]
            batch_id = uuid4()
            records, skipped_pairs = _build_pending_records(
                db,
                project_id=project_id,
                submitted_by=submitted_by,
                user_story_ids=user_story_ids,
                reviewer_emails=reviewer_emails,
                batch_id=batch_id,
            )
            if records:
                db.add_all(records)
            db.commit()

        return records, skipped_pairs, sorted(failed)
    except AppException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("story_approval_persist_submit_failed")
        raise DatabaseOperationException(
            "Unable to persist stories and create approval requests for submission"
        ) from exc
    finally:
        db.expire_on_commit = True


def get_approval_request_by_id(db: Session, approval_id: UUID) -> StoryApprovalRequest | None:
    """Fetch a single approval record by its primary key."""

    try:
        return db.get(StoryApprovalRequest, approval_id)
    except Exception as exc:
        logger.exception("story_approval_lookup_failed")
        raise DatabaseOperationException(
            f"Unable to fetch approval request: {approval_id}"
        ) from exc


def list_approvals_by_project(db: Session, project_id: UUID) -> list[StoryApprovalRequest]:
    """Return all approval records for a project."""

    try:
        return (
            db.query(StoryApprovalRequest)
            .filter(StoryApprovalRequest.project_id == project_id)
            .order_by(StoryApprovalRequest.submitted_at.desc())
            .all()
        )
    except Exception as exc:
        logger.exception("story_approval_list_by_project_failed")
        raise DatabaseOperationException(
            f"Unable to fetch approvals for project: {project_id}"
        ) from exc


def list_review_queue_for_reviewer(
    db: Session,
    reviewer_email: str,
    *,
    status: str | None = None,
    project_id: UUID | None = None,
    epic_id: str | None = None,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list, int]:
    """Return one page of the reviewer's approvals plus the total matching count.

    Left joins so an approval still surfaces if its story row hasn't landed yet
    (submission can precede the generate-time save into user_stories). Filtering
    and paging are done in the DB so the caller never loads the whole assigned set;
    the total is counted against the same filters (before limit/offset) so the
    client can render the correct number of pages.
    """

    Decider = aliased(User)

    try:
        query = (
            db.query(
                StoryApprovalRequest.id,
                StoryApprovalRequest.user_story_id,
                StoryApprovalRequest.project_id,
                StoryApprovalRequest.status,
                StoryApprovalRequest.submitted_at,
                StoryApprovalRequest.decided_at,
                UserStory.title,
                UserStory.description,
                UserStory.acceptance_criteria,
                UserStory.priority,
                UserStory.epic_id,
                Epic.title.label("epic_title"),
                Project.name.label("project_name"),
                User.name.label("submitted_by_name"),
                Decider.name.label("decided_by_name"),
            )
            .outerjoin(UserStory, UserStory.story_key == StoryApprovalRequest.user_story_id)
            .outerjoin(Epic, Epic.epic_key == UserStory.epic_id)
            .outerjoin(Project, Project.id == StoryApprovalRequest.project_id)
            .outerjoin(User, User.id == StoryApprovalRequest.submitted_by)
            .outerjoin(Decider, Decider.id == StoryApprovalRequest.decided_by)
            .filter(StoryApprovalRequest.reviewer_email == reviewer_email)
        )
        if status:
            query = query.filter(StoryApprovalRequest.status == status)
        if project_id:
            query = query.filter(StoryApprovalRequest.project_id == project_id)
        if epic_id:
            query = query.filter(UserStory.epic_id == epic_id)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    UserStory.title.ilike(term),
                    StoryApprovalRequest.user_story_id.ilike(term),
                )
            )

        total = query.order_by(None).count()
        query = query.order_by(StoryApprovalRequest.submitted_at.desc()).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return query.all(), total
    except Exception as exc:
        logger.exception("story_approval_review_queue_failed")
        raise DatabaseOperationException(
            f"Unable to fetch review queue for reviewer: {reviewer_email}"
        ) from exc


def list_reviewer_queue_facets(db: Session, reviewer_email: str) -> dict[str, list]:
    """Return the distinct projects and epics across the reviewer's whole assigned set.

    Computed unfiltered (like the status counts) so the filter dropdowns stay
    complete no matter which page or filter the reviewer is currently viewing.
    """

    try:
        projects = (
            db.query(StoryApprovalRequest.project_id, Project.name)
            .outerjoin(Project, Project.id == StoryApprovalRequest.project_id)
            .filter(StoryApprovalRequest.reviewer_email == reviewer_email)
            .distinct()
            .all()
        )
        epics = (
            db.query(UserStory.epic_id, Epic.title)
            .select_from(StoryApprovalRequest)
            .join(UserStory, UserStory.story_key == StoryApprovalRequest.user_story_id)
            .outerjoin(Epic, Epic.epic_key == UserStory.epic_id)
            .filter(
                StoryApprovalRequest.reviewer_email == reviewer_email,
                UserStory.epic_id.isnot(None),
            )
            .distinct()
            .all()
        )
        return {
            "projects": [
                {"id": str(pid), "label": name or "Unknown project"}
                for pid, name in projects
                if pid
            ],
            "epics": [{"id": eid, "label": title or eid} for eid, title in epics if eid],
        }
    except Exception as exc:
        logger.exception("story_approval_review_facets_failed")
        raise DatabaseOperationException(
            f"Unable to fetch review queue facets for reviewer: {reviewer_email}"
        ) from exc


def count_reviewer_approvals_by_status(db: Session, reviewer_email: str) -> dict[str, int]:
    """Return counts of the reviewer's approvals grouped by status."""

    try:
        rows = (
            db.query(StoryApprovalRequest.status, func.count())
            .filter(StoryApprovalRequest.reviewer_email == reviewer_email)
            .group_by(StoryApprovalRequest.status)
            .all()
        )
        return {status: count for status, count in rows}
    except Exception as exc:
        logger.exception("story_approval_review_counts_failed")
        raise DatabaseOperationException(
            f"Unable to count approvals for reviewer: {reviewer_email}"
        ) from exc


def get_batch_decision_summary(db: Session, submission_batch_id: UUID) -> dict | None:
    """Summarize a submission batch, but only once every story in it is decided.

    Returns None while any request in the batch is still pending (so the caller
    stays silent until the whole submission is resolved), else a dict with the
    submitter, project, and the approved/rejected story keys — the basis for the
    single 'your submission has been reviewed' email. Story keys are de-duped
    because a batch has one row per (story, reviewer); any-one-decides gives every
    reviewer row of a story the same status.
    """

    try:
        rows = (
            db.query(
                StoryApprovalRequest.user_story_id,
                StoryApprovalRequest.status,
                StoryApprovalRequest.submitted_by,
                StoryApprovalRequest.project_id,
            )
            .filter(StoryApprovalRequest.submission_batch_id == submission_batch_id)
            .distinct()
            .all()
        )
        if not rows:
            return None
        if any(row.status == "pending" for row in rows):
            return None
        return {
            "submitted_by": rows[0].submitted_by,
            "project_id": rows[0].project_id,
            "approved": sorted({r.user_story_id for r in rows if r.status == "approved"}),
            "rejected": sorted({r.user_story_id for r in rows if r.status == "rejected"}),
        }
    except Exception as exc:
        logger.exception("story_approval_batch_summary_failed")
        raise DatabaseOperationException(
            f"Unable to summarize approval batch: {submission_batch_id}"
        ) from exc


def decide_approval_with_cascade(
    db: Session,
    approval_id: UUID,
    *,
    status: str,
    decided_by: UUID,
    decided_by_email: str,
) -> StoryApprovalRequest:
    """Atomically decide an approval and cascade to sibling pending requests.

    Locks the target row with SELECT ... FOR UPDATE gated on status='pending', so
    two reviewers deciding sibling rows of the same story concurrently cannot both
    pass a status check and interleave to a mixed final state. The decision and the
    sibling cascade are committed together so a mid-cascade failure can't leave the
    decided row settled while siblings stay pending forever.

    The cascade is scoped to the deciding row's submission_batch_id, not just the
    story, so an independent, later submission of the same story (different
    submitter or reviewer set) can't have its pending requests silently resolved
    by someone else's earlier, unrelated decision.

    STORY_APPROVE only gates the action; it does not say this row is yours. The
    reviewer check below is what stops one reviewer settling a story assigned to
    another — and, via the cascade, the whole batch and the story's status. The
    comparison is exact, matching list_review_queue_for_reviewer's filter, so the
    rule is precisely "you can decide what your queue shows you".
    """

    try:
        record = (
            db.query(StoryApprovalRequest)
            .filter(
                StoryApprovalRequest.id == approval_id,
                StoryApprovalRequest.status == "pending",
            )
            .with_for_update()
            .first()
        )
        if record is None:
            existing = db.get(StoryApprovalRequest, approval_id)
            if existing is None:
                raise AppException(
                    code="APPROVAL_NOT_FOUND",
                    message=f"Approval request {approval_id} not found",
                    status_code=404,
                )
            raise AppException(
                code="APPROVAL_ALREADY_DECIDED",
                message=(f"Approval request {approval_id} has already been {existing.status}"),
                status_code=409,
            )

        if record.reviewer_email != decided_by_email:
            raise AppException(
                code="APPROVAL_FORBIDDEN",
                message="Not an assigned reviewer for this approval request",
                status_code=403,
            )

        decided_at = datetime.now(timezone.utc)
        record.status = status
        record.decided_at = decided_at
        record.decided_by = decided_by
        db.add(record)

        # Sibling rows inherit the same decider: any-one-decides means whoever
        # clicked resolved the story for every assigned reviewer in this batch.
        db.query(StoryApprovalRequest).filter(
            StoryApprovalRequest.user_story_id == record.user_story_id,
            StoryApprovalRequest.submission_batch_id == record.submission_batch_id,
            StoryApprovalRequest.status == "pending",
            StoryApprovalRequest.id != approval_id,
        ).update(
            {"status": status, "decided_at": decided_at, "decided_by": decided_by},
            synchronize_session=False,
        )

        db.query(UserStory).filter(UserStory.story_key == record.user_story_id).update(
            {"status": status},
            synchronize_session=False,
        )

        db.commit()
        db.refresh(record)
        return record
    except AppException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("story_approval_decide_cascade_failed")
        raise DatabaseOperationException(
            f"Unable to process approval decision for: {approval_id}"
        ) from exc
