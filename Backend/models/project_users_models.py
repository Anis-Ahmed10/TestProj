"""Database models for project team mappings."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.connection import Base


class ProjectUser(Base):
    """Mapping table connecting Users to Projects."""

    __tablename__ = "project_users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    assigned_at = Column(DateTime(timezone=False), nullable=True, server_default=func.now())
    status = Column(String(20), default="Active", nullable=True)
    hours_this_sprint = Column("hours", Integer, default=0, nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "project_id", name="unique_project_user"),)
