"""Business service for team management."""

from __future__ import annotations

import logging
from http import HTTPStatus
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, ResourceNotFoundError
from app.database.access_scope_db import get_visible_project_ids
from app.database.teams_db import (
    get_available_users_for_project,
    get_team_members_by_project,
    remove_member_from_project,
)
from app.models.project_users_models import ProjectUser
from app.schemas.teams import TeamMemberResponse
from app.schemas.users import UserSummary

logger = logging.getLogger(__name__)


class TeamsService:
    """Operations for managing project team members."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _ensure_project_visible(self, project_id: UUID, current_user_id: UUID) -> None:
        """Raise a 403 if this project is outside the caller's visibility
        scope. Visibility is role-based (see app.database.access_scope_db):
        e.g. an Engineer can only see the team of a project they're on."""

        visible_ids = get_visible_project_ids(self.db, current_user_id)
        if visible_ids is not None and project_id not in visible_ids:
            raise AppException(
                code="FORBIDDEN",
                message="You do not have access to this project.",
                status_code=HTTPStatus.FORBIDDEN,
            )

    def get_project_team_members(
        self, project_id: UUID, current_user_id: UUID
    ) -> list[TeamMemberResponse]:
        """Fetch all users currently assigned to a project."""
        self._ensure_project_visible(project_id, current_user_id)
        try:
            assigned_users = get_team_members_by_project(self.db, project_id)

            return [
                TeamMemberResponse(
                    id=str(user.id),
                    user_id=str(user.id),
                    name=getattr(user, "full_name", getattr(user, "name", user.email)),
                    email=user.email,
                    role=getattr(user, "role", "Team Member"),
                    hours_this_sprint=pu.hours_this_sprint or 0,
                    status=getattr(pu, "status", None)
                    or ("Active" if getattr(user, "is_active", True) else "Inactive"),
                )
                for user, pu in assigned_users
            ]
        except Exception as exc:
            logger.exception("teams_get_project_members_failure")
            raise AppException(
                code="TEAM_MEMBERS_FETCH_FAILED",
                message="Unable to fetch team members.",
                status_code=500,
            ) from exc

    def get_available_users(self, project_id: UUID, current_user_id: UUID) -> list[UserSummary]:
        """Fetch users eligible to be added to the project."""
        self._ensure_project_visible(project_id, current_user_id)
        try:
            users = get_available_users_for_project(self.db, project_id)
            return [UserSummary.model_validate(u) for u in users]
        except Exception as exc:
            logger.exception("teams_get_available_users_failure")
            raise AppException(
                code="TEAMS_AVAILABLE_USERS_FAILED",
                message="Unable to fetch available users right now.",
                status_code=500,
            ) from exc

    def add_members_to_project(
        self, project_id: UUID, user_ids: list[UUID], current_user_id: UUID
    ) -> list[TeamMemberResponse]:
        self._ensure_project_visible(project_id, current_user_id)

        if not user_ids:
            return []

        requested_ids = set(user_ids)
        try:
            current_team = get_team_members_by_project(self.db, project_id)
        except Exception as exc:
            self.db.rollback()
            logger.exception(
                "teams_add_members_failed",
                extra={"project_id": str(project_id), "user_ids": [str(u) for u in user_ids]},
            )
            raise AppException(
                code="TEAM_MEMBERS_ADD_FAILED",
                message="Unable to add team members right now.",
                status_code=500,
            ) from exc

        existing_ids = {user.id for user, _pu in current_team if user.id in requested_ids}
        new_ids = requested_ids - existing_ids
        if not new_ids:
            return self.get_project_team_members(project_id, current_user_id)

        try:
            stmt = (
                pg_insert(ProjectUser)
                .values([{"project_id": project_id, "user_id": uid} for uid in user_ids])
                .on_conflict_do_nothing(constraint="unique_project_user")
                .returning(ProjectUser)
            )
            self.db.execute(stmt)
            self.db.commit()
            return self.get_project_team_members(project_id, current_user_id)
        except AppException:
            raise
        except Exception as exc:
            self.db.rollback()
            logger.exception(
                "teams_add_members_failed",
                extra={"project_id": str(project_id), "user_ids": [str(u) for u in user_ids]},
            )
            raise AppException(
                code="TEAM_MEMBERS_ADD_FAILED",
                message="Unable to add team members right now.",
                status_code=500,
            ) from exc

    def remove_member_from_project(self, project_id: UUID, user_id: UUID, current_user_id: UUID):
        self._ensure_project_visible(project_id, current_user_id)
        try:
            removed_member = remove_member_from_project(self.db, project_id, user_id)
            if removed_member is None:
                self.db.rollback()
                raise ResourceNotFoundError(
                    f"User {user_id} is not a member of project {project_id}"
                )
            self.db.commit()
            return {"name": removed_member}
        except ResourceNotFoundError:
            raise
        except Exception as exc:
            self.db.rollback()
            logger.exception(
                "teams_remove_member_failed",
                extra={"project_id": str(project_id), "user_id": str(user_id)},
            )
            raise AppException(
                code="TEAM_MEMBER_REMOVE_FAILED",
                message="Unable to remove team member right now.",
                status_code=500,
            ) from exc
