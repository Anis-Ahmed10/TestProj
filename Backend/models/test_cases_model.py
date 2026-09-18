from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.core.connection import Base


class TestCase(Base):
    """ORM mapping for the `test_cases` table."""

    __tablename__ = "test_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_story_id = Column(
        String(100),
        ForeignKey("user_stories.story_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    test_format_type = Column(String(20), nullable=False)
    test_data = Column(JSONB, nullable=False)
    created_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    jira_key = Column(String(50), nullable=True)
    status = Column(
        Enum(
            "approved",
            "pending",
            "archived",
            name="test_case_status_enum",
        ),
        nullable=False,
        server_default=text("'pending'"),
    )
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())
    last_modified = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
