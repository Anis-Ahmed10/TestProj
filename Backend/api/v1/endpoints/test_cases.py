"""Test case status management endpoints."""

from __future__ import annotations

import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user_id,
    require_permission,
    require_project_permission_for_test_case_status,
    require_visible_project,
)
from app.components.authorizer import Permission
from app.core.connection import get_db
from app.database.crud_test_cases import count_test_cases_by_project
from app.schemas.common import SuccessResponse
from app.schemas.test_cases import (
    BulkUpdateTestCaseStatusResponse,
    ProjectLibraryResponse,
    ProjectTestCaseSummary,
    StatusFilter,
    UpdateTestCasesStatusByIdsRequest,
)
from app.services.test_case_service import (
    bulk_update_status_by_ids,
    fetch_test_library_payload_by_project,
)
from app.utils.audit_log import audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test-cases", tags=["Test Case Service"])


@router.get(
    "/library/{project_id}",
    response_model=SuccessResponse[list[ProjectLibraryResponse]],
    response_model_exclude_none=True,
    summary="Fetch nested test library for a specific project",
    dependencies=[
        Depends(require_permission(Permission.TESTCASE_LIBRARY_READ)),
        Depends(require_visible_project),
    ],
)
@audit_log(
    service="test_cases",
    method="GET",
    endpoint="/test-cases/library/{project_id}",
    error_code="TEST_LIBRARY_BY_PROJECT_FETCH_FAILED",
    error_message="Failed to fetch test library for project",
    extra=lambda kw: {"project_id": kw["project_id"]},
)
def get_test_library_by_project(
    project_id: UUID,
    status: Annotated[
        Literal["approved", "pending", "all", "unapproved"] | None,
        Query(description="Filter: approved, pending, unapproved, or all"),
    ] = "approved",
    db: Session = Depends(get_db),
) -> SuccessResponse[list[ProjectLibraryResponse]]:
    normalized_status: StatusFilter = (
        "pending" if status == "unapproved" else (status or "approved")
    )
    payload = fetch_test_library_payload_by_project(
        db, project_id, status_filter=normalized_status
    )
    return SuccessResponse(
        message="Test library retrieved successfully",
        data=payload,
    )


@router.patch(
    "/status",
    response_model=SuccessResponse[BulkUpdateTestCaseStatusResponse],
    response_model_exclude_none=True,
    dependencies=[
        Depends(require_project_permission_for_test_case_status(Permission.TESTCASE_UPDATE))
    ],
)
@audit_log(
    service="test_cases",
    method="PATCH",
    endpoint="/test-cases/status",
    error_code="TEST_CASE_STATUS_UPDATE_FAILED",
    error_message="Failed to update test case statuses",
    extra=lambda kw: {"project_id": kw["payload"].project_id},
)
async def update_test_case_statuses_by_ids(
    payload: UpdateTestCasesStatusByIdsRequest,
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Session = Depends(get_db),
):
    result = bulk_update_status_by_ids(
        db,
        test_case_ids=payload.ids,
        new_status=payload.status,
        project_id=payload.project_id,
    )
    message = (
        f"Test case status update completed: {result['updated_count']} updated to "
        f"'{payload.status.value}'"
    )
    logger.info(
        "User %s updated %s test case(s) to %s: ids=%s",
        current_user_id,
        result["updated_count"],
        payload.status.value,
        payload.ids,
    )
    return SuccessResponse(
        message=message,
        data=BulkUpdateTestCaseStatusResponse(**result),
    )


@router.get(
    "/project/{project_id}/summary",
    response_model=SuccessResponse[ProjectTestCaseSummary],
    response_model_exclude_none=True,
    summary="Get test case counts for a project (Overview / Recent Activity)",
    dependencies=[
        Depends(require_permission(Permission.TESTCASE_SUMMARY_READ)),
        Depends(require_visible_project),
    ],
)
async def get_project_test_case_summary(
    project_id: UUID,
    db: Session = Depends(get_db),
):
    summary = count_test_cases_by_project(db, project_id)
    return SuccessResponse(
        message="Test case summary retrieved successfully",
        data=ProjectTestCaseSummary(**summary),
    )
