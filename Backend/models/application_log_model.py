"""SQLAlchemy model for application request log records."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.connection import Base


class ApplicationLog(Base):
    """Persisted log of every incoming API request."""

    __tablename__ = "application_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logged_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    service_name = Column(String(128), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    http_method = Column(String(10), nullable=False)
    endpoint = Column(String(2048), nullable=False)
    status_code = Column(Integer, nullable=True)
    message = Column(String(2048), nullable=True)
    project_id = Column(UUID(as_uuid=True), nullable=True)
    client_name = Column(String(255), nullable=True)
