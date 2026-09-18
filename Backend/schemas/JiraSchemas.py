"""Schemas for Jira and test case requests/responses."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class TestCase(BaseModel):
    """Schema representing a single test case."""

    __test__ = False

    id: Optional[str] = None
    tc_id: Optional[str] = None

    title: str
    priority: str

    steps: Optional[Union[str, List[str]]] = None

    expected: Optional[Union[str, List[str]]] = None

    tags: Optional[List[str]] = None

    scenario: Optional[Dict[str, Any]] = None

    preconditions: Optional[List[str]] = None

    charter_mission: Optional[str] = None
    charter_focus: Optional[str] = None
    charter_duration: Optional[str] = None

    charter_scope: Optional[Union[str, List[str]]] = None

    techniques: Optional[Union[str, List[str]]] = None

    def normalize(self):
        """Normalize test case fields for processing."""

        if not self.id and self.tc_id:
            self.id = self.tc_id

        def normalize_list_field(value):

            match value:

                case list():
                    return " | ".join(value)

                case _:
                    return value

        self.steps = normalize_list_field(self.steps)

        self.expected = normalize_list_field(self.expected)

        if self.scenario:

            self.steps = None
            self.expected = None

            self.scenario["given"] = normalize_list_field(
                self.scenario.get(
                    "given",
                    [],
                )
            )

            self.scenario["when"] = normalize_list_field(
                self.scenario.get(
                    "when",
                    [],
                )
            )

            self.scenario["then"] = normalize_list_field(
                self.scenario.get(
                    "then",
                    [],
                )
            )

        if self.charter_mission:

            self.steps = None
            self.expected = None

        self.charter_scope = normalize_list_field(self.charter_scope)

        self.techniques = normalize_list_field(self.techniques)

        return self


class RequestModel(BaseModel):
    """Schema for JiraSchemas request payload."""

    userStoryId: str

    projectId: str

    format: Literal[
        "standard",
        "bdd",
        "exploratory",
    ]

    test_cases: List[TestCase]


class PushedTestCase(BaseModel):
    tc_id: str
    jira_key: Optional[str] = None
    status: Literal["pushed", "duplicate", "failed"]
    rename_note: Optional[str] = None


class PushToJiraResponse(BaseModel):
    total: int
    pushed_count: int
    duplicate_count: int
    failed_count: int
    db_saved_count: int

    pushed: List[PushedTestCase] = []
    duplicates: List[str] = []
    failed: List[dict] = []

    db_skipped: List[str] = []
    db_failed: List[str] = []

    project_link: str = ""


# jira import related schemas


class JiraFetchRequest(BaseModel):
    jira_url: str = Field(..., json_schema_extra={"example": "https://company.atlassian.net"})

    project_key: str = Field(..., json_schema_extra={"example": "ADTD"})

    api_token: str

    last_sync: Optional[datetime] = None


# jira per-project configuration (settings screen)


class JiraConfigRequest(BaseModel):
    """Payload to save a project's Jira URL/Project Key."""

    jira_url: Optional[str] = Field(
        default=None, json_schema_extra={"example": "https://company.atlassian.net"}
    )
    project_key: Optional[str] = Field(default=None, json_schema_extra={"example": "ADTD"})


class JiraConfigResponse(BaseModel):
    """Current Jira URL/Project Key config for a project."""

    jira_url: Optional[str] = None
    project_key: Optional[str] = None
    is_connected: bool = False


class JiraTestConnectionResponse(BaseModel):
    """Result of testing the Jira connection."""

    success: bool
    message: str


# jira per-user credentials (Profile page)


class JiraCredentialsRequest(BaseModel):
    """Payload to save the caller's own Jira email and API token."""

    jira_email: Optional[str] = Field(default=None, max_length=255)
    api_token: Optional[str] = Field(default=None, max_length=300)


class JiraCredentialsResponse(BaseModel):
    """The caller's saved Jira email; api_token is never returned, only whether it is set."""

    jira_email: Optional[str] = None
    has_api_token: bool = False
