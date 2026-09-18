"""Schemas for user story and epic requests/responses."""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class StoryResponse(BaseModel):
    storyId: str

    storyTitle: str

    description: str

    acceptanceCriteria: Optional[str] = None

    issue_type: str

    already_exists: bool = False

    status: str

    priority: Optional[str] = None


class ProjectUserStoryResponse(BaseModel):
    """Response shape for a single approved user story belonging to a project."""

    storyId: str = Field(..., description="Business story key, e.g. a Jira issue key")

    jiraIssueKey: Optional[str] = Field(
        default=None,
        description="Jira issue key for this story, when it originated from Jira",
    )

    title: str

    description: str = ""


class EpicResponse(BaseModel):
    epicId: str

    epicTitle: str

    user_stories: List[StoryResponse]


class StoryRequest(BaseModel):
    storyId: str

    storyTitle: str

    description: str

    acceptanceCriteria: Optional[str] = None

    issue_type: str

    priority: Optional[str] = Field(
        default=None,
        description=(
            "Priority as supplied by the source (Jira value or a manual selection), stored as-is."
        ),
    )


class SelectedEpic(BaseModel):
    epicId: str
    epicTitle: str = ""
    user_stories: List[StoryRequest]


class ImportStoriesRequest(BaseModel):
    selected_epics: List[SelectedEpic]
    project_id: UUID = Field(..., description="Project these stories belong to")


class StoryStatusLookupRequest(BaseModel):
    """Look up existing DB status for a set of story keys — used by non-Jira imports
    (Excel/CSV) which are parsed client-side and can't get the Jira fetch enrichment."""

    project_id: UUID
    story_keys: List[str] = Field(default_factory=list)


class StoryStatusEntry(BaseModel):
    already_exists: bool = False
    status: str = "pending"


class StoryStatusLookupResponse(BaseModel):
    statuses: dict[str, StoryStatusEntry] = Field(default_factory=dict)


class ImportResponse(BaseModel):
    success: bool

    inserted: list[str] = []

    updated: list[str] = []

    failed: list[str] = []

    failed_reasons: list[dict] = []

    skipped: list[str] = []

    renamed: list[dict] = []


class RefreshStoriesResponse(BaseModel):
    success: bool

    imported_count: int = 0
    updated_count: int = 0
    failed_count: int = 0

    changed_story_keys: list[str] = []
    new_story_keys: list[str] = []


class ApplyRefreshResponse(BaseModel):
    success: bool = True
    updated: list[str] = Field(default_factory=list)


class JiraStoryUpdate(BaseModel):
    storyId: str
    storyTitle: str
    description: str = ""
    acceptanceCriteria: Optional[str] = None
    issue_type: str = "Story"
    already_exists: Optional[bool] = False
    status: Optional[str] = None


class JiraEpicUpdate(BaseModel):
    epicId: Optional[str] = None
    epicTitle: Optional[str] = None
    user_stories: List[JiraStoryUpdate] = Field(default_factory=list)


class StoryChangeSchema(BaseModel):
    field: Literal["storyTitle", "description", "acceptanceCriteria"]
    before: str = ""
    after: str = ""


class StoryEditRecordSchema(BaseModel):
    storyId: str = Field(min_length=1, max_length=100)
    epicId: str = Field(min_length=1, max_length=100)
    changes: List[StoryChangeSchema] = Field(min_length=1)
    editedAt: datetime


class StoryEditLogRequest(BaseModel):
    project_id: UUID = Field(..., description="Project the edited stories belong to")
    edit_log: List[StoryEditRecordSchema] = Field(min_length=1, max_length=500)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "edit_log": [
                        {
                            "storyId": "STORY-42",
                            "epicId": "EPIC-7",
                            "editedAt": "2026-06-24T10:00:00Z",
                            "changes": [
                                {
                                    "field": "storyTitle",
                                    "before": "Old title",
                                    "after": "New title",
                                }
                            ],
                        }
                    ]
                }
            ]
        }
    }


class StoryEditLogResponse(BaseModel):
    saved: int
