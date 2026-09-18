"""SQLAlchemy model for programme records."""

from __future__ import annotations

from sqlalchemy import UUID, Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.sql import func

from app.core.connection import Base


class Programme(Base):
    """Persisted programme row."""

    __tablename__ = "programmes"

    id = Column(UUID, primary_key=True)
    client_id = Column(UUID, ForeignKey("clients.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, server_default=text("'active'"), default="active")
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())
    last_modified = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
