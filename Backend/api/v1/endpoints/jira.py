from __future__ import annotations

from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query

from app.api.dependencies import (
    get_current_user_id,
    get_jira_service,
    require_permission,
    require_project_permission_from_jira_request,
    require_visible_project,
)
from app.components.authorizer import Permission
from app.schemas.JiraSchemas import (
    JiraConfigRequest,
    JiraConfigResponse,
    JiraCredentialsRequest,
    JiraCredentialsResponse,
    JiraTestConnectionResponse,
    PushToJiraResponse,
    RequestModel,
)
from app.schemas.user_stories import (
    ApplyRefreshResponse,
    EpicResponse,
    JiraEpicUpdate,
    RefreshStoriesResponse,
)
from app.services.jiraService import JiraService
from app.utils.audit_log import audit_log

T = TypeVar("T")


def _field(result: object, name: str, default: T = None) -> T:
    return (
        result.get(name, default) if isinstance(result, dict) else getattr(result, name, default)
    )


router = APIRouter(
    prefix="/jira",
    tags=["Jira: Import/Export"],
)


@router.post(
    "/push-to-jira",
    response_model=PushToJiraResponse,
    dependencies=[Depends(require_project_permission_from_jira_request(Permission.JIRA_PUSH))],
)
@audit_log(
    service="jira",
    method="POST",
    endpoint="/jira/push-to-jira",
    success_message=lambda kw, result: (
        f"direction:Push|items:{result.total} test case(s)|"
        f"details:{result.pushed_count}/{result.total} pushed, "
        f"{result.duplicate_count} duplicate(s), {result.failed_count} failed"
    ),
    error_message="Failed to push to Jira",
    extra=lambda kw: {"project_id": kw["request"].projectId},
)
async def push_to_jira(
    request: RequestModel,
    service: Annotated[JiraService, Depends(get_jira_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    """Push processed test cases to Jira."""
    return await service.push_to_jira(request, current_user_id)


@router.get(
    "/fetch-issues/{project_id}",
    response_model=list[EpicResponse],
    dependencies=[
        Depends(require_permission(Permission.JIRA_PULL)),
        Depends(require_visible_project),
    ],
)
@audit_log(
    service="jira",
    method="GET",
    endpoint="/jira/fetch-issues",
    success_message=lambda kw, result: (
        f"direction:Pull|items:"
        f"{sum(len(_field(epic, 'user_stories', [])) for epic in result)} user stor(y/ies), "
        f"{len(result)} epic(s)|details:Jira issues fetched successfully"
    ),
    error_message="Failed to fetch Jira issues",
    extra=lambda kw: {"project_id": kw["project_id"]},
)
async def fetch_jira(
    project_id: UUID,
    service: Annotated[JiraService, Depends(get_jira_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    status: Annotated[list[str], Query()] = [],
):
    """
    Fetch issues from Jira using the Jira URL/Project Key saved on the project
    and the API token saved against the current user.

    When one or more `status` query params are supplied, only user stories in
    those statuses are returned; epics are always included for grouping.
    """
    jira_url, project_key, jira_email, api_token = service.get_project_jira_credentials(
        project_id, current_user_id
    )
    return await service.fetch_jira_data(
        jira_url=jira_url,
        project_key=project_key,
        api_token=api_token,
        statuses=status,
        project_id=project_id,
        db=service.db,
        jira_email=jira_email,
    )


@router.get(
    "/statuses/{project_id}",
    response_model=list[str],
    dependencies=[
        Depends(require_permission(Permission.JIRA_PULL)),
        Depends(require_visible_project),
    ],
)
@audit_log(
    service="jira",
    method="GET",
    endpoint="/jira/statuses",
    success_message=lambda kw, result: f"Fetched {len(result)} Jira status(es)",
    error_message="Failed to fetch Jira statuses",
    extra=lambda kw: {"project_id": kw["project_id"]},
)
async def fetch_jira_statuses(
    project_id: UUID,
    service: Annotated[JiraService, Depends(get_jira_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    jira_url, project_key, jira_email, api_token = service.get_project_jira_credentials(
        project_id, current_user_id
    )
    return await service.fetch_project_story_statuses(
        jira_url=jira_url,
        project_key=project_key,
        api_token=api_token,
        jira_email=jira_email,
    )


@router.get(
    "/config/{project_id}",
    response_model=JiraConfigResponse,
    dependencies=[
        Depends(require_permission(Permission.JIRA_CONFIG_READ)),
        Depends(require_visible_project),
    ],
)
@audit_log(
    service="jira",
    method="GET",
    endpoint="/jira/config",
    success_message="Jira config retrieved successfully",
    error_message="Failed to retrieve Jira config",
    extra=lambda kw: {"project_id": kw["project_id"]},
)
async def get_jira_config(
    project_id: UUID,
    service: Annotated[JiraService, Depends(get_jira_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    """Return the saved Jira URL / Project Key for a project."""
    return service.get_jira_config(project_id, current_user_id)


@router.put(
    "/config/{project_id}",
    response_model=JiraConfigResponse,
    dependencies=[
        Depends(require_permission(Permission.JIRA_CONFIG_UPDATE)),
        Depends(require_visible_project),
    ],
)
@audit_log(
    service="jira",
    method="PUT",
    endpoint="/jira/config",
    success_message="Jira config saved successfully",
    error_message="Failed to save Jira config",
    extra=lambda kw: {"project_id": kw["project_id"]},
)
async def save_jira_config(
    project_id: UUID,
    payload: JiraConfigRequest,
    service: Annotated[JiraService, Depends(get_jira_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    """Save a project's Jira URL/Project Key."""
    return service.save_jira_config(project_id, current_user_id, payload)


@router.get(
    "/my-credentials",
    response_model=JiraCredentialsResponse,
)
@audit_log(
    service="jira",
    method="GET",
    endpoint="/jira/my-credentials",
    success_message="Jira credentials retrieved successfully",
    error_message="Failed to retrieve Jira credentials",
)
async def get_my_jira_credentials(
    service: Annotated[JiraService, Depends(get_jira_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    """Return the caller's own saved Jira email (Profile page)."""
    return service.get_my_jira_credentials(current_user_id)


@router.put(
    "/my-credentials",
    response_model=JiraCredentialsResponse,
)
@audit_log(
    service="jira",
    method="PUT",
    endpoint="/jira/my-credentials",
    success_message="Jira credentials saved successfully",
    error_message="Failed to save Jira credentials",
)
async def save_my_jira_credentials(
    payload: JiraCredentialsRequest,
    service: Annotated[JiraService, Depends(get_jira_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    """Save the caller's own Jira email/API token (Profile page), after Jira
    confirms the token belongs to that email's account."""
    return await service.save_my_jira_credentials(current_user_id, payload)


@router.post(
    "/test-connection/{project_id}",
    response_model=JiraTestConnectionResponse,
    dependencies=[
        Depends(require_permission(Permission.JIRA_TEST_CONNECTION)),
        Depends(require_visible_project),
    ],
)
@audit_log(
    service="jira",
    method="POST",
    endpoint="/jira/test-connection",
    success_message="Jira connection test completed",
    error_message="Failed to test Jira connection",
    extra=lambda kw: {"project_id": kw["project_id"]},
)
async def test_jira_connection(
    project_id: UUID,
    service: Annotated[JiraService, Depends(get_jira_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    """Test the saved Jira connection for a project using a real Jira REST API call."""
    return await service.test_connection(project_id, current_user_id)


@router.get(
    "/refresh-imported-stories/{project_id}",
    response_model=RefreshStoriesResponse,
    dependencies=[
        Depends(require_permission(Permission.JIRA_REFRESH)),
        Depends(require_visible_project),
    ],
)
@audit_log(
    service="jira",
    method="GET",
    endpoint="/jira/refresh-imported-stories",
    success_message=lambda kw, result: (
        f"direction:Pull|items:"
        f"{len(_field(result, 'changed_story_keys', []))} changed, "
        f"{len(_field(result, 'new_story_keys', []))} new|details:Jira stories refresh checked"
    ),
    error_message="Failed to refresh Jira stories",
    extra=lambda kw: {"project_id": kw["project_id"]},
)
async def refresh_stories(
    project_id: UUID,
    service: Annotated[JiraService, Depends(get_jira_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    status: Annotated[list[str], Query()] = [],
):
    """
    Re-fetch Jira and compare against DB, honouring the same status filter as
    import so filtered-out stories aren't reported as new.
    """
    jira_url, project_key, jira_email, api_token = service.get_project_jira_credentials(
        project_id, current_user_id
    )
    return await service.refresh_imported_stories(
        jira_url=jira_url,
        project_key=project_key,
        api_token=api_token,
        project_id=project_id,
        statuses=status,
        jira_email=jira_email,
    )


@router.post(
    "/apply-refresh-changes/{project_id}",
    response_model=ApplyRefreshResponse,
    dependencies=[
        Depends(require_permission(Permission.JIRA_APPLY_REFRESH)),
        Depends(require_visible_project),
    ],
)
@audit_log(
    service="jira",
    method="POST",
    endpoint="/jira/apply-refresh-changes",
    success_message=lambda kw, result: (
        f"direction:Pull|items:{len(_field(result, 'updated', []))} story(ies) updated|"
        "details:Jira refresh changes applied successfully"
    ),
    error_message="Failed to apply Jira refresh changes",
    extra=lambda kw: {"project_id": kw["project_id"]},
)
async def apply_refresh_changes_endpoint(
    project_id: UUID,
    service: Annotated[JiraService, Depends(get_jira_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    status: Annotated[list[str], Query()] = [],
    payload: Annotated[list[JiraEpicUpdate] | None, Body()] = None,
):
    if payload:
        return await service.apply_refresh_updates_direct(
            fresh_epics=[
                epic.model_dump() if hasattr(epic, "model_dump") else epic for epic in payload
            ],
            project_id=project_id,
        )
    jira_url, project_key, jira_email, api_token = service.get_project_jira_credentials(
        project_id, current_user_id
    )
    return await service.apply_refresh_updates(
        jira_url=jira_url,
        project_key=project_key,
        api_token=api_token,
        project_id=project_id,
        statuses=status,
        jira_email=jira_email,
    )
