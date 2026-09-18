"""Pydantic schemas for project teams."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AddTeamMembersPayload(BaseModel):
    user_ids: list[UUID]


class TeamMemberResponse(BaseModel):
    id: str | UUID
    user_id: str | UUID
    name: str
    email: str
    role: Optional[str] = "Team Member"
    hours_this_sprint: Optional[int] = 0
    status: str = "Active"

    model_config = ConfigDict(from_attributes=True)
