from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    """Named bundle of permissions assigned to a user."""

    TEST_LEAD = "Test Lead"
    TEST_MANAGER = "Test Manager"
    TEST_ENGINEER = "Test Engineer"


class Permission(str, Enum):
    """Fine-grained action an endpoint requires, named resource:action."""

    CLIENT_CREATE = "client:create"
    CLIENT_READ = "client:read"
    CLIENT_UPDATE = "client:update"
    CLIENT_DELETE = "client:delete"

    PROGRAMME_CREATE = "programme:create"
    PROGRAMME_READ = "programme:read"
    PROGRAMME_UPDATE = "programme:update"
    PROGRAMME_DELETE = "programme:delete"

    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"

    TESTCASE_GENERATE = "testcase:generate"
    TESTCASE_UPDATE = "testcase:update"
    TESTCASE_SAVE = "testcase:save"
    TESTCASE_SUMMARY_READ = "testcase:summary_read"
    TESTCASE_LIBRARY_READ = "testcase:library_read"

    AUTOMATION_ANALYZE = "automation:analyze"

    REGRESSION_READ = "regression:read"

    STORY_SAVE = "story:save"
    STORY_EDIT_LOG = "story:edit_log"
    STORY_REQUEST_APPROVAL = "story:request_approval"
    STORY_APPROVE = "story:approve"
    STORY_GET_PENDING_APPROVALS = "story:get_pending_approvals"
    STORY_GET_PROJECT_APPROVALS = "story:get_project_approvals"
    STORY_LIST_BY_PROJECT = "story:list_by_project"

    DOCUMENT_UPLOAD = "document:upload"
    LIST_DOCUMENTS = "document:list"
    DOCUMENT_DELETE = "document:delete"

    LOGS_READ = "logs:read"

    JIRA_PUSH = "jira:push"
    JIRA_PULL = "jira:pull"
    JIRA_APPLY_REFRESH = "jira:apply_refresh"
    JIRA_REFRESH = "jira:refresh"
    JIRA_CONFIG_READ = "jira:config_read"
    JIRA_CONFIG_UPDATE = "jira:config_update"
    JIRA_TEST_CONNECTION = "jira:test_connection"
    JIRA_TEST_CASES_READ = "jira:test_cases_read"
    LIST_APPROVAL_USERS = "list:approval_users"

    USER_MANAGE = "user:manage"

    TEAM_READ = "team:read"
    TEAM_ADD = "team:add"
    TEAM_REMOVE = "team:remove"
    TEAM_AVAILABLE_USERS = "team:available_users"


_ROLE_LOOKUP = {role.value.lower(): role for role in Role}


def parse_role(value: str | None) -> Role | None:
    """Resolve a stored role string to a Role, tolerating casing/whitespace drift."""

    if not value:
        return None
    return _ROLE_LOOKUP.get(value.strip().lower())


@dataclass(frozen=True)
class AuthenticatedUser:
    """Request-scoped identity context resolved from JWT + database.

    role is the display/fallback role name from users.role; effective authority
    is resolved by the Authorizer from the RBAC tables.
    """

    id: uuid.UUID
    name: str
    email: str
    role: str
    is_active: bool
