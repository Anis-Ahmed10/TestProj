"""Schemas for client management APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


def _strip_and_validate(value: Any, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} is required")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


class ClientCreateRequest(BaseModel):
    """Request payload for creating a client."""

    name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=255)
    location: str = Field(..., min_length=1, max_length=255)
    contact: str = Field(
        ...,
        validation_alias=AliasChoices("contact", "primaryContact", "primary_contact"),
        serialization_alias="contact",
        min_length=1,
        max_length=255,
    )

    @field_validator("name", "industry", "location", "contact")
    @classmethod
    def values_cannot_be_blank(cls, value: str, info) -> str:
        return _strip_and_validate(value, info.field_name.replace("_", " "))


class ClientResponse(BaseModel):
    """Response payload for a single client."""

    model_config = ConfigDict(from_attributes=True)

    id: int | str | UUID
    name: str
    industry: str
    location: str | None = None
    contact: str = Field(
        validation_alias=AliasChoices("contact", "primary_contact", "primaryContact"),
        serialization_alias="contact",
    )
    status: str
    manager_id: int | str | UUID | None = None
    manager_name: str | None = None
    programmes_count: int = 0
    projects_count: int = 0
    active_members_count: int = 0
    created_at: datetime
    last_modified: datetime


class ClientListResponse(BaseModel):
    """Response payload for the client list."""

    items: list[ClientResponse]
    total: int


class ClientUpdate(BaseModel):
    """Partial client update payload."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "name": "string",
                "industry": "string",
                "location": "string",
                "contact": "string",
                "status": "string",
                "manager": "string",
            }
        },
    )

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    industry: Optional[str] = Field(default=None, min_length=1, max_length=255)
    location: Optional[str] = Field(default=None, min_length=1, max_length=255)
    contact: Optional[str] = Field(default=None, min_length=1, max_length=255)
    status: Optional[str] = Field(default=None, min_length=1, max_length=50)
    manager_id: Optional[UUID] = None

    @field_validator("manager_id", mode="before")
    @classmethod
    def coerce_empty_manager_id_to_none(cls, value: Any) -> Optional[UUID]:
        if value == "" or value == "null" or value is None:
            return None
        return value

    @field_validator("name", "industry", "location", "contact", "status", mode="before")
    @classmethod
    def values_cannot_be_blank_or_null(cls, value: Any, info) -> str:
        return _strip_and_validate(value, info.field_name.replace("_", " "))


class ProgramResponse(BaseModel):
    """Program association returned on the client details response."""

    model_config = ConfigDict(extra="forbid")

    id: UUID | int
    name: str
    description: Optional[str] = None


class ClientDetailResponseNoTimestamps(BaseModel):
    """Client details response without created_at/last_modified fields."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int | str | UUID
    name: str
    industry: str
    location: str | None = None
    contact: str
    status: str
    manager_name: str | None = None
    manager_id: int | str | UUID | None = None
    programmes_count: int = 0
    projects_count: int = 0
    active_members_count: int = 0

    programs: list[ProgramResponse] = Field(default_factory=list)
