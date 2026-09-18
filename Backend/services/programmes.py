"""Business service for programme management."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.logging import logger
from app.database.access_scope_db import (
    get_visible_client_ids,
    get_visible_programme_ids,
    get_visible_project_ids,
)
from app.database.programmes_db import (
    check_programme_name_exists,
    count_active_projects_by_programme,
    create_programme_entry,
    delete_programme_entry,
    get_client_by_id,
    get_programme,
    get_programme_with_details_db,
    list_all_programmes,
    update_programme_entry,
)
from app.database.projects_db import (
    count_visible_projects_by_programme,
    list_projects_by_programme_id,
)
from app.schemas.programmes import (
    ProgrammeCreateRequest,
    ProgrammeDetailResponse,
    ProgrammeResponse,
    ProgrammeUpdateRequest,
    ProgrammeUpdateResponse,
    ProjectAssociationResponse,
)


class ProgrammesService:
    """Handle programme creation, listing, and deletion logic."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_programme(
        self, db: Session, payload: ProgrammeCreateRequest, current_user_id: UUID
    ) -> ProgrammeResponse:
        """Create a new programme under a client."""

        client = get_client_by_id(db, payload.client_id)
        if client is None:
            raise AppException(
                code="CLIENT_NOT_FOUND",
                message=f"Client {payload.client_id} not found",
                status_code=HTTPStatus.NOT_FOUND,
            )

        visible_client_ids = get_visible_client_ids(db, current_user_id)
        if visible_client_ids is not None and payload.client_id not in visible_client_ids:
            raise AppException(
                code="FORBIDDEN",
                message="You do not have access to this client.",
                status_code=HTTPStatus.FORBIDDEN,
            )

        if check_programme_name_exists(db, client_id=payload.client_id, name=payload.name):
            raise AppException(
                code="PROGRAMME_ALREADY_EXISTS",
                message="Programme name already exists in this client.",
                status_code=HTTPStatus.CONFLICT,
            )

        try:
            programme = create_programme_entry(
                db,
                client_id=payload.client_id,
                name=payload.name,
                description=payload.description,
            )

            row = get_programme_with_details_db(db, programme.id)
            if row is not None:
                prog, project_count, manager_name = row
                res = ProgrammeResponse.model_validate(prog)
                res.project_count = project_count
                res.manager_name = manager_name
                return res

            return ProgrammeResponse.model_validate(programme)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("programme_create_unexpected_failure")
            raise AppException(
                code="PROGRAMME_CREATE_FAILED",
                message="Unable to create the programme right now.",
                status_code=500,
            ) from exc

    def list_programmes(
        self,
        db: Session,
        current_user_id: UUID,
        client_id: UUID | None = None,
    ) -> list[ProgrammeResponse]:
        """Return programmes visible to the current user, optionally filtered
        by client."""

        try:
            rows = list_all_programmes(db, client_id=client_id)

            visible_ids = get_visible_programme_ids(db, current_user_id)
            if visible_ids is not None:
                rows = [row for row in rows if row.Programme.id in visible_ids]

            # Fetch visible project IDs for role scoping (Lead / Engineer)
            visible_project_ids = get_visible_project_ids(db, current_user_id)
            project_counts_by_programme: dict[UUID, int] = {}
            if visible_project_ids is not None:
                project_counts_by_programme = count_visible_projects_by_programme(
                    db, visible_project_ids
                )

            result = []
            for row in rows:
                programme = row.Programme
                response = ProgrammeResponse.model_validate(programme)

                if visible_project_ids is not None:
                    response.project_count = project_counts_by_programme.get(programme.id, 0)
                else:
                    response.project_count = row.project_count

                response.manager_name = getattr(row, "manager_name", None)
                result.append(response)
            return result
        except AppException:
            raise
        except Exception as exc:
            logger.exception("programme_list_unexpected_failure")
            raise AppException(
                code="PROGRAMME_LIST_FAILED",
                message="Unable to fetch programmes right now.",
                status_code=500,
            ) from exc

    def get_programme_details(
        self,
        db: Session,
        programme_id: UUID,
        current_user_id: UUID,
    ) -> ProgrammeDetailResponse:
        """Return a programme with associated projects."""

        try:
            row = get_programme_with_details_db(db, programme_id)
            if row is None:
                raise AppException(
                    code="PROGRAMME_NOT_FOUND",
                    message=f"Programme {programme_id} not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )
            programme, _project_count, manager_name = row

            visible_programme_ids = get_visible_programme_ids(db, current_user_id)
            if visible_programme_ids is not None and programme.id not in visible_programme_ids:
                raise AppException(
                    code="FORBIDDEN",
                    message="You do not have access to this programme.",
                    status_code=HTTPStatus.FORBIDDEN,
                )

            projects = list_projects_by_programme_id(db, programme.id)

            visible_project_ids = get_visible_project_ids(db, current_user_id)
            if visible_project_ids is not None:
                projects = [p for p in projects if p.id in visible_project_ids]

            return ProgrammeDetailResponse(
                id=programme.id,
                client_id=programme.client_id,
                name=programme.name,
                description=programme.description,
                status=programme.status,
                manager_name=manager_name,
                created_at=programme.created_at,
                last_modified=programme.last_modified,
                projects=[
                    ProjectAssociationResponse.model_validate(project) for project in projects
                ],
            )
        except AppException:
            logger.debug("get_programme_details_failed")
            raise
        except Exception as exc:
            logger.exception("get_programme_details_unexpected_failure")
            raise AppException(
                code="PROGRAMME_DETAILS_FETCH_FAILED",
                message="Failed to fetch programme details",
                status_code=500,
            ) from exc

    def update_programme(
        self,
        db: Session,
        programme_id: UUID,
        payload: ProgrammeUpdateRequest,
        current_user_id: UUID,
    ) -> ProgrammeUpdateResponse:
        """Update a programme's fields."""

        try:
            programme = get_programme(db, programme_id)

            visible_ids = get_visible_programme_ids(db, current_user_id)
            if visible_ids is not None and programme_id not in visible_ids:
                raise AppException(
                    code="FORBIDDEN",
                    message="You do not have access to this programme.",
                    status_code=HTTPStatus.FORBIDDEN,
                )

            if (
                payload.name is not None
                and payload.name.strip().lower() != programme.name.strip().lower()
            ):
                if check_programme_name_exists(
                    db, client_id=programme.client_id, name=payload.name
                ):
                    raise AppException(
                        code="PROGRAMME_ALREADY_EXISTS",
                        message="Programme name already exists in this client.",
                        status_code=HTTPStatus.CONFLICT,
                    )

            update_programme_entry(
                db,
                programme_id,
                name=payload.name,
                description=payload.description,
                status=payload.status,
            )
            row = get_programme_with_details_db(db, programme_id)
            if row is None:
                raise AppException(
                    code="PROGRAMME_NOT_FOUND",
                    message=f"Programme {programme_id} not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )

            prog, project_count, manager_name = row
            res = ProgrammeUpdateResponse.model_validate(prog)
            res.project_count = project_count
            res.manager_name = manager_name
            return res
        except AppException:
            logger.debug("programme_update_failed")
            raise
        except Exception as exc:
            logger.exception("programme_update_unexpected_failure")
            raise AppException(
                code="PROGRAMME_UPDATE_FAILED",
                message="Unable to update the programme right now.",
                status_code=500,
            ) from exc

    def delete_programme(
        self, db: Session, programme_id: UUID, current_user_id: UUID
    ) -> dict[str, str]:
        """Delete a programme only if it has no active projects."""
        try:
            get_programme(db, programme_id)

            visible_ids = get_visible_programme_ids(db, current_user_id)
            if visible_ids is not None and programme_id not in visible_ids:
                raise AppException(
                    code="FORBIDDEN",
                    message="You do not have access to this programme.",
                    status_code=HTTPStatus.FORBIDDEN,
                )

            active_projects = count_active_projects_by_programme(db, programme_id)
            if active_projects > 0:
                raise AppException(
                    code="PROGRAMME_DELETE_BLOCKED",
                    message="Programme cannot be deleted because active projects exist.",
                    status_code=HTTPStatus.CONFLICT,
                )

            deleted = delete_programme_entry(db, programme_id)
            return {
                "deleted_programme_id": str(deleted.id),
                "deleted_programme_name": deleted.name,
            }
        except AppException:
            logger.debug("programme_delete_failed")
            raise
        except Exception as exc:
            logger.exception("programme_delete_unexpected_failure")
            raise AppException(
                code="PROGRAMME_DELETE_FAILED",
                message="Failed to delete programme",
                status_code=500,
            ) from exc
