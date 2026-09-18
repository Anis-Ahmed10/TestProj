"""SQLAlchemy model for story approval request records."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.connection import Base


class StoryApprovalRequest(Base):
    """Tracks reviewer approval requests for user stories."""

    __tablename__ = "story_approval_requests"

    __table_args__ = (
        # Enforces at the DB level that a (story, reviewer) pair can have at most
        # one pending request, closing the race where two concurrent submissions
        # both pass the app-level "not already pending" check and both insert.
        # Also serves as the lookup index for that same existing-pending query.
        Index(
            "ux_sar_story_reviewer_pending",
            "user_story_id",
            "reviewer_email",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        # Matches list_review_queue_for_reviewer's reviewer + status filter.
        Index("ix_sar_reviewer_status", "reviewer_email", "status"),
        # Matches decide_approval_with_cascade's sibling-cascade filter.
        Index("ix_sar_story_batch_status", "user_story_id", "submission_batch_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Stories are identified throughout this app by their business `story_key`
    # (e.g. a Jira issue key), never by the internal `user_stories.id` UUID —
    # see `test_cases.user_story_id`, which follows the same String(100) pattern.
    user_story_id = Column(String(100), nullable=False)

    project_id = Column(UUID(as_uuid=True), nullable=False)

    submitted_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    reviewer_email = Column(String(255), nullable=False)

    # Who actually recorded the decision (the signed-in user who clicked), as
    # opposed to reviewer_email (who the request was assigned to). With any-one-
    # decides semantics the decider can be a different reviewer than the one this
    # row was addressed to — and cascaded sibling rows carry the same decider —
    # so this is the truthful audit of who resolved the story. NULL while pending.
    decided_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # Shared by every (story, reviewer) row created in the same submit_for_approval
    # call. A decision cascades only to pending siblings with the same batch id, so
    # two independent submissions of the same story (different submitters/reviewer
    # sets) can't resolve each other out.
    submission_batch_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    status = Column(String(20), nullable=False, server_default="pending", default="pending")

    # Client-side default alongside the server one so a freshly inserted row already
    # carries its timestamp in memory — no per-row SELECT to read it back after commit.
    submitted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    decided_at = Column(DateTime(timezone=True), nullable=True)
