from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path

from app.api.dependencies import get_current_user_id, get_programme_service, require_permission
from app.components.authorizer import Permission
from app.database.access_scope_db import get_visible_project_ids
from app.database.projects_db import list_projects_by_programme_id
from app.schemas.common import SuccessResponse
from app.schemas.programmes import (
    ProgrammeCreateRequest,
    ProgrammeDetailResponse,
    ProgrammeResponse,
    ProgrammeUpdateRequest,
    ProgrammeUpdateResponse,
    ProjectAssociationResponse,
)
from app.services.programmes import ProgrammesService
from app.utils.audit_context import client_name_for_client_id, client_name_for_programme_id
from app.utils.audit_log import audit_log

router = APIRouter(prefix="/programmes", tags=["Programmes"])


@router.post(
    "",
    response_model=SuccessResponse[ProgrammeResponse],
    response_model_exclude_none=True,
    status_code=201,
    summary="Create a new programme",
    dependencies=[Depends(require_permission(Permission.PROGRAMME_CREATE))],
)
@audit_log(
    service="programmes",
    method="POST",
    endpoint="/programmes",
    success_status=201,
    error_code="PROGRAMME_CREATE_FAILED",
    error_message="Failed to create programme",
    extra=lambda kw: {
        "client_name": client_name_for_client_id(kw["service"].db, kw["payload"].client_id)
    },
)
def create_programme(
    payload: ProgrammeCreateRequest,
    service: Annotated[ProgrammesService, Depends(get_programme_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[ProgrammeResponse]:
    data = service.create_programme(service.db, payload, current_user_id)
    return SuccessResponse(message="Programme created successfully", data=data)


@router.get(
    "",
    response_model=SuccessResponse[list[ProgrammeResponse]],
    response_model_exclude_none=True,
    summary="List all active programmes",
    dependencies=[Depends(require_permission(Permission.PROGRAMME_READ))],
)
@audit_log(
    service="programmes",
    method="GET",
    endpoint="/programmes",
    error_code="PROGRAMME_LIST_FAILED",
    error_message="Failed to fetch programmes",
    extra=lambda kw: {
        "client_name": client_name_for_client_id(kw["service"].db, kw.get("client_id"))
    },
)
def list_programmes(
    service: Annotated[ProgrammesService, Depends(get_programme_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    client_id: UUID | None = None,
) -> SuccessResponse[list[ProgrammeResponse]]:
    data = service.list_programmes(service.db, current_user_id, client_id=client_id)
    return SuccessResponse(message="Programmes retrieved successfully", data=data)


@router.get(
    "/{programme_id}",
    response_model=SuccessResponse[ProgrammeDetailResponse],
    response_model_exclude_none=True,
    summary="Fetch programme details",
    dependencies=[Depends(require_permission(Permission.PROGRAMME_READ))],
)
@audit_log(
    service="programmes",
    method="GET",
    endpoint="/programmes/{programme_id}",
    error_code="PROGRAMME_DETAILS_FETCH_FAILED",
    error_message="Failed to fetch programme details",
)
def get_programme_details(
    programme_id: Annotated[UUID, Path()],
    service: Annotated[ProgrammesService, Depends(get_programme_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[ProgrammeDetailResponse]:
    data = service.get_programme_details(service.db, programme_id, current_user_id)
    return SuccessResponse(message="Programme retrieved successfully", data=data)


@router.get(
    "/{programme_id}/projects",
    response_model=SuccessResponse[list[ProjectAssociationResponse]],
    response_model_exclude_none=True,
    summary="Fetch all projects for a programme",
    dependencies=[Depends(require_permission(Permission.PROJECT_READ))],
)
@audit_log(
    service="programmes",
    method="GET",
    endpoint="/programmes/{programme_id}/projects",
    error_code="PROGRAMME_PROJECTS_FETCH_FAILED",
    error_message="Failed to fetch programme projects",
)
def get_programme_projects(
    programme_id: Annotated[UUID, Path()],
    service: Annotated[ProgrammesService, Depends(get_programme_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[list[ProjectAssociationResponse]]:
    projects = list_projects_by_programme_id(service.db, programme_id)

    visible_project_ids = get_visible_project_ids(service.db, current_user_id)
    if visible_project_ids is not None:
        projects = [p for p in projects if p.id in visible_project_ids]

    data = [ProjectAssociationResponse.model_validate(p) for p in projects]
    return SuccessResponse(message="Programme projects retrieved successfully", data=data)


@router.patch(
    "/{programme_id}",
    response_model=SuccessResponse[ProgrammeUpdateResponse],
    response_model_exclude_none=True,
    summary="Update a programme",
    dependencies=[Depends(require_permission(Permission.PROGRAMME_UPDATE))],
)
@audit_log(
    service="programmes",
    method="PATCH",
    endpoint="/programmes/{programme_id}",
    error_code="PROGRAMME_UPDATE_FAILED",
    error_message="Failed to update programme",
    extra=lambda kw: {
        "client_name": client_name_for_programme_id(kw["service"].db, kw["programme_id"])
    },
)
def update_programme(
    programme_id: Annotated[UUID, Path()],
    payload: ProgrammeUpdateRequest,
    service: Annotated[ProgrammesService, Depends(get_programme_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[ProgrammeUpdateResponse]:
    data = service.update_programme(service.db, programme_id, payload, current_user_id)
    return SuccessResponse(message="Programme updated successfully", data=data)


@router.delete(
    "/{programme_id}",
    response_model=SuccessResponse[dict],
    response_model_exclude_none=True,
    summary="Archive (soft delete) a programme",
    dependencies=[Depends(require_permission(Permission.PROGRAMME_DELETE))],
)
@audit_log(
    service="programmes",
    method="DELETE",
    endpoint="/programmes/{programme_id}",
    error_code="PROGRAMME_DELETE_FAILED",
    error_message="Failed to delete programme",
    extra=lambda kw: {
        "client_name": client_name_for_programme_id(kw["service"].db, kw["programme_id"])
    },
)
def delete_programme(
    programme_id: Annotated[UUID, Path()],
    service: Annotated[ProgrammesService, Depends(get_programme_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[dict]:
    deleted = service.delete_programme(service.db, programme_id, current_user_id)
    return SuccessResponse(message="Programme deleted successfully", data=deleted)
