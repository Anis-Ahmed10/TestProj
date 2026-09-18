from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApplicationLogEntry(BaseModel):
    """A single persisted application log row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    logged_at: datetime
    service_name: str
    user_id: UUID | None = None
    user_email: str | None = None
    user_name: str | None = None
    http_method: str
    endpoint: str
    status_code: int | None = None
    message: str | None = None
    project_id: UUID | None = None
    client_name: str | None = None


class ApplicationLogsResponse(BaseModel):
    """Response payload for application logs."""

    logs: list[ApplicationLogEntry]
    total: int
