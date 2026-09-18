from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_id, require_permission
from app.components.authorizer.models import Permission
from app.core.connection import get_db
from app.database.application_log_db import list_log_entries
from app.schemas.application_logs import ApplicationLogEntry, ApplicationLogsResponse
from app.schemas.common import SuccessResponse
from app.utils.audit_log import audit_log

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get(
    "",
    response_model=SuccessResponse[ApplicationLogsResponse],
    response_model_exclude_none=True,
    status_code=200,
    summary="Get application logs",
    dependencies=[Depends(require_permission(Permission.LOGS_READ))],
)
@audit_log(
    service="logs",
    method="GET",
    endpoint="/logs",
    error_code="LOGS_FETCH_FAILED",
    error_message="Failed to fetch application logs",
)
def get_application_logs(
    db: Annotated[Session, Depends(get_db)],
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[
        str | None,
        Query(description="Filter by service, e.g. 'ai' or 'jira'"),
    ] = None,
    project_id: Annotated[
        str | None,
        Query(description="Filter by project id"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuccessResponse[ApplicationLogsResponse]:
    """Return application audit logs, newest first, optionally filtered by
    service and/or project."""
    entries, total = list_log_entries(
        db,
        service_name=service,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )
    data = ApplicationLogsResponse(
        logs=[ApplicationLogEntry.model_validate(entry) for entry in entries],
        total=total,
    )
    message = "Application logs retrieved successfully" if entries else "No application logs found"
    return SuccessResponse(message=message, data=data)
