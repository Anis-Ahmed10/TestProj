"""SQLAlchemy model for client records."""

from __future__ import annotations

from sqlalchemy import UUID, Column, DateTime, ForeignKey, String, text
from sqlalchemy.sql import func

from app.core.connection import Base


class Client(Base):
    """Persisted client table used by the client APIs."""

    __tablename__ = "clients"

    id = Column(UUID, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    industry = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    contact = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, server_default=text("'active'"), default="active")
    manager_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_modified = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
