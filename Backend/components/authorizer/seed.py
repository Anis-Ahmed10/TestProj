from __future__ import annotations

import logging

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.components.authorizer.models import Permission, Role
from app.components.authorizer.policy import ROLE_PERMISSIONS
from app.models.rbac_models import PermissionModel, RoleModel

logger = logging.getLogger(__name__)

_ROLE_DESCRIPTIONS = {
    Role.TEST_LEAD: "Platform owner; full access including user management",
    Role.TEST_MANAGER: "Owns clients, programmes, projects and delivery",
    Role.TEST_ENGINEER: "Day-to-day test authoring and analysis",
}


# Advisory lock keys are global to the database, and aeidb is shared with
# aei-ai-service. Anything else taking a pg_advisory lock must not reuse this.
_RBAC_SEED_LOCK_KEY = 5417231


def seed_rbac_defaults(db: Session) -> None:

    try:
        # Concurrent Lambda cold starts all seed at once, and roles.name /
        # permissions.name are UNIQUE — without this the losers of the race hit
        # an IntegrityError and take the whole cold start down. Serialised, the
        # second caller reads what the first committed and adds nothing. The
        # lock is held to the end of this transaction.
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _RBAC_SEED_LOCK_KEY})

        existing_permissions = {
            name.lower(): perm
            for name, perm in db.execute(select(PermissionModel.name, PermissionModel)).all()
        }

        new_permission_values: set[str] = set()
        for permission in Permission:
            key = permission.value.lower()
            if key not in existing_permissions:
                row = PermissionModel(name=permission.value)
                db.add(row)
                existing_permissions[key] = row
                new_permission_values.add(permission.value)

        existing_roles = {
            role_row.name.lower(): role_row
            for role_row in db.execute(select(RoleModel)).scalars().all()
        }

        created_roles = 0
        linked_permissions = 0
        removed_permissions = 0
        for role in Role:
            baseline = ROLE_PERMISSIONS.get(role, frozenset())
            baseline_permission_rows = [
                existing_permissions[permission.value.lower()] for permission in baseline
            ]
            role_row = existing_roles.get(role.value.lower())

            if role_row is None:
                role_row = RoleModel(
                    name=role.value,
                    description=_ROLE_DESCRIPTIONS.get(role),
                    is_system=True,
                )
                role_row.permissions = baseline_permission_rows
                db.add(role_row)
                created_roles += 1
                continue

            # Existing role: attach any baseline permission it lacks; extra
            # (admin-added) links beyond the baseline are left untouched.
            before_names = {perm.name.lower() for perm in role_row.permissions}
            after_names = {permission.value.lower() for permission in baseline}

            if before_names != after_names:
                linked_permissions += len(after_names - before_names)
                removed_permissions += len(before_names - after_names)
                role_row.permissions = baseline_permission_rows

        db.commit()
        if new_permission_values or created_roles or linked_permissions or removed_permissions:
            logger.info(
                "rbac_seed_applied",
                extra={
                    "permissions_created": len(new_permission_values),
                    "roles_created": created_roles,
                    "permissions_linked": linked_permissions,
                    "permissions_removed": removed_permissions,
                },
            )
    except Exception:
        db.rollback()
        logger.exception("rbac_seed_failed")
        raise
