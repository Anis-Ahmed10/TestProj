from __future__ import annotations

from sqlalchemy import (
    UUID,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.connection import Base

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        UUID,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        UUID,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class RoleModel(Base):
    """Persisted role; named bundle of permissions, editable at runtime."""

    __tablename__ = "roles"

    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, nullable=False, server_default=text("false"), default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    permissions = relationship(
        "PermissionModel",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )


class PermissionModel(Base):
    """Persisted permission, named resource:action."""

    __tablename__ = "permissions"

    id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    roles = relationship(
        "RoleModel",
        secondary=role_permissions,
        back_populates="permissions",
        lazy="selectin",
    )
