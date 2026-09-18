"""SQLAlchemy model for project records."""

from __future__ import annotations

from sqlalchemy import UUID, Column, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.connection import Base


class Project(Base):
    """Persisted project row."""

    __tablename__ = "projects"

    id = Column(UUID, primary_key=True)
    programme_id = Column(UUID, ForeignKey("programmes.id"), nullable=False)
    name = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, server_default="active", default="active")
    lead_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    start_date = Column(Date, nullable=True)
    jira_url = Column(String(255), nullable=True)
    jira_project_key = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())
    last_modified = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    epics = relationship(
        "Epic",
        primaryjoin="Project.id == foreign(Epic.project_id)",
        back_populates="project",
    )
