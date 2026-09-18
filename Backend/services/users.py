"""Business service for user directory lookups."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.logging import logger
from app.database.projects_db import get_project_approvers
from app.database.users_db import list_roles, list_users, update_user_role
from app.schemas.users import ProjectApprover, RoleSummary, UpdateUserRoleResponse, UserSummary


class UsersService:
    """User directory and role management operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_approval_users(self, db: Session, project_id: uuid.UUID) -> list[ProjectApprover]:
        """Return the project's manager and lead, the reviewers stories can go to."""

        try:
            return [
                ProjectApprover(role_label=label, name=name, email=email)
                for label, name, email in get_project_approvers(db, project_id)
            ]
        except AppException:
            raise
        except Exception as exc:
            logger.exception("approval_users_list_unexpected_failure")
            raise AppException(
                code="USERS_LIST_FAILED",
                message="Unable to fetch users right now.",
                status_code=500,
            ) from exc

    def list_users(self, db: Session) -> list[UserSummary]:
        """Return all active users."""

        try:
            users = list_users(db)
            return [UserSummary.model_validate(u) for u in users]
        except AppException:
            raise
        except Exception as exc:
            logger.exception("users_list_unexpected_failure")
            raise AppException(
                code="USERS_LIST_FAILED",
                message="Unable to fetch users right now.",
                status_code=500,
            ) from exc

    def list_roles(self, db: Session) -> list[RoleSummary]:
        """Return all available roles as lightweight summaries."""

        try:
            roles = list_roles(db)
            return [RoleSummary.model_validate(r) for r in roles]
        except AppException:
            raise
        except Exception as exc:
            logger.exception("roles_list_unexpected_failure")
            raise AppException(
                code="ROLES_LIST_FAILED",
                message="Unable to fetch roles right now.",
                status_code=500,
            ) from exc

    def update_user_role(
        self, db: Session, user_id: uuid.UUID, role_name: str
    ) -> UpdateUserRoleResponse:
        """Update the role for a given user; raises AppException if user or role is not found."""

        try:
            user = update_user_role(db, user_id, role_name)
            return UpdateUserRoleResponse.model_validate(user)
        except AppException:
            raise
        except Exception as exc:
            logger.exception(
                "update_user_role_unexpected_failure",
                extra={"user_id": str(user_id), "role_name": role_name},
            )
            raise AppException(
                code="UPDATE_USER_ROLE_FAILED",
                message="Unable to update user role right now.",
                status_code=500,
            ) from exc
