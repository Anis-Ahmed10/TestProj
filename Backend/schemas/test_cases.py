# -----------------------------
# Test case status management
# -----------------------------
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field

StatusFilter = Literal["approved", "pending", "all"]


class TestCaseStatus(str, Enum):
    """Supported statuses for test cases."""

    pending = "pending"
    approved = "approved"
    archived = "archived"


class BulkTestCaseUpdateResult(BaseModel):
    """Per-test-case result for bulk operations."""

    id: str
    status: TestCaseStatus | None = None
    success: bool
    error: str | None = None


class BulkUpdateTestCaseStatusResponse(BaseModel):
    """Response payload for bulk status updates."""

    found_count: int
    updated_count: int
    results: list[BulkTestCaseUpdateResult]


class UpdateTestCasesStatusByIdsRequest(BaseModel):
    """Request payload to update one or more test case statuses by ids."""

    ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("testCaseIds", "ids", "test_case_ids"),
        serialization_alias="ids",
        min_length=1,
    )
    status: TestCaseStatus
    project_id: UUID = Field(
        ...,
        validation_alias=AliasChoices("projectId", "project_id"),
        serialization_alias="project_id",
    )


class StoryEditLogResponse(BaseModel):
    """Audit log payload for a user story."""

    changes: dict[str, Any] | list[Any] | None = None
    edited_at: datetime | None = None


class TestCaseLibraryResponse(BaseModel):
    """Test case payload for the nested library response (approved or pending)."""

    id: str
    title: str
    test_format_type: str | None = None
    test_data: dict[str, Any] | list[Any] | None = None
    jira_key: str | None = None
    status: str
    created_at: datetime | None = None


class UserStoryLibraryResponse(BaseModel):
    """User story payload for the nested library response."""

    id: str
    story_key: str | None = None
    title: str
    description: str | None = None
    acceptance_criteria: str | None = None
    priority: str | None = None
    story_edit_logs: list[StoryEditLogResponse] = Field(default_factory=list)
    test_cases: list[TestCaseLibraryResponse] = Field(default_factory=list)


class EpicLibraryResponse(BaseModel):
    """Epic payload for the nested library response."""

    epic_id: str
    epic_key: str
    epic_title: str
    user_stories: list[UserStoryLibraryResponse] = Field(default_factory=list)


class ProjectLibraryResponse(BaseModel):
    """Top-level project payload for the nested library response."""

    project_id: str
    project_name: str
    epics: list[EpicLibraryResponse] = Field(default_factory=list)


class ProjectTestCaseSummary(BaseModel):
    """Test case count breakdown for a single project (Overview / Recent Activity)."""

    total: int
    approved: int
    pending: int
    archived: int
    pass_rate: float
