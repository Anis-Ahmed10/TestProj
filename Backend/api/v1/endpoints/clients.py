from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path

from app.api.dependencies import get_client_service, get_current_user_id, require_permission
from app.components.authorizer import Permission
from app.schemas.clients import (
    ClientCreateRequest,
    ClientDetailResponseNoTimestamps,
    ClientListResponse,
    ClientResponse,
    ClientUpdate,
)
from app.schemas.common import SuccessResponse
from app.services.clients import ClientService
from app.utils.audit_log import audit_log

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.post(
    "",
    response_model=SuccessResponse[ClientResponse],
    response_model_exclude_none=True,
    status_code=201,
    summary="Create a new client",
    dependencies=[Depends(require_permission(Permission.CLIENT_CREATE))],
)
@audit_log(
    service="clients",
    method="POST",
    endpoint="/clients",
    success_status=201,
    error_code="CLIENT_CREATE_FAILED",
    error_message="Failed to create client",
    extra=lambda kw: {"client_name": kw["payload"].name},
)
def create_client(
    payload: ClientCreateRequest,
    service: Annotated[ClientService, Depends(get_client_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[ClientResponse]:
    client = service.create_client(service.db, payload, manager_id=current_user_id)
    return SuccessResponse(message="Client created successfully", data=client)


@router.get(
    "",
    response_model=SuccessResponse[ClientListResponse],
    response_model_exclude_none=True,
    summary="List clients",
    dependencies=[Depends(require_permission(Permission.CLIENT_READ))],
)
@audit_log(
    service="clients",
    method="GET",
    endpoint="/clients",
    error_code="CLIENT_LIST_FAILED",
    error_message="Failed to fetch clients",
)
def list_clients(
    service: Annotated[ClientService, Depends(get_client_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[ClientListResponse]:
    client_list = service.list_clients(service.db, current_user_id)
    message = "Clients retrieved successfully" if client_list.items else "No clients available"
    return SuccessResponse(message=message, data=client_list)


@router.get(
    "/{client_name}",
    response_model=SuccessResponse[ClientDetailResponseNoTimestamps],
    response_model_exclude_none=True,
    summary="Fetch client details",
    dependencies=[Depends(require_permission(Permission.CLIENT_READ))],
)
@audit_log(
    service="clients",
    method="GET",
    endpoint="/clients/{client_name}",
    error_code="CLIENT_DETAILS_FETCH_FAILED",
    error_message="Failed to fetch client details",
    extra=lambda kw: {"client_name": kw["client_name"]},
)
def get_client_details(
    client_name: Annotated[str, Path(min_length=1, max_length=255)],
    service: Annotated[ClientService, Depends(get_client_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[ClientDetailResponseNoTimestamps]:
    data = service.get_client_details(client_name=client_name, current_user_id=current_user_id)
    return SuccessResponse(message="Client retrieved successfully", data=data)


@router.patch(
    "/{client_name}",
    response_model=SuccessResponse[ClientResponse],
    response_model_exclude_none=True,
    summary="Update client details",
    dependencies=[Depends(require_permission(Permission.CLIENT_UPDATE))],
)
@audit_log(
    service="clients",
    method="PATCH",
    endpoint="/clients/{client_name}",
    error_code="CLIENT_UPDATE_FAILED",
    error_message="Failed to update client",
    extra=lambda kw: {"client_name": kw["client_name"]},
)
def update_client(
    client_name: Annotated[str, Path(min_length=1, max_length=255)],
    payload: ClientUpdate,
    service: Annotated[ClientService, Depends(get_client_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[ClientResponse]:
    data = service.update_client(
        client_name=client_name, payload=payload, current_user_id=current_user_id
    )
    return SuccessResponse(message="Client updated successfully", data=data)


@router.delete(
    "/{client_name}",
    response_model=SuccessResponse[dict],
    response_model_exclude_none=True,
    summary="Archive (soft delete) a client",
    dependencies=[Depends(require_permission(Permission.CLIENT_DELETE))],
)
@audit_log(
    service="clients",
    method="DELETE",
    endpoint="/clients/{client_name}",
    error_code="CLIENT_ARCHIVE_FAILED",
    error_message="Failed to archive client",
    extra=lambda kw: {"client_name": kw["client_name"]},
)
def archive_client(
    client_name: Annotated[str, Path(min_length=1, max_length=255)],
    service: Annotated[ClientService, Depends(get_client_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[dict]:
    archived_name = service.archive_client(
        client_name=client_name, current_user_id=current_user_id
    )
    return SuccessResponse(
        message="Client archived successfully",
        data={"archived_client_name": archived_name},
    )
