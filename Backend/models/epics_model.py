import uuid

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.connection import Base


class Epic(Base):
    __tablename__ = "epics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)

    epic_key = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    title = Column(String(255), nullable=False)
    project = relationship("Project", back_populates="epics")

    user_stories = relationship(
        "UserStory",
        back_populates="epic",
        cascade="all, delete-orphan",
    )
