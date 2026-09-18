from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.connection import Base


class User(Base):
    """Persisted user table.

    Column nullability/defaults mirror the actual `public.users` table
    (created directly in Postgres, not via this model) — see `\\d public.users`:
    only `id`, `name`, `email` are NOT NULL; `role`, `is_active`, `created_at`,
    and `last_modified` are nullable at the DB level.
    """

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True)

    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)

    role = Column(
        String(50),
        ForeignKey("roles.name", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=True,
    )
    is_active = Column(Boolean, nullable=False, server_default=func.true())

    jira_email = Column(String(255), nullable=True)
    jira_api_token = Column(String(512), nullable=True)

    created_at = Column(DateTime(timezone=False), nullable=True, server_default=func.now())
    last_modified = Column(
        DateTime(timezone=False),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now(),
    )
