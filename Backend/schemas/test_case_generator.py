"""Schemas for test case generation."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class TestCaseFormat(str, Enum):
    """Supported test case output formats."""

    standard = "standard"  # ID, steps, expected, precondition
    bdd = "bdd"  # Given, When, Then


class CoverageDepth(str, Enum):
    """Supported coverage depth values."""

    smoke = "smoke"  # Happy path only
    standard = "standard"  # Happy path + negative paths
    comprehensive = "comprehensive"  # All paths including edge cases, security, regression


class PriorityAssignment(str, Enum):
    """Supported priority assignment strategies."""

    auto_risk = "auto_risk"  # AI auto-assigns based on risk analysis
    all_high = "all_high"  # Mark all tests as high priority
    manual = "manual"  # User will assign later (no priority in response)


@dataclass
class BatchArtifact:
    """Encapsulates a finalized batch with precomputed prompt rendering."""

    payload: dict[str, Any]
    story_contexts: dict[str, dict[str, str]]
    rendered_prompt: str
    estimated_size: int


class TestCaseGenerationContextDocument(BaseModel):
    """Context document supplied to the generator."""

    document_id: str = Field(
        ...,
        validation_alias=AliasChoices("documentId", "document_id"),
        serialization_alias="documentId",
        max_length=100,
    )
    title: str = Field(
        ...,
        validation_alias=AliasChoices("title"),
        serialization_alias="title",
        min_length=1,
        max_length=250,
    )
    link: str = Field(
        ...,
        validation_alias=AliasChoices("link"),
        serialization_alias="link",
        min_length=1,
        max_length=2_048,
    )

    @field_validator("link")
    @classmethod
    def link_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("link cannot be empty")
        return value


class TestCaseGenerationStory(BaseModel):
    """Structured story nested inside an epic."""

    story_key: str = Field(
        ...,
        validation_alias=AliasChoices("storyId", "storyKey", "story_key"),
        serialization_alias="storyKey",
        max_length=100,
    )
    summary: str = Field(
        ...,
        validation_alias=AliasChoices("storyTitle", "summary"),
        serialization_alias="summary",
        min_length=1,
        max_length=1_000,
    )
    description: str = Field(
        ...,
        validation_alias=AliasChoices("description"),
        serialization_alias="description",
        min_length=1,
        max_length=10_000,
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("acceptanceCriteria", "acceptance_criteria"),
        serialization_alias="acceptanceCriteria",
    )

    @field_validator("summary", "description")
    @classmethod
    def text_fields_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("story text cannot be empty")
        return value

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def normalize_acceptance_criteria(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [
                item for item in (part.strip() for part in re.split(r"[\r\n;]+", value)) if item
            ]
        if isinstance(value, tuple):
            value = list(value)
        if isinstance(value, list):
            normalized: list[str] = []
            for item in value:
                text = str(item).strip()
                if text:
                    normalized.append(text)
            return normalized
        raise ValueError("acceptanceCriteria must be a string or an array of strings")


class TestCaseGenerationEpic(BaseModel):
    """Epic containing one or more stories."""

    epic_key: str = Field(
        ...,
        validation_alias=AliasChoices("epicId", "epicKey", "epic_key"),
        serialization_alias="epicKey",
        max_length=100,
    )
    epic_summary: str = Field(
        ...,
        validation_alias=AliasChoices("epicTitle", "epicSummary", "epic_summary"),
        serialization_alias="epicSummary",
        min_length=1,
        max_length=1_000,
    )
    stories: list[TestCaseGenerationStory] = Field(
        ...,
        validation_alias=AliasChoices("stories"),
        serialization_alias="stories",
        min_length=1,
    )

    @field_validator("epic_summary")
    @classmethod
    def epic_summary_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("epicSummary cannot be empty")
        return value


def _normalize_format(value: str) -> str:
    normalized = value.strip().lower()
    mapping = {
        "structured (id, steps, expected)": "standard",
        "bdd (given/when/then)": "bdd",
    }
    if normalized not in mapping:
        raise ValueError(
            "settings.format must be one of: Structured (ID, Steps, Expected), "
            "BDD (Given/When/Then)"
        )
    return mapping[normalized]


def _normalize_coverage(value: str) -> str:
    normalized = value.strip().lower()
    mapping = {
        "standard (happy + negative)": "standard",
        "comprehensive (all paths)": "comprehensive",
        "smoke (happy path only)": "smoke",
    }
    if normalized not in mapping:
        raise ValueError(
            "settings.coverage must be one of: Standard (Happy + Negative), "
            "Comprehensive (All paths), Smoke (Happy path only)"
        )
    return mapping[normalized]


def _normalize_priority(value: str) -> str:
    normalized = value.strip().lower()
    mapping = {
        "auto-assign by risk": "auto_risk",
        "all high": "all_high",
        "manual": "manual",
    }
    if normalized not in mapping:
        raise ValueError("settings.priority must be one of: Auto-assign by risk, All High, Manual")
    return mapping[normalized]


class TestCaseGenerationSettings(BaseModel):
    """Frontend-selected generation settings."""

    format: str = Field(..., min_length=1, max_length=100)
    coverage: str = Field(..., min_length=1, max_length=100)
    priority: str = Field(..., min_length=1, max_length=100)

    @field_validator("format")
    @classmethod
    def format_must_be_supported(cls, value: str) -> str:
        return _normalize_format(value)

    @field_validator("coverage")
    @classmethod
    def coverage_must_be_supported(cls, value: str) -> str:
        return _normalize_coverage(value)

    @field_validator("priority")
    @classmethod
    def priority_must_be_supported(cls, value: str) -> str:
        return _normalize_priority(value)


class TestCaseGenerationRequest(BaseModel):
    """Request payload for generating test cases."""

    impact_prompt: str | None = Field(
        default=None,
        validation_alias=AliasChoices("impactPrompt", "impact_prompt"),
        serialization_alias="impactPrompt",
        max_length=10_000,
    )
    context_documents: list[TestCaseGenerationContextDocument] = Field(
        default_factory=list, alias="contextDocuments"
    )
    epics: list[TestCaseGenerationEpic] = Field(...)
    settings: TestCaseGenerationSettings

    @field_validator("context_documents", mode="before")
    @classmethod
    def normalize_context_documents(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @field_validator("epics", mode="before")
    @classmethod
    def normalize_epics(cls, value: Any) -> Any:
        if value is None:
            return []
        return value

    @model_validator(mode="after")
    def require_supported_input(self) -> "TestCaseGenerationRequest":
        if not self.epics:
            raise ValueError("Request must include epics")
        if not self.context_documents:
            raise ValueError("Request must include contextDocuments")
        return self


class TestCaseGenerationTestCase(BaseModel):
    """Single generated test case in the UI response."""

    test_case_id: str = Field(
        ...,
        validation_alias=AliasChoices("testCaseId", "test_case_id", "id"),
        serialization_alias="testCaseId",
        min_length=1,
        max_length=100,
    )
    title: str = Field(..., min_length=1, max_length=500)
    type: str = Field(..., min_length=1, max_length=100)
    priority: str | None = Field(default=None, min_length=1, max_length=50)
    preconditions: list[str] = Field(default_factory=list)
    test_data: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("testData", "test_data"),
        serialization_alias="testData",
    )
    expected_result: str = Field(
        ...,
        validation_alias=AliasChoices("expectedResult", "expected_result"),
        serialization_alias="expectedResult",
        min_length=1,
        max_length=10_000,
    )
    tags: list[str] = Field(default_factory=list)

    @field_validator("test_case_id", "title", "type", "expected_result")
    @classmethod
    def text_fields_cannot_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field cannot be empty")
        return value

    @field_validator("priority")
    @classmethod
    def priority_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("field cannot be empty")
        return value

    model_config = ConfigDict(extra="forbid")


class TestCaseGenerationStandardTestCase(TestCaseGenerationTestCase):
    """Standard-format generated test case."""

    steps: list[str] = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")


class TestCaseGenerationBddTestCase(TestCaseGenerationTestCase):
    """BDD-format generated test case."""

    scenario: dict[str, Any] = Field(
        ...,
        validation_alias=AliasChoices("scenario"),
        serialization_alias="scenario",
    )

    model_config = ConfigDict(extra="forbid")


class TestCaseGenerationStoryResult(BaseModel):
    """Story-level grouping in the UI response."""

    story_key: str = Field(
        ...,
        validation_alias=AliasChoices("storyKey", "story_key"),
        serialization_alias="storyKey",
        min_length=1,
        max_length=100,
    )
    story_summary: str = Field(
        ...,
        validation_alias=AliasChoices("storySummary", "story_summary", "summary"),
        serialization_alias="storySummary",
        min_length=1,
        max_length=1_000,
    )
    test_cases: list[TestCaseGenerationStandardTestCase | TestCaseGenerationBddTestCase] | None = (
        Field(
            default=None,
            validation_alias=AliasChoices("testCases", "test_cases"),
            serialization_alias="testCases",
        )
    )


class TestCaseGenerationEpicResult(BaseModel):
    """Epic-level grouping in the UI response."""

    epic_key: str = Field(
        ...,
        validation_alias=AliasChoices("epicKey", "epic_key"),
        serialization_alias="epicKey",
        min_length=1,
        max_length=100,
    )
    epic_summary: str = Field(
        ...,
        validation_alias=AliasChoices("epicSummary", "epic_summary"),
        serialization_alias="epicSummary",
        min_length=1,
        max_length=1_000,
    )
    stories: list[TestCaseGenerationStoryResult] = Field(default_factory=list)


class TestCaseGenerationIssueTraceability(BaseModel):
    """Epic/story pair attached to a generation issue."""

    epic_key: str = Field(
        ...,
        validation_alias=AliasChoices("epicKey", "epic_key"),
        serialization_alias="epicKey",
        min_length=1,
        max_length=100,
    )
    story_key: str = Field(
        ...,
        validation_alias=AliasChoices("storyKey", "story_key"),
        serialization_alias="storyKey",
        min_length=1,
        max_length=100,
    )


class TestCaseGenerationIssue(BaseModel):
    """Non-fatal batch failure details included with partial results."""

    story_keys: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("storyKeys", "story_keys"),
        serialization_alias="storyKeys",
    )
    epic_keys: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("epicKeys", "epic_keys"),
        serialization_alias="epicKeys",
    )
    traceability: list[TestCaseGenerationIssueTraceability] = Field(
        default_factory=list,
        validation_alias=AliasChoices("traceability", "traceability_items"),
        serialization_alias="traceability",
    )
    code: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=2_000)


class TestCaseGenerationMetadata(BaseModel):
    """Response metadata for the UI."""

    generated_at: str = Field(
        ...,
        validation_alias=AliasChoices("generatedAt", "generated_at"),
        serialization_alias="generatedAt",
    )
    format: str = Field(..., min_length=1, max_length=100)
    coverage: str = Field(..., min_length=1, max_length=100)
    priority_mode: str = Field(
        ...,
        validation_alias=AliasChoices("priorityMode", "priority_mode"),
        serialization_alias="priorityMode",
        min_length=1,
        max_length=50,
    )
    total_epics: int = Field(
        ...,
        validation_alias=AliasChoices("totalEpics", "total_epics"),
        serialization_alias="totalEpics",
        ge=0,
    )
    total_stories: int = Field(
        ...,
        validation_alias=AliasChoices("totalStories", "total_stories"),
        serialization_alias="totalStories",
        ge=0,
    )
    total_test_cases: int = Field(
        ...,
        validation_alias=AliasChoices("totalTestCases", "total_test_cases"),
        serialization_alias="totalTestCases",
        ge=0,
    )


class TestCaseGenerationData(BaseModel):
    """Nested response payload returned to the UI."""

    metadata: TestCaseGenerationMetadata
    generated_test_cases: list[TestCaseGenerationEpicResult] = Field(
        default_factory=list,
        validation_alias=AliasChoices("generatedTestCases", "generated_test_cases"),
        serialization_alias="generatedTestCases",
    )
    generation_issues: list[TestCaseGenerationIssue] = Field(
        default_factory=list,
        validation_alias=AliasChoices("generationIssues", "generation_issues"),
        serialization_alias="generationIssues",
    )


def current_utc_isoformat() -> str:
    """Return a UTC timestamp formatted for UI metadata."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
