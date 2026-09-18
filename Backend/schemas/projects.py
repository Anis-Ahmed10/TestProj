"""Schemas for project APIs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ALLOWED_STATUSES = {
    "active": "active",
    "onhold": "onhold",
    "complete": "complete",
}


def _normalize_required_text(value: Any, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} is required")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


class ProjectCreateRequest(BaseModel):
    """Request payload for creating a project."""

    programme_id: UUID
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(default=None)
    lead_id: Optional[UUID] = Field(default=None)
    status: Optional[str] = Field(default="active", max_length=50)
    start_date: Optional[date] = None

    @field_validator("name")
    @classmethod
    def name_cannot_be_blank(cls, value: str) -> str:
        return _normalize_required_text(value, "project name")

    @field_validator("description", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: Any) -> str:
        if value is None:
            return "active"
        text = str(value).strip()
        if not text:
            return "active"
        normalized = _ALLOWED_STATUSES.get(text.lower())
        if normalized is None:
            raise ValueError("status must be active, onhold, or complete")
        return normalized


class ProjectUpdateRequest(BaseModel):
    """Request payload for updating a project."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None, max_length=50)
    lead_id: Optional[UUID] = Field(default=None)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            raise ValueError("project name cannot be blank")
        if len(text) > 50:
            raise ValueError("project name must be 50 characters or fewer")
        return text

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip().lower()
        normalized = _ALLOWED_STATUSES.get(text)
        if normalized is None:
            raise ValueError("status must be active, onhold, or complete")
        return normalized


class ProjectUpdateResponse(BaseModel):
    """Response payload for a project update — only the fields that can change."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | int
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    lead_id: Optional[UUID] = Field(default=None)
    lead_name: Optional[str] = None
    last_modified: Optional[datetime] = None


class ProjectResponse(BaseModel):
    """Response payload for a single project."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | int
    programme_id: UUID | int
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    lead_id: Optional[UUID | str] = None
    lead_name: Optional[str] = None
    start_date: Optional[date] = None
    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    programme_name: Optional[str] = None
    client_id: Optional[UUID | int] = None
    client_name: Optional[str] = None


@dataclass
class ProjectListRow:
    id: UUID | int
    programme_id: UUID | int
    name: str
    description: str | None
    status: str
    last_modified: datetime
    programme_name: str
    client_id: UUID | int
    client_name: str
    lead_id: UUID | str | None = None
    lead_name: str | None = None
