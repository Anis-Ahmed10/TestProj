from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.components.authorizer.models import AuthenticatedUser, Permission, Role
from app.database.rbac_db import get_permissions_for_role

_ALL_PERMISSIONS = frozenset(Permission)


_TEST_ENGINEER = {
    Permission.TESTCASE_GENERATE,
    Permission.TESTCASE_UPDATE,
    Permission.TESTCASE_SAVE,
    Permission.AUTOMATION_ANALYZE,
    Permission.REGRESSION_READ,
    Permission.STORY_EDIT_LOG,
    Permission.STORY_SAVE,
    Permission.JIRA_PULL,
    Permission.JIRA_PUSH,
    Permission.JIRA_APPLY_REFRESH,
    Permission.JIRA_REFRESH,
    Permission.DOCUMENT_UPLOAD,
    Permission.STORY_GET_PENDING_APPROVALS,
    Permission.STORY_GET_PROJECT_APPROVALS,
    Permission.STORY_REQUEST_APPROVAL,
    Permission.STORY_LIST_BY_PROJECT,
    Permission.PROGRAMME_READ,
    Permission.PROJECT_READ,
    Permission.CLIENT_READ,
    Permission.TESTCASE_SUMMARY_READ,
    Permission.JIRA_CONFIG_READ,
    Permission.JIRA_CONFIG_UPDATE,
    Permission.JIRA_TEST_CONNECTION,
    Permission.JIRA_TEST_CASES_READ,
    Permission.LIST_DOCUMENTS,
    Permission.TESTCASE_LIBRARY_READ,
    Permission.TEAM_READ,
    Permission.LIST_APPROVAL_USERS,
}

_EXCLUDED_TEST_LEAD_PERMISSIONS = {
    Permission.CLIENT_CREATE,
    Permission.CLIENT_UPDATE,
    Permission.CLIENT_DELETE,
    Permission.PROGRAMME_CREATE,
    Permission.PROGRAMME_UPDATE,
    Permission.PROGRAMME_DELETE,
    Permission.LOGS_READ,
    Permission.USER_MANAGE,
}

TEST_MANAGER = _ALL_PERMISSIONS

TEST_LEAD = _ALL_PERMISSIONS - _EXCLUDED_TEST_LEAD_PERMISSIONS

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.TEST_LEAD: frozenset(TEST_LEAD),
    Role.TEST_MANAGER: frozenset(TEST_MANAGER),
    Role.TEST_ENGINEER: frozenset(_TEST_ENGINEER),
}


class Authorizer(Protocol):
    """Swappable policy-decision contract consulted by enforcement dependencies."""

    def has_permission(self, user: AuthenticatedUser, permission: Permission) -> bool: ...

    def permissions_for(self, user: AuthenticatedUser) -> frozenset[str]: ...


class DbAuthorizer:
    """Active policy engine; resolves permissions from the RBAC tables per request."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def has_permission(self, user: AuthenticatedUser, permission: Permission) -> bool:
        return permission.value in self.permissions_for(user)

    def permissions_for(self, user: AuthenticatedUser) -> frozenset[str]:
        return get_permissions_for_role(self._db, user.role)


def get_authorizer(db: Session) -> Authorizer:
    """Return the active policy engine; swap the implementation here, not in endpoints."""

    return DbAuthorizer(db)
