from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseOperationException
from app.models.rbac_models import PermissionModel, RoleModel, role_permissions

logger = logging.getLogger(__name__)


def get_permissions_for_role(db: Session, role_name: str) -> frozenset[str]:
    """Resolve the permission names granted to a role via the RBAC tables."""

    if not role_name or not role_name.strip():
        return frozenset()
    try:
        rows = (
            db.execute(
                select(PermissionModel.name)
                .join(
                    role_permissions,
                    role_permissions.c.permission_id == PermissionModel.id,
                )
                .join(RoleModel, RoleModel.id == role_permissions.c.role_id)
                .where(func.lower(RoleModel.name) == role_name.strip().lower())
            )
            .scalars()
            .all()
        )
        return frozenset(rows)
    except Exception as exc:
        logger.exception("get_permissions_for_role_failed", extra={"role": role_name})
        raise DatabaseOperationException("Unable to resolve role permissions") from exc
