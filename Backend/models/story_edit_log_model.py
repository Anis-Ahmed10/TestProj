"""ORM model for story edit audit log."""

import uuid

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.core.connection import Base


class StoryEditLog(Base):
    __tablename__ = "story_edit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # No FK — stories are saved to user_stories during generate, after this log
    # is written. A referential constraint would block generation on first run.
    story_id = Column(
        String(100),
        nullable=False,
        index=True,
    )

    epic_id = Column(
        String(100),
        nullable=False,
        index=True,
    )

    changes = Column(JSONB, nullable=False)
    edited_at = Column(DateTime(timezone=True), nullable=False)

    # index supports time-range audit queries (e.g. "all edits between date A and B")
    logged_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
