"""Database API routes."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user_id,
    require_project_permission_from_jira_request,
    require_project_permission_from_story_edit_log_payload,
    require_project_permission_from_story_save_payload,
    require_project_permission_from_story_status_lookup_payload,
)
from app.components.authorizer import Permission
from app.core.connection import get_db
from app.schemas.JiraSchemas import RequestModel
from app.schemas.user_stories import (
    ImportResponse,
    ImportStoriesRequest,
    StoryEditLogRequest,
    StoryEditLogResponse,
    StoryStatusLookupRequest,
    StoryStatusLookupResponse,
)
from app.services.databaseService import DatabaseService
from app.utils.audit_log import audit_log

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/database",
    tags=["Database"],
)

# Bump this when the test-case generation/save pipeline changes meaningfully
# (prompt version, schema version, etc). Surfaced as VERSION in Pipeline Run History.
TEST_GENERATOR_PIPELINE_VERSION = "1.0"


@router.post(
    "/save-test-cases",
    dependencies=[Depends(require_project_permission_from_jira_request(Permission.TESTCASE_SAVE))],
)
@audit_log(
    service="database",
    method="POST",
    endpoint="/database/save-test-cases",
    success_message="Test cases saved successfully",
    error_code="TESTCASE_SAVE_FAILED",
    error_message="Failed to save test cases",
    extra=lambda kw: {"project_id": kw["request"].projectId},
)
async def save_test_cases(
    request: RequestModel,
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    result = await DatabaseService.save_test_cases(
        request=request,
        db=db,
    )
    return result


@router.post(
    "/story-edit-log",
    response_model=StoryEditLogResponse,
    status_code=201,
    summary="Batch-save story field edit audit records",
    responses={500: {"description": "Database write failed"}},
    dependencies=[
        Depends(require_project_permission_from_story_edit_log_payload(Permission.STORY_EDIT_LOG))
    ],
)
@audit_log(
    service="database",
    method="POST",
    endpoint="/database/story-edit-log",
    success_status=201,
    success_message="Story edit log saved successfully",
    error_code="STORY_EDIT_LOG_SAVE_FAILED",
    error_message="Failed to save story edit log",
)
async def save_story_edit_log(
    payload: StoryEditLogRequest,
    db: Annotated[Session, Depends(get_db)],
):
    saved = DatabaseService.save_story_edit_log(
        db=db,
        edit_log=payload.edit_log,
    )
    return StoryEditLogResponse(saved=saved)


@router.post(
    "/save-stories",
    response_model=ImportResponse,
    dependencies=[
        Depends(require_project_permission_from_story_save_payload(Permission.STORY_SAVE))
    ],
)
@audit_log(
    service="database",
    method="POST",
    endpoint="/database/save-stories",
    success_message="Stories saved successfully",
    error_code="STORIES_SAVE_FAILED",
    error_message="Failed to save stories",
    extra=lambda kw: {"project_id": kw["payload"].project_id},
)
async def save_stories(
    payload: ImportStoriesRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    result = DatabaseService.save_selected_stories(
        db=db,
        selected_epics=payload.selected_epics,
        project_id=payload.project_id,
    )
    return result


@router.post(
    "/story-statuses",
    response_model=StoryStatusLookupResponse,
    summary="Look up existing DB status for story keys (enriches non-Jira imports)",
    dependencies=[
        Depends(require_project_permission_from_story_status_lookup_payload(Permission.STORY_SAVE))
    ],
)
@audit_log(
    service="database",
    method="POST",
    endpoint="/database/story-statuses",
    success_message="Story statuses fetched successfully",
    error_code="STORY_STATUS_LOOKUP_FAILED",
    error_message="Failed to look up story statuses",
    extra=lambda kw: {"project_id": kw["payload"].project_id},
)
async def get_story_statuses(
    payload: StoryStatusLookupRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    statuses = DatabaseService.get_story_statuses(
        db=db,
        project_id=payload.project_id,
        story_keys=payload.story_keys,
    )
    return StoryStatusLookupResponse(statuses=statuses)
