from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user_id,
    get_project_service,
    get_teams_service,
    require_permission,
    require_project_permission,
    require_visible_project,
)
from app.components.authorizer import Permission
from app.core.connection import get_db
from app.core.exceptions import AppException
from app.database.access_scope_db import get_visible_project_ids
from app.database.user_stories_db import get_approved_user_stories_by_project
from app.schemas.common import SuccessResponse
from app.schemas.projects import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
    ProjectUpdateResponse,
)
from app.schemas.teams import AddTeamMembersPayload, TeamMemberResponse
from app.schemas.user_stories import ProjectUserStoryResponse
from app.schemas.users import UserSummary
from app.services.projects import ProjectsService
from app.services.teams import TeamsService
from app.utils.audit_context import client_name_for_programme_id, client_name_for_project_id
from app.utils.audit_log import audit_log

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post(
    "",
    response_model=SuccessResponse[ProjectResponse],
    response_model_exclude_none=True,
    status_code=201,
    summary="Create a new project",
    dependencies=[Depends(require_permission(Permission.PROJECT_CREATE))],
)
@audit_log(
    service="projects",
    method="POST",
    endpoint="/projects/create",
    success_status=201,
    error_code="PROJECT_CREATE_FAILED",
    error_message="Failed to create project",
    extra=lambda kw: {
        "client_name": client_name_for_programme_id(kw["service"].db, kw["payload"].programme_id)
    },
)
def create_project(
    payload: ProjectCreateRequest,
    service: Annotated[ProjectsService, Depends(get_project_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[ProjectResponse]:
    data = service.create_project(service.db, payload, current_user_id)
    return SuccessResponse(message="Project created successfully", data=data)


@router.get(
    "",
    response_model=SuccessResponse[list[ProjectResponse]],
    response_model_exclude_none=True,
    summary="List active projects",
    dependencies=[Depends(require_permission(Permission.PROJECT_READ))],
)
@audit_log(
    service="projects",
    method="GET",
    endpoint="/projects",
    error_code="PROJECT_LIST_FAILED",
    error_message="Failed to fetch projects",
)
def list_projects(
    service: Annotated[ProjectsService, Depends(get_project_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[list[ProjectResponse]]:
    data = service.list_projects(service.db, current_user_id)
    return SuccessResponse(message="Projects retrieved successfully", data=data)


@router.patch(
    "/{project_id}",
    response_model=SuccessResponse[ProjectUpdateResponse],
    response_model_exclude_none=True,
    summary="Update a project",
    dependencies=[Depends(require_project_permission(Permission.PROJECT_UPDATE))],
)
@audit_log(
    service="projects",
    method="PATCH",
    endpoint="/projects/{project_id}",
    error_code="PROJECT_UPDATE_FAILED",
    error_message="Failed to update project",
    extra=lambda kw: {
        "project_id": kw["project_id"],
        "client_name": client_name_for_project_id(kw["service"].db, kw["project_id"]),
    },
)
def update_project(
    project_id: Annotated[UUID, Path()],
    payload: ProjectUpdateRequest,
    service: Annotated[ProjectsService, Depends(get_project_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[ProjectUpdateResponse]:
    data = service.update_project(service.db, project_id, payload, current_user_id)
    return SuccessResponse(message="Project updated successfully", data=data)


@router.delete(
    "/{project_id}",
    response_model=SuccessResponse[dict],
    response_model_exclude_none=True,
    summary="Soft delete a project",
    dependencies=[Depends(require_project_permission(Permission.PROJECT_DELETE))],
)
@audit_log(
    service="projects",
    method="DELETE",
    endpoint="/projects/{project_id}",
    error_code="PROJECT_DELETE_FAILED",
    error_message="Failed to delete project",
    extra=lambda kw: {
        "project_id": kw["project_id"],
        "client_name": client_name_for_project_id(kw["service"].db, kw["project_id"]),
    },
)
def delete_project(
    project_id: Annotated[UUID, Path()],
    service: Annotated[ProjectsService, Depends(get_project_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[dict]:
    deleted = service.delete_project(service.db, project_id, current_user_id)
    return SuccessResponse(message="Project deleted successfully", data=deleted)


@router.get(
    "/{project_id}/team",
    response_model=SuccessResponse[list[TeamMemberResponse]],
    summary="Get all team members for a project",
    dependencies=[Depends(require_project_permission(Permission.TEAM_READ))],
)
@audit_log(
    service="teams",
    method="GET",
    endpoint="/projects/{project_id}/team",
    error_code="TEAM_MEMBERS_FETCH_FAILED",
    error_message="Unable to fetch team members right now.",
)
def get_team_members(
    project_id: UUID,
    service: Annotated[TeamsService, Depends(get_teams_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[list[TeamMemberResponse]]:
    """Fetch all users currently assigned to a project."""
    data = service.get_project_team_members(project_id, current_user_id)
    return SuccessResponse(message="Team members retrieved successfully", data=data)


@router.get(
    "/{project_id}/team/available-users",
    response_model=SuccessResponse[list[UserSummary]],
    summary="List users not currently in the project",
    dependencies=[Depends(require_project_permission(Permission.TEAM_AVAILABLE_USERS))],
)
@audit_log(
    service="teams",
    method="GET",
    endpoint="/projects/{project_id}/team/available-users",
    error_code="AVAILABLE_USERS_FETCH_FAILED",
    error_message="Unable to fetch available users right now.",
)
def get_available_users(
    project_id: UUID,
    service: Annotated[TeamsService, Depends(get_teams_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[list[UserSummary]]:
    """Fetch users to populate the 'Add Member' multiselect popup."""
    data = service.get_available_users(project_id, current_user_id)
    return SuccessResponse(message="Available users retrieved successfully", data=data)


@router.post(
    "/{project_id}/team",
    response_model=SuccessResponse[list[TeamMemberResponse]],
    summary="Add multiple members to the project",
    dependencies=[Depends(require_project_permission(Permission.TEAM_ADD))],
)
@audit_log(
    service="teams",
    method="POST",
    endpoint="/projects/{project_id}/team",
    success_message="Team members added successfully",
    error_code="TEAM_MEMBERS_ADD_FAILED",
    error_message="Unable to add team members right now.",
    extra=lambda kw: {"project_id": kw["project_id"]},
)
def add_team_members(
    project_id: UUID,
    payload: AddTeamMembersPayload,
    service: Annotated[TeamsService, Depends(get_teams_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[list[TeamMemberResponse]]:
    """Assign multiple users to a project simultaneously."""
    data = service.add_members_to_project(project_id, payload.user_ids, current_user_id)
    added_count = len(payload.user_ids)
    return SuccessResponse(message=f"{added_count} Members added successfully", data=data)


@router.delete(
    "/{project_id}/team/{user_id}",
    response_model=SuccessResponse[dict],
    summary="Remove a member from the project",
    dependencies=[Depends(require_project_permission(Permission.TEAM_REMOVE))],
)
@audit_log(
    service="teams",
    method="DELETE",
    endpoint="/projects/{project_id}/team/{user_id}",
    success_message="Team member removed successfully",
    error_code="TEAM_MEMBER_REMOVE_FAILED",
    error_message="Unable to remove team member right now.",
    extra=lambda kw: {"project_id": kw["project_id"]},
)
def remove_team_member(
    project_id: UUID,
    user_id: UUID,
    service: Annotated[TeamsService, Depends(get_teams_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[dict]:
    """Remove a user from a project team."""
    removed_member = service.remove_member_from_project(project_id, user_id, current_user_id)
    return SuccessResponse(
        message=f"Team member {user_id} removed successfully", data=removed_member
    )


@router.get(
    "/{project_id}/user-stories",
    response_model=SuccessResponse[list[ProjectUserStoryResponse]],
    response_model_exclude_none=True,
    summary="Get all approved user stories for a project",
    dependencies=[
        Depends(require_permission(Permission.STORY_LIST_BY_PROJECT)),
        Depends(require_visible_project),
    ],
)
@audit_log(
    service="projects",
    method="GET",
    endpoint="/projects/{project_id}/user-stories",
    error_code="PROJECT_USER_STORIES_FETCH_FAILED",
    error_message="Unable to fetch user stories for this project right now.",
)
def get_project_user_stories(
    project_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[list[ProjectUserStoryResponse]]:
    """Return every approved user story for a project (e.g. for the Regression
    Analyzer's story picker). Returns an empty list if none exist."""
    visible_ids = get_visible_project_ids(db, current_user_id)
    if visible_ids is not None and project_id not in visible_ids:
        raise AppException(
            code="FORBIDDEN",
            message="You do not have access to this project.",
            status_code=403,
        )
    stories = get_approved_user_stories_by_project(db, project_id)
    data = [
        ProjectUserStoryResponse(
            storyId=story.story_key,
            jiraIssueKey=story.story_key,
            title=story.title,
            description=story.description or "",
        )
        for story in stories
        if story.story_key
    ]
    return SuccessResponse(message="User stories retrieved successfully", data=data)
