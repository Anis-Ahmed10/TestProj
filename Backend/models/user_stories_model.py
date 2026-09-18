"""ORM models for Jira import — maps to aeidb schema: epics + user_stories."""

import uuid

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.connection import Base


class UserStory(Base):
    __tablename__ = "user_stories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    epic_id = Column(
        String(100),
        ForeignKey("epics.epic_key"),
        nullable=False,
    )

    story_key = Column(String(100), nullable=True, unique=True, index=True)

    title = Column(String(255), nullable=False)

    description = Column(Text, nullable=True)

    acceptance_criteria = Column(Text, nullable=True)

    priority = Column(String(20), nullable=True)

    status = Column(String(20), nullable=True)
    epic = relationship(
        "Epic",
        back_populates="user_stories",
    )
