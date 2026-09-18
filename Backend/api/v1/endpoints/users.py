"""User directory API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    get_current_user,
    get_current_user_id,
    get_request_authorizer,
    get_users_service,
    require_permission,
    require_visible_project,
)
from app.components.authorizer import AuthenticatedUser, Authorizer, Permission
from app.schemas.common import SuccessResponse
from app.schemas.users import (
    MeResponse,
    ProjectApprover,
    RoleSummary,
    UpdateUserRoleRequest,
    UpdateUserRoleResponse,
    UserSummary,
)
from app.services.users import UsersService
from app.utils.audit_log import audit_log

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/current-user",
    response_model=SuccessResponse[MeResponse],
    summary="Fetch the authenticated caller's identity, role and permissions",
)
@audit_log(
    service="users",
    method="GET",
    endpoint="/users/current-user",
    success_message="Current user retrieved successfully",
    error_code="CURRENT_USER_RETRIEVAL_FAILED",
    error_message="Unable to fetch current user right now.",
)
def get_me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    authorizer: Annotated[Authorizer, Depends(get_request_authorizer)],
) -> SuccessResponse[MeResponse]:
    """Return the caller's profile with permissions resolved from the RBAC tables."""

    permissions = sorted(authorizer.permissions_for(current_user))
    return SuccessResponse(
        message="Current user retrieved successfully",
        data=MeResponse(
            id=current_user.id,
            name=current_user.name,
            email=current_user.email,
            role=current_user.role,
            permissions=permissions,
        ),
    )


@router.get(
    "/approval-users",
    response_model=SuccessResponse[list[ProjectApprover]],
    response_model_exclude_none=True,
    summary="List the reviewers a project's stories can be sent to",
    dependencies=[
        Depends(require_permission(Permission.LIST_APPROVAL_USERS)),
        Depends(require_visible_project),
    ],
)
@audit_log(
    service="users",
    method="GET",
    endpoint="/users/approval-users",
    error_code="APPROVAL_USERS_LIST_FAILED",
    error_message="Unable to fetch approval users right now.",
)
def list_approval_users(
    service: Annotated[UsersService, Depends(get_users_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    project_id: Annotated[UUID, Query()],
) -> SuccessResponse[list[ProjectApprover]]:
    """List the project's manager and lead, the only selectable reviewers."""
    data = service.list_approval_users(service.db, project_id)
    return SuccessResponse(message="Approval users retrieved successfully", data=data)


@router.get(
    "",
    response_model=SuccessResponse[list[UserSummary]],
    response_model_exclude_none=True,
    summary="List all users",
    dependencies=[Depends(require_permission(Permission.USER_MANAGE))],
)
@audit_log(
    service="users",
    method="GET",
    endpoint="/users",
    error_code="USERS_LIST_FAILED",
    error_message="Unable to fetch users right now.",
)
def list_users(
    service: Annotated[UsersService, Depends(get_users_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[list[UserSummary]]:
    """List all active users."""
    data = service.list_users(service.db)
    return SuccessResponse(message="Users List retrieved successfully", data=data)


@router.get(
    "/roles",
    response_model=SuccessResponse[list[RoleSummary]],
    summary="List all available roles",
    dependencies=[Depends(require_permission(Permission.USER_MANAGE))],
)
@audit_log(
    service="users",
    method="GET",
    endpoint="/users/roles",
    success_message="Roles retrieved successfully",
    error_code="ROLES_LIST_FAILED",
    error_message="Unable to fetch roles right now.",
)
def list_roles(
    service: Annotated[UsersService, Depends(get_users_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[list[RoleSummary]]:
    """Return all roles from the roles table for frontend pickers."""
    data = service.list_roles(service.db)
    return SuccessResponse(message="Roles retrieved successfully", data=data)


@router.patch(
    "/{user_id}",
    response_model=SuccessResponse[UpdateUserRoleResponse],
    summary="Update a user's role",
    dependencies=[Depends(require_permission(Permission.USER_MANAGE))],
)
@audit_log(
    service="users",
    method="PATCH",
    endpoint="/users/{user_id}",
    success_message="User role updated successfully",
    error_code="UPDATE_USER_ROLE_FAILED",
    error_message="Unable to update user role right now.",
)
def update_user_role(
    user_id: UUID,
    body: UpdateUserRoleRequest,
    service: Annotated[UsersService, Depends(get_users_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[UpdateUserRoleResponse]:
    """Assign a new role to the specified user.

    Validates that both the user and the role exist before persisting the change.
    Requires USER_MANAGE permission.
    """
    data = service.update_user_role(service.db, user_id, body.role_name)
    return SuccessResponse(message="User role updated successfully", data=data)
