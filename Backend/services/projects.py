"""Business service for project management."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.logging import logger
from app.database.access_scope_db import get_visible_programme_ids, get_visible_project_ids
from app.database.programmes_db import get_programme
from app.database.projects_db import (
    check_project_name_exists,
    create_project_entry,
    get_project_by_id,
    list_all_projects,
    soft_delete_project_entry,
    update_project_entry,
)
from app.database.users_db import get_user_by_id
from app.schemas.projects import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
    ProjectUpdateResponse,
)


class ProjectsService:
    """Handle project creation, retrieval, update, and deletion logic."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_project(
        self, db: Session, payload: ProjectCreateRequest, current_user_id: UUID
    ) -> ProjectResponse:
        """Create a new project under a programme. if that programme is
        visible to the caller."""

        try:
            get_programme(db, payload.programme_id)

            visible_programme_ids = get_visible_programme_ids(db, current_user_id)
            if (
                visible_programme_ids is not None
                and payload.programme_id not in visible_programme_ids
            ):
                raise AppException(
                    code="FORBIDDEN",
                    message="You do not have access to this programme.",
                    status_code=HTTPStatus.FORBIDDEN,
                )

            if check_project_name_exists(db, programme_id=payload.programme_id, name=payload.name):
                raise AppException(
                    code="PROJECT_ALREADY_EXISTS",
                    message="Project name already exists in this programme.",
                    status_code=HTTPStatus.CONFLICT,
                )

            lead_user = None
            if payload.lead_id is not None:
                lead_user = get_user_by_id(self.db, payload.lead_id)
                if not lead_user:
                    raise AppException(
                        code="LEAD_NOT_FOUND",
                        message=f"Project lead user '{payload.lead_id}' not found.",
                        status_code=HTTPStatus.BAD_REQUEST,
                    )

            project = create_project_entry(
                self.db,
                programme_id=payload.programme_id,
                name=payload.name,
                description=payload.description,
                status=payload.status or "active",
                lead_id=payload.lead_id,
                start_date=payload.start_date,
            )
            response = ProjectResponse.model_validate(project)
            response.lead_name = (
                lead_user.name if lead_user else getattr(project, "lead_name", None)
            )
            return response
        except AppException:
            raise
        except Exception as exc:
            logger.exception("project_create_unexpected_failure")
            raise AppException(
                code="PROJECT_CREATE_FAILED",
                message="Unable to create the project right now.",
                status_code=500,
            ) from exc

    def list_projects(self, db: Session, current_user_id: UUID) -> list[ProjectResponse]:
        """Fetch all active projects"""

        try:
            projects = list_all_projects(db)

            visible_ids = get_visible_project_ids(db, current_user_id)
            if visible_ids is not None:
                projects = [p for p in projects if p.id in visible_ids]

            return [ProjectResponse.model_validate(p) for p in projects]
        except AppException:
            raise
        except Exception as exc:
            logger.exception("project_list_unexpected_failure")
            raise AppException(
                code="PROJECT_LIST_FAILED",
                message="Unable to fetch projects right now.",
                status_code=500,
            ) from exc

    def update_project(
        self,
        db: Session,
        project_id: UUID,
        payload: ProjectUpdateRequest,
        current_user_id: UUID,
    ) -> ProjectUpdateResponse:
        """Update a project's fields."""

        try:
            project = get_project_by_id(db, project_id)
            if project is None:
                raise AppException(
                    code="PROJECT_NOT_FOUND",
                    message=f"Project {project_id} not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )

            visible_ids = get_visible_project_ids(db, current_user_id)
            if visible_ids is not None and project_id not in visible_ids:
                raise AppException(
                    code="FORBIDDEN",
                    message="You do not have access to this project.",
                    status_code=HTTPStatus.FORBIDDEN,
                )

            lead_user = None
            if payload.lead_id is not None:
                lead_user = get_user_by_id(self.db, payload.lead_id)
                if not lead_user:
                    raise AppException(
                        code="LEAD_NOT_FOUND",
                        message=f"Project lead user '{payload.lead_id}' not found.",
                        status_code=HTTPStatus.BAD_REQUEST,
                    )

            if (
                payload.name is not None
                and payload.name.strip().lower() != project.name.strip().lower()
            ):
                if check_project_name_exists(
                    db, programme_id=project.programme_id, name=payload.name
                ):
                    raise AppException(
                        code="PROJECT_ALREADY_EXISTS",
                        message="Project name already exists in this programme.",
                        status_code=HTTPStatus.CONFLICT,
                    )

            updated = update_project_entry(
                self.db,
                project_id,
                name=payload.name,
                description=payload.description,
                status=payload.status,
                lead_id=payload.lead_id,
            )
            response = ProjectUpdateResponse.model_validate(updated)

            # Attach lead_name to response
            if payload.lead_id is not None:
                response.lead_name = lead_user.name if lead_user else None
            else:
                response.lead_name = getattr(updated, "lead_name", None)

            return response
            # return ProjectUpdateResponse.model_validate(updated)
        except AppException:
            logger.debug("project_update_failed")
            raise
        except Exception as exc:
            logger.exception("project_update_unexpected_failure")
            raise AppException(
                code="PROJECT_UPDATE_FAILED",
                message="Unable to update the project right now.",
                status_code=500,
            ) from exc

    def delete_project(
        self, db: Session, project_id: UUID, current_user_id: UUID
    ) -> dict[str, str]:
        """Soft delete a project."""

        try:
            visible_ids = get_visible_project_ids(db, current_user_id)
            if visible_ids is not None and project_id not in visible_ids:
                raise AppException(
                    code="FORBIDDEN",
                    message="You do not have access to this project.",
                    status_code=HTTPStatus.FORBIDDEN,
                )
            deleted = soft_delete_project_entry(db, project_id)
            return {
                "deleted_project_id": str(deleted.id),
                "deleted_project_name": deleted.name,
            }
        except AppException:
            logger.debug("project_delete_failed")
            raise
        except Exception as exc:
            logger.exception("project_delete_unexpected_failure")
            raise AppException(
                code="PROJECT_DELETE_FAILED",
                message="Unable to delete the project right now.",
                status_code=500,
            ) from exc
