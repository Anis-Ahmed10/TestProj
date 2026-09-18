"""Schemas for programme APIs."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_required_text(value: Any, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} is required")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


class ProgrammeCreateRequest(BaseModel):
    """Request payload for creating a programme."""

    client_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)

    @field_validator("name")
    @classmethod
    def name_cannot_be_blank(cls, value: str) -> str:
        return _normalize_required_text(value, "programme name")

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ProgrammeUpdateRequest(BaseModel):
    """Request payload for updating a programme."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None, max_length=50)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            raise ValueError("programme name cannot be blank")
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
        allowed = {"active", "onhold", "complete"}
        text = str(value).strip().lower()
        if text not in allowed:
            raise ValueError("status must be active, onhold, or complete")
        return text


class ProgrammeUpdateResponse(BaseModel):
    """Response payload for a programme update — only the fields that can change."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | int
    client_id: UUID | int
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    manager_name: Optional[str] = None
    project_count: int = 0
    last_modified: Optional[datetime] = None


class ProgrammeResponse(BaseModel):
    """Response payload for a single programme."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | int
    client_id: UUID | int
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    manager_name: Optional[str] = None
    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    project_count: int = 0


class ProjectAssociationResponse(BaseModel):
    """Project association returned on the programme details response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | int
    name: str
    description: Optional[str] = None
    status: str
    lead_id: Optional[UUID | str] = None
    lead_name: Optional[str] = None
    start_date: Optional[date] = None
    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None


class ProgrammeDetailResponse(BaseModel):
    """Programme details response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | int
    client_id: UUID | int
    name: str
    description: Optional[str] = None
    status: str
    manager_name: Optional[str] = None
    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None

    projects: list[ProjectAssociationResponse] = Field(default_factory=list)
