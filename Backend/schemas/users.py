from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MeResponse(BaseModel):
    """Caller identity and authority; the contract the frontend gates its UI on."""

    id: UUID
    name: str
    email: str
    role: str
    permissions: list[str]


class UserSummary(BaseModel):
    """Lightweight user record for pickers/dropdowns."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role: str | None = None


class ProjectApprover(BaseModel):
    """A project's manager or lead — the only reviewers stories can be sent to."""

    role_label: str
    name: str
    email: str


class RoleSummary(BaseModel):
    """Lightweight role record for frontend pickers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None


class UpdateUserRoleRequest(BaseModel):
    """Payload to change a user's role; accepts the role name string."""

    role_name: str = Field(..., min_length=1, description="Name of the role to assign")


class UpdateUserRoleResponse(BaseModel):
    """Updated user record returned after a successful role change."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role: str | None = None
