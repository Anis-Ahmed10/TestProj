"""Story approval API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from app.api.dependencies import (
    get_current_user,
    get_current_user_id,
    get_story_approval_service,
    require_permission,
    require_project_permission_from_story_approval_submit_payload,
    require_visible_project,
)
from app.components.authorizer.models import AuthenticatedUser, Permission
from app.schemas.common import SuccessResponse
from app.schemas.story_approval import (
    ReviewQueueResponse,
    StoryApprovalDecisionRequest,
    StoryApprovalDecisionResponse,
    StoryApprovalRecord,
    StoryApprovalSubmitRequest,
    StoryApprovalSubmitResponse,
)
from app.services.story_approval import StoryApprovalService
from app.utils.audit_log import audit_log

router = APIRouter(prefix="/story-approvals", tags=["Story Approvals"])


@router.post(
    "",
    response_model=SuccessResponse[StoryApprovalSubmitResponse],
    response_model_exclude_none=True,
    status_code=201,
    summary="Submit user stories for reviewer approval",
    dependencies=[
        Depends(
            require_project_permission_from_story_approval_submit_payload(
                Permission.STORY_REQUEST_APPROVAL
            )
        ),
    ],
)
@audit_log(
    service="story-approvals",
    method="POST",
    endpoint="/story-approvals",
    success_status=201,
    error_code="APPROVAL_SUBMIT_FAILED",
    error_message="Unable to submit stories for approval right now.",
)
def submit_for_approval(
    payload: StoryApprovalSubmitRequest,
    service: Annotated[StoryApprovalService, Depends(get_story_approval_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[StoryApprovalSubmitResponse]:
    """Send selected user stories for reviewer approval."""
    data = service.submit_for_approval(service.db, payload, current_user_id)
    return SuccessResponse(message="Stories submitted for approval successfully", data=data)


@router.get(
    "/review-queue",
    response_model=SuccessResponse[ReviewQueueResponse],
    response_model_exclude_none=True,
    summary="Review queue for the signed-in reviewer",
    dependencies=[Depends(require_permission(Permission.STORY_GET_PENDING_APPROVALS))],
)
@audit_log(
    service="story-approvals",
    method="GET",
    endpoint="/story-approvals/review-queue",
    error_code="APPROVAL_LIST_FAILED",
    error_message="Unable to fetch the review queue right now.",
)
def get_review_queue(
    service: Annotated[StoryApprovalService, Depends(get_story_approval_service)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    status: Annotated[str | None, Query()] = None,
    project_id: Annotated[UUID | None, Query()] = None,
    epic_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SuccessResponse[ReviewQueueResponse]:
    """Return one page of stories assigned to the signed-in reviewer, with counts."""
    data = service.get_review_queue(
        service.db,
        current_user.email,
        status=status,
        project_id=project_id,
        epic_id=epic_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return SuccessResponse(message="Review queue retrieved successfully", data=data)


@router.patch(
    "/{approval_id}/decision",
    response_model=SuccessResponse[StoryApprovalDecisionResponse],
    response_model_exclude_none=True,
    summary="Approve or reject an approval request",
    dependencies=[Depends(require_permission(Permission.STORY_APPROVE))],
)
@audit_log(
    service="story-approvals",
    method="PATCH",
    endpoint="/story-approvals/{approval_id}/decision",
    error_code="APPROVAL_DECIDE_FAILED",
    error_message="Unable to process approval decision right now.",
)
def decide_approval(
    approval_id: Annotated[UUID, Path()],
    payload: StoryApprovalDecisionRequest,
    service: Annotated[StoryApprovalService, Depends(get_story_approval_service)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> SuccessResponse[StoryApprovalDecisionResponse]:
    """Reviewer approves or rejects a pending approval request."""
    data = service.decide_approval(
        service.db,
        approval_id,
        payload.decision,
        decided_by=current_user.id,
        decided_by_email=current_user.email,
    )
    return SuccessResponse(message="Approval decision recorded successfully", data=data)


@router.get(
    "/project/{project_id}",
    response_model=SuccessResponse[list[StoryApprovalRecord]],
    response_model_exclude_none=True,
    summary="List all approvals for a project",
    dependencies=[
        Depends(require_permission(Permission.STORY_GET_PROJECT_APPROVALS)),
        Depends(require_visible_project),
    ],
)
@audit_log(
    service="story-approvals",
    method="GET",
    endpoint="/story-approvals/project/{project_id}",
    error_code="APPROVAL_LIST_FAILED",
    error_message="Unable to fetch project approvals right now.",
)
def list_project_approvals(
    project_id: Annotated[UUID, Path()],
    service: Annotated[StoryApprovalService, Depends(get_story_approval_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[list[StoryApprovalRecord]]:
    """Fetch all approval records for a project."""
    data = service.list_project_approvals(service.db, project_id)
    return SuccessResponse(message="Project approvals retrieved successfully", data=data)
