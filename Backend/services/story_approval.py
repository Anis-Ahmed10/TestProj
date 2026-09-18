"""Business service for story approval workflow."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import logger
from app.database.crud_jira_import import normalize_story_priority
from app.database.projects_db import get_project_approvers, get_project_by_id
from app.database.story_approval_db import (
    count_reviewer_approvals_by_status,
    decide_approval_with_cascade,
    get_batch_decision_summary,
    list_approvals_by_project,
    list_review_queue_for_reviewer,
    list_reviewer_queue_facets,
    persist_and_create_approval_requests,
)
from app.database.users_db import get_user_by_id
from app.schemas.story_approval import (
    ReviewQueueCounts,
    ReviewQueueFacet,
    ReviewQueueFacets,
    ReviewQueueResponse,
    ReviewStory,
    StoryApprovalDecisionResponse,
    StoryApprovalRecord,
    StoryApprovalSkippedPair,
    StoryApprovalSubmitRequest,
    StoryApprovalSubmitResponse,
)
from app.services.email_templates.story_approval import (
    build_approval_notification,
    build_decision_summary_notification,
)
from app.services.ses_email_service import SesEmailService


def _split_acceptance_criteria(raw: str | None) -> list[str]:
    """Split a stored acceptance-criteria blob into individual, trimmed items.

    Both write paths (normal save and send-for-approval) join criteria with ' | '
    before persisting, so split on that first; also split on newlines so any
    legacy newline-joined rows still render as separate items rather than one blob.
    """

    if not raw:
        return []
    return [part.strip() for part in re.split(r"\s*\|\s*|\r?\n", raw) if part.strip()]


class StoryApprovalService:
    """Handle story approval submission, listing, and decision logic."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def submit_for_approval(
        self,
        db: Session,
        payload: StoryApprovalSubmitRequest,
        submitted_by: UUID,
    ) -> StoryApprovalSubmitResponse:
        """Persist the selected stories, create approval records, and notify reviewers.

        Story persistence and approval-request creation happen in one atomic call so
        a submitted story always has a user_stories row for the decision cascade and
        the re-import status check to land on.
        """

        try:
            reviewer_emails = self._validated_reviewers(
                db, payload.project_id, payload.reviewer_emails
            )

            epics_payload = [
                {
                    "epicId": epic.epicId,
                    "epicTitle": epic.epicTitle or epic.epicId,
                    "user_stories": [
                        {
                            "storyId": s.storyId,
                            "storyTitle": s.storyTitle,
                            "description": s.description,
                            "acceptanceCriteria": s.acceptanceCriteria or "",
                            "issue_type": s.issue_type,
                            "priority": s.priority,
                        }
                        for s in epic.user_stories
                    ],
                }
                for epic in payload.epics
            ]
            created, skipped_pairs, failed_story_ids = persist_and_create_approval_requests(
                db,
                epics_payload=epics_payload,
                project_id=payload.project_id,
                submitted_by=submitted_by,
                reviewer_emails=reviewer_emails,
            )
            created_records = [StoryApprovalRecord.model_validate(r) for r in created]
            skipped_count = len(skipped_pairs)
            if skipped_pairs:
                logger.info(
                    "story_approval_skipped_duplicate",
                    extra={
                        "skipped_pairs": [
                            {"user_story_id": str(story_id), "reviewer_email": reviewer_email}
                            for story_id, reviewer_email in skipped_pairs
                        ],
                    },
                )
            if failed_story_ids:
                logger.warning(
                    "story_approval_story_save_failed",
                    extra={"failed_story_ids": failed_story_ids},
                )

            # Send one email to all reviewers if any records were created
            if created_records:
                submitted_story_ids = {r.user_story_id for r in created_records}
                self._send_notification(
                    db=db,
                    reviewer_emails=reviewer_emails,
                    submitted_by=submitted_by,
                    project_id=payload.project_id,
                    story_count=len(submitted_story_ids),
                )

            return StoryApprovalSubmitResponse(
                submitted_count=len(created_records),
                skipped_count=skipped_count,
                approval_records=created_records,
                skipped_pairs=[
                    StoryApprovalSkippedPair(user_story_id=story_id, reviewer_email=reviewer_email)
                    for story_id, reviewer_email in skipped_pairs
                ],
                failed_story_ids=failed_story_ids,
            )
        except AppException:
            raise
        except Exception as exc:
            logger.exception("story_approval_submit_unexpected_failure")
            raise AppException(
                code="APPROVAL_SUBMIT_FAILED",
                message="Unable to submit stories for approval right now.",
                status_code=500,
            ) from exc

    def _validated_reviewers(
        self, db: Session, project_id: UUID, requested: list[str]
    ) -> list[str]:
        """Return the requested reviewers, rejecting anyone not assigned to the project.

        The picker only offers the project's manager and lead, so anything outside
        that pair reached the API by another route and would otherwise get an
        approval request — and a notification email — addressed to it.
        """

        assigned = {email.lower(): email for _, _, email in get_project_approvers(db, project_id)}
        if not assigned:
            raise AppException(
                code="APPROVAL_NO_APPROVERS",
                message=(
                    "This project has no active Project Manager or Project Lead "
                    "to approve stories."
                ),
                status_code=409,
            )

        unknown = [email for email in requested if email.lower() not in assigned]
        if unknown:
            logger.warning(
                "story_approval_reviewer_not_assigned",
                extra={"reviewer_count": len(unknown)},
            )
            raise AppException(
                code="APPROVAL_INVALID_REVIEWER",
                message="One or more selected reviewers are not approvers for this project.",
                status_code=400,
            )
        return [assigned[email.lower()] for email in requested]

    def get_review_queue(
        self,
        db: Session,
        reviewer_email: str,
        *,
        status: str | None = None,
        project_id: UUID | None = None,
        epic_id: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ReviewQueueResponse:
        """Build one page of the reviewer's review queue, with counts and facets."""

        try:
            page = max(page, 1)
            page_size = max(1, min(page_size, 100))
            rows, total = list_review_queue_for_reviewer(
                db,
                reviewer_email,
                status=status,
                project_id=project_id,
                epic_id=epic_id,
                search=search,
                limit=page_size,
                offset=(page - 1) * page_size,
            )
            counts = count_reviewer_approvals_by_status(db, reviewer_email)
            facets = list_reviewer_queue_facets(db, reviewer_email)
            stories = [
                ReviewStory(
                    id=row.id,
                    user_story_id=row.user_story_id,
                    project_id=row.project_id,
                    project_name=row.project_name or "Unknown project",
                    epic_id=row.epic_id,
                    epic_title=row.epic_title,
                    title=row.title or row.user_story_id,
                    description=row.description or "",
                    acceptance_criteria=_split_acceptance_criteria(row.acceptance_criteria),
                    priority=normalize_story_priority(row.priority),
                    submitted_by=row.submitted_by_name or "Unknown",
                    submitted_at=row.submitted_at,
                    status=row.status,
                    decided_at=row.decided_at,
                    decided_by_name=(
                        (row.decided_by_name or "Unknown") if row.decided_at else None
                    ),
                )
                for row in rows
            ]
            return ReviewQueueResponse(
                stories=stories,
                total=total,
                counts=ReviewQueueCounts(
                    pending=counts.get("pending", 0),
                    approved=counts.get("approved", 0),
                    rejected=counts.get("rejected", 0),
                ),
                facets=ReviewQueueFacets(
                    projects=[ReviewQueueFacet(**p) for p in facets["projects"]],
                    epics=[ReviewQueueFacet(**e) for e in facets["epics"]],
                ),
            )
        except AppException:
            raise
        except Exception as exc:
            logger.exception("story_approval_review_queue_unexpected_failure")
            raise AppException(
                code="APPROVAL_LIST_FAILED",
                message="Unable to fetch the review queue right now.",
                status_code=500,
            ) from exc

    def list_project_approvals(
        self,
        db: Session,
        project_id: UUID,
    ) -> list[StoryApprovalRecord]:
        """List all approval records for a project."""

        try:
            records = list_approvals_by_project(db, project_id)
            return [StoryApprovalRecord.model_validate(r) for r in records]
        except AppException:
            raise
        except Exception as exc:
            logger.exception("story_approval_list_project_unexpected_failure")
            raise AppException(
                code="APPROVAL_LIST_FAILED",
                message="Unable to fetch project approvals right now.",
                status_code=500,
            ) from exc

    def decide_approval(
        self,
        db: Session,
        approval_id: UUID,
        decision: str,
        decided_by: UUID,
        decided_by_email: str,
    ) -> StoryApprovalDecisionResponse:
        """Approve or reject a single approval request."""

        try:
            updated = decide_approval_with_cascade(
                db,
                approval_id,
                status=decision,
                decided_by=decided_by,
                decided_by_email=decided_by_email,
            )
            # If this decision was the last pending one in its batch, email the
            # submitter a single summary. Best-effort and post-commit — a mail
            # failure must never undo the recorded decision.
            self._notify_submitter_if_batch_complete(db, updated.submission_batch_id)
            return StoryApprovalDecisionResponse.model_validate(updated)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("story_approval_decide_unexpected_failure")
            raise AppException(
                code="APPROVAL_DECIDE_FAILED",
                message="Unable to process approval decision right now.",
                status_code=500,
            ) from exc

    def _notify_submitter_if_batch_complete(self, db: Session, submission_batch_id: UUID) -> None:
        """Email the submitter a summary once every story in the batch is decided.

        Silent while the batch still has pending requests. Fully best-effort: any
        lookup, template, or send failure is logged and swallowed so it can't fail
        the decision that already committed.
        """

        try:
            summary = get_batch_decision_summary(db, submission_batch_id)
            if summary is None:
                return

            submitter = get_user_by_id(db, summary["submitted_by"])
            if submitter is None or not submitter.email:
                logger.warning("story_approval_decision_no_submitter_email")
                return

            project = get_project_by_id(db, summary["project_id"])
            project_name = project.name if project is not None else "N/A"

            settings = get_settings()
            cloudfront_url = settings.cloudfront_url or "http://localhost:3000"
            review_link = f"{cloudfront_url}/test-generator"

            subject, html_body, text_body = build_decision_summary_notification(
                submitter_name=submitter.name or "there",
                project_name=project_name,
                approved_keys=summary["approved"],
                rejected_keys=summary["rejected"],
                review_link=review_link,
            )
            SesEmailService().send_email(
                recipients=[submitter.email],
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        except Exception:
            logger.warning("story_approval_decision_email_failed", exc_info=True)

    def _send_notification(
        self,
        *,
        db: Session,
        reviewer_emails: list[str],
        submitted_by: UUID,
        project_id: UUID,
        story_count: int,
    ) -> None:
        """Best-effort SES notification — failure is logged but does not block."""

        settings = get_settings()
        requestor_name = "Unknown User"
        project_name = "N/A"

        try:
            user = get_user_by_id(db, submitted_by)
            if user is not None:
                requestor_name = user.name
        except Exception:
            logger.warning("story_approval_requestor_lookup_failed", exc_info=True)

        try:
            project = get_project_by_id(db, project_id)
            if project is not None:
                project_name = project.name
        except Exception:
            logger.warning("story_approval_project_lookup_failed", exc_info=True)

        cloudfront_url = settings.cloudfront_url or "http://localhost:3000"
        approval_link = f"{cloudfront_url}/approvals"

        subject, html_body, text_body = build_approval_notification(
            reviewer_emails=reviewer_emails,
            requestor_name=requestor_name,
            project_name=project_name,
            story_count=story_count,
            approval_link=approval_link,
        )
        email_service = SesEmailService()
        sent = email_service.send_email(
            recipients=reviewer_emails,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )
        if not sent:
            logger.warning(
                "story_approval_email_not_sent",
                extra={"reviewer_emails": reviewer_emails},
            )
