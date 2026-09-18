"""Schemas for story approval request/response payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.user_stories import SelectedEpic


class StoryApprovalSubmitRequest(BaseModel):
    """Payload for sending user stories for reviewer approval.

    Carries full story content grouped by epic (not just ids) so submission can
    upsert the stories into user_stories in the same transaction that creates the
    approval requests — guaranteeing an approval request never exists without its
    story row (which the decision cascade and re-import status check depend on).

    The picker defaults `reviewer_emails` to the project's manager and lead but
    lets the submitter change it, so the chosen reviewers are checked against the
    users who actually hold approval rights before any request is created.
    """

    epics: list[SelectedEpic] = Field(min_length=1)
    project_id: UUID
    reviewer_emails: list[EmailStr] = Field(min_length=1)


class StoryApprovalRecord(BaseModel):
    """Single approval record response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_story_id: str
    project_id: UUID
    submitted_by: UUID
    reviewer_email: str
    status: str
    submitted_at: datetime
    decided_at: Optional[datetime] = None
    decided_by: Optional[UUID] = None


class StoryApprovalSkippedPair(BaseModel):
    """A (story, reviewer) pair that was not submitted because it was already pending."""

    user_story_id: str
    reviewer_email: str


class StoryApprovalSubmitResponse(BaseModel):
    """Response after submitting stories for approval."""

    submitted_count: int
    skipped_count: int
    approval_records: list[StoryApprovalRecord]
    skipped_pairs: list[StoryApprovalSkippedPair] = Field(default_factory=list)
    # Stories whose row could not be saved, so no approval request was created for them.
    failed_story_ids: list[str] = Field(default_factory=list)


class StoryApprovalDecisionRequest(BaseModel):
    """Payload for reviewer approve/reject action."""

    decision: Literal["approved", "rejected"]


class StoryApprovalDecisionResponse(BaseModel):
    """Response after a reviewer decision."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_story_id: str
    status: str
    decided_at: datetime
    decided_by: Optional[UUID] = None


class ReviewStory(BaseModel):
    """A pending/decided approval joined with its user story content for the review queue."""

    id: UUID
    user_story_id: str
    project_id: UUID
    project_name: str
    epic_id: Optional[str] = None
    epic_title: Optional[str] = None
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    priority: Optional[str] = None
    submitted_by: str
    submitted_at: datetime
    status: str
    decided_at: Optional[datetime] = None
    decided_by_name: Optional[str] = None


class ReviewQueueCounts(BaseModel):
    """Per-status counts across the reviewer's entire assigned set (unfiltered)."""

    pending: int = 0
    approved: int = 0
    rejected: int = 0


class ReviewQueueFacet(BaseModel):
    """A distinct filterable value (project or epic) in the reviewer's assigned set."""

    id: str
    label: str


class ReviewQueueFacets(BaseModel):
    """Complete filter-dropdown options, independent of the current page/filter."""

    projects: list[ReviewQueueFacet] = Field(default_factory=list)
    epics: list[ReviewQueueFacet] = Field(default_factory=list)


class ReviewQueueResponse(BaseModel):
    """Reviewer's review queue: one page of enriched stories, plus counts and facets."""

    stories: list[ReviewStory]
    counts: ReviewQueueCounts
    total: int = 0
    facets: ReviewQueueFacets = Field(default_factory=ReviewQueueFacets)
