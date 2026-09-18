"""CRUD (read) operations for project-scoped user stories."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.constants import APPROVED_STATUS
from app.core.exceptions import DatabaseOperationException
from app.core.logging import logger
from app.models.epics_model import Epic
from app.models.user_stories_model import UserStory


def get_approved_user_stories_by_project(
    db: Session,
    project_id: uuid.UUID,
) -> list[UserStory]:
    """Return all approved user stories for a project, newest epic first"""
    try:
        return (
            db.query(UserStory)
            .join(Epic, UserStory.epic_id == Epic.epic_key)
            .filter(
                Epic.project_id == project_id,
                UserStory.status == APPROVED_STATUS,
            )
            .order_by(UserStory.title.asc())
            .all()
        )
    except Exception as exc:
        logger.exception(
            "get_approved_user_stories_by_project_failed",
            extra={"project_id": str(project_id)},
        )
        raise DatabaseOperationException(
            f"Unable to fetch user stories for project: {project_id}"
        ) from exc
