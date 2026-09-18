"""Database access helpers for project teams."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseOperationException
from app.models.project_users_models import ProjectUser
from app.models.users_models import User

logger = logging.getLogger(__name__)


def get_available_users_for_project(db: Session, project_id: UUID) -> list[User]:
    """Fetch all active users who are NOT currently in the specified project."""
    try:
        # Subquery: IDs of users already in this project
        assigned_user_ids = select(ProjectUser.user_id).where(ProjectUser.project_id == project_id)

        # Select users not in the subquery
        stmt = (
            select(User)
            .where(User.is_active.is_(True), User.id.notin_(assigned_user_ids))
            .order_by(User.name)
        )
        return list(db.execute(stmt).scalars().all())

    except Exception as exc:
        logger.exception(
            "get_available_users_for_project_failed", extra={"project_id": str(project_id)}
        )
        raise DatabaseOperationException("Unable to fetch available users") from exc


def get_team_members_by_project(db: Session, project_id: UUID):
    """Fetch all team members with project-specific details."""
    try:
        stmt = (
            select(User, ProjectUser)
            .join(ProjectUser, User.id == ProjectUser.user_id)
            .where(ProjectUser.project_id == project_id)
        )
        return db.execute(stmt).all()

    except Exception as exc:
        logger.exception(
            "get_team_members_by_project_failed",
            extra={"project_id": str(project_id)},
        )
        raise DatabaseOperationException("Unable to fetch team members") from exc


def remove_member_from_project(db: Session, project_id: UUID, user_id: UUID) -> str | None:
    """Remove a user from a project."""
    try:
        result = (
            db.query(User, ProjectUser)
            .join(ProjectUser, User.id == ProjectUser.user_id)
            .filter(
                ProjectUser.project_id == project_id,
                ProjectUser.user_id == user_id,
            )
            .first()
        )

        if not result:
            return None

        user, association = result
        removed_name = user.name

        db.delete(association)
        db.flush()
        return removed_name

    except Exception as exc:
        logger.exception(
            "remove_member_from_project_failed",
            extra={"project_id": str(project_id), "user_id": str(user_id)},
        )
        raise DatabaseOperationException("Unable to remove team member from project") from exc
