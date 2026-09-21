"""FastAPI dependency providers."""

from __future__ import annotations

import logging
import uuid
from typing import Callable

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.components.authorizer import (
    AuthenticatedUser,
    Authorizer,
    Permission,
    get_authorizer,
    parse_role,
)
from app.core.config import Settings, get_settings
from app.core.connection import get_db
from app.core.exceptions import AppException, AuthorizationError
from app.database.access_scope_db import (
    get_visible_client_ids,
    get_visible_programme_ids,
    get_visible_project_ids,
)
from app.database.crud_test_cases import (
    get_project_id_for_user_story,
    get_project_ids_for_story_ids,
    get_project_ids_for_test_case_ids,
)
from app.database.users_db import create_user_on_signup, get_user_by_email
from app.schemas.file_operations import ConfirmUploadRequest, DuplicateCheckRequest
from app.schemas.JiraSchemas import RequestModel
from app.schemas.story_approval import StoryApprovalSubmitRequest
from app.schemas.test_cases import UpdateTestCasesStatusByIdsRequest
from app.schemas.user_stories import (
    ImportStoriesRequest,
    StoryEditLogRequest,
    StoryStatusLookupRequest,
)
from app.services.clients import ClientService
from app.services.file_operations import FileOperationsService
from app.services.jiraService import JiraService
from app.services.programmes import ProgrammesService
from app.services.projects import ProjectsService
from app.services.story_approval import StoryApprovalService
from app.services.teams import TeamsService
from app.services.users import UsersService
from app.utils.jwt import decode_jwt_payload

logger = logging.getLogger(__name__)


def get_app_settings() -> Settings:
    return get_settings()


def get_file_operations_service(db: Session = Depends(get_db)) -> FileOperationsService:
    return FileOperationsService(db=db)


def get_jira_service(db: Session = Depends(get_db)) -> JiraService:
    return JiraService(db=db)


def get_client_service(db: Session = Depends(get_db)):
    return ClientService(db=db)


def get_programme_service(db: Session = Depends(get_db)):
    return ProgrammesService(db=db)


def get_project_service(db: Session = Depends(get_db)):
    return ProjectsService(db=db)


def get_request_authorizer(db: Session = Depends(get_db)) -> Authorizer:
    return get_authorizer(db)


def get_story_approval_service(db: Session = Depends(get_db)):
    return StoryApprovalService(db=db)


def get_users_service(db: Session = Depends(get_db)):
    return UsersService(db=db)


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """Resolve the caller's identity from the JWT and their authority from the database."""

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = decode_jwt_payload(token)
        email = claims.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Token missing email claim")
        cognito_id = uuid.UUID(claims["sub"])
        name = claims.get("name") or ""
    except ValueError:
        raise HTTPException(status_code=401, detail="Missing or invalid authorization token")
    except KeyError:
        raise HTTPException(status_code=401, detail="Token missing required Cognito claims")

    user = get_user_by_email(db, email)
    if user is None:
        user = create_user_on_signup(db, cognito_id, name=name, email=email)

    if not user.is_active:
        logger.warning("authz_inactive_user_rejected", extra={"user_id": str(user.id)})
        raise AuthorizationError("User account is deactivated")

    canonical = parse_role(user.role)
    role_name = canonical.value if canonical else (user.role or "").strip()

    return AuthenticatedUser(
        id=user.id,
        name=user.name,
        email=user.email,
        role=role_name,
        is_active=user.is_active,
    )


def get_current_user_id(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> uuid.UUID:
    """Backwards-compatible identity dependency; delegates to get_current_user."""

    return current_user.id


def require_permission(permission: Permission) -> Callable[..., None]:
    """Build a dependency that rejects callers whose role lacks the given permission."""

    def dependency(
        current_user: AuthenticatedUser = Depends(get_current_user),
        authorizer: Authorizer = Depends(get_request_authorizer),
    ) -> None:
        if not authorizer.has_permission(current_user, permission):
            logger.warning(
                "authz_denied",
                extra={
                    "user_id": str(current_user.id),
                    "user_role": current_user.role,
                    "permission": permission.value,
                },
            )
            raise AuthorizationError()

    return dependency


def get_teams_service(db: Session = Depends(get_db)) -> TeamsService:
    """Dependency injection for the Teams service."""
    return TeamsService(db)


def require_visible_project(
    project_id: uuid.UUID,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    """Dependency that 403s if project_id is outside the caller's visibility scope."""
    visible_ids = get_visible_project_ids(db, current_user_id)
    if visible_ids is not None and project_id not in visible_ids:
        logger.warning(
            "project_access_denied",
            extra={"user_id": str(current_user_id), "project_id": str(project_id)},
        )
        raise AppException(
            code="FORBIDDEN",
            message="You do not have access to this project.",
            status_code=403,
        )
    return project_id


def _authorize_for_project(
    *,
    current_user: AuthenticatedUser,
    project_id: uuid.UUID,
    permission: Permission,
    authorizer: Authorizer,
    db: Session,
) -> None:
    if not authorizer.has_permission(current_user, permission):
        logger.warning(
            "authz_denied",
            extra={
                "user_id": str(current_user.id),
                "user_role": current_user.role,
                "permission": permission.value,
            },
        )
        raise AuthorizationError()

    visible_ids = get_visible_project_ids(db, current_user.id)
    if visible_ids is not None and project_id not in visible_ids:
        logger.warning(
            "project_access_denied",
            extra={
                "user_id": str(current_user.id),
                "project_id": str(project_id),
                "permission": permission.value,
            },
        )
        raise AppException(
            code="FORBIDDEN",
            message="You do not have access to this project.",
            status_code=403,
        )


def require_project_permission(permission: Permission) -> Callable[..., uuid.UUID]:
    def dependency(
        project_id: uuid.UUID,
        current_user: AuthenticatedUser = Depends(get_current_user),
        authorizer: Authorizer = Depends(get_request_authorizer),
        db: Session = Depends(get_db),
    ) -> uuid.UUID:
        _authorize_for_project(
            current_user=current_user,
            project_id=project_id,
            permission=permission,
            authorizer=authorizer,
            db=db,
        )
        return project_id

    return dependency


def require_project_permission_from_jira_request(
    permission: Permission,
) -> Callable[..., RequestModel]:
    """Same gate, for routes whose project_id arrives as request.projectId."""

    def dependency(
        request: RequestModel,
        current_user: AuthenticatedUser = Depends(get_current_user),
        authorizer: Authorizer = Depends(get_request_authorizer),
        db: Session = Depends(get_db),
    ) -> RequestModel:
        try:
            declared_project_id = uuid.UUID(request.projectId)
        except ValueError:
            raise AppException(
                code="INVALID_PROJECT_ID",
                message="projectId must be a valid UUID.",
                status_code=422,
            )

        _authorize_for_project(
            current_user=current_user,
            project_id=declared_project_id,
            permission=permission,
            authorizer=authorizer,
            db=db,
        )

        actual_project_id = get_project_id_for_user_story(db, request.userStoryId)
        if actual_project_id is not None and actual_project_id != declared_project_id:
            logger.warning(
                "test_case_story_project_mismatch",
                extra={
                    "user_id": str(current_user.id),
                    "declared_project_id": str(declared_project_id),
                    "actual_project_id": str(actual_project_id),
                },
            )
            raise AppException(
                code="FORBIDDEN",
                message="This user story does not belong to the given project.",
                status_code=403,
            )

        return request

    return dependency


def require_project_permission_from_story_save_payload(
    permission: Permission,
) -> Callable[..., ImportStoriesRequest]:
    def dependency(
        payload: ImportStoriesRequest,
        current_user: AuthenticatedUser = Depends(get_current_user),
        authorizer: Authorizer = Depends(get_request_authorizer),
        db: Session = Depends(get_db),
    ) -> ImportStoriesRequest:
        _authorize_for_project(
            current_user=current_user,
            project_id=payload.project_id,
            permission=permission,
            authorizer=authorizer,
            db=db,
        )
        return payload

    return dependency


def require_project_permission_from_story_status_lookup_payload(
    permission: Permission,
) -> Callable[..., StoryStatusLookupRequest]:
    def dependency(
        payload: StoryStatusLookupRequest,
        current_user: AuthenticatedUser = Depends(get_current_user),
        authorizer: Authorizer = Depends(get_request_authorizer),
        db: Session = Depends(get_db),
    ) -> StoryStatusLookupRequest:
        _authorize_for_project(
            current_user=current_user,
            project_id=payload.project_id,
            permission=permission,
            authorizer=authorizer,
            db=db,
        )
        return payload

    return dependency


def require_project_permission_for_test_case_status(
    permission: Permission,
) -> Callable[..., UpdateTestCasesStatusByIdsRequest]:
    def dependency(
        payload: UpdateTestCasesStatusByIdsRequest,
        current_user: AuthenticatedUser = Depends(get_current_user),
        authorizer: Authorizer = Depends(get_request_authorizer),
        db: Session = Depends(get_db),
    ) -> UpdateTestCasesStatusByIdsRequest:
        _authorize_for_project(
            current_user=current_user,
            project_id=payload.project_id,
            permission=permission,
            authorizer=authorizer,
            db=db,
        )

        actual_project_ids = get_project_ids_for_test_case_ids(db, payload.ids)
        foreign_ids = actual_project_ids - {payload.project_id}
        if foreign_ids:
            logger.warning(
                "test_case_project_mismatch",
                extra={
                    "user_id": str(current_user.id),
                    "declared_project_id": str(payload.project_id),
                    "foreign_project_ids": [str(p) for p in foreign_ids],
                },
            )
            raise AppException(
                code="FORBIDDEN",
                message="One or more test cases do not belong to the given project.",
                status_code=403,
            )

        return payload

    return dependency


def require_project_permission_from_story_approval_submit_payload(
    permission: Permission,
) -> Callable[..., StoryApprovalSubmitRequest]:
    def dependency(
        payload: StoryApprovalSubmitRequest,
        current_user: AuthenticatedUser = Depends(get_current_user),
        authorizer: Authorizer = Depends(get_request_authorizer),
        db: Session = Depends(get_db),
    ) -> StoryApprovalSubmitRequest:
        _authorize_for_project(
            current_user=current_user,
            project_id=payload.project_id,
            permission=permission,
            authorizer=authorizer,
            db=db,
        )
        return payload

    return dependency


def _authorize_for_entity(
    *,
    current_user: AuthenticatedUser,
    entity_id: uuid.UUID,
    permission: Permission,
    authorizer: Authorizer,
    db: Session,
) -> None:
    if not authorizer.has_permission(current_user, permission):
        logger.warning(
            "authz_denied",
            extra={
                "user_id": str(current_user.id),
                "user_role": current_user.role,
                "permission": permission.value,
            },
        )
        raise AuthorizationError()

    visible_client_ids = get_visible_client_ids(db, current_user.id)
    visible_programme_ids = get_visible_programme_ids(db, current_user.id)
    visible_project_ids = get_visible_project_ids(db, current_user.id)

    if visible_client_ids is None or visible_programme_ids is None or visible_project_ids is None:
        return

    visible = visible_client_ids | visible_programme_ids | visible_project_ids
    if entity_id not in visible:
        logger.warning(
            "entity_access_denied",
            extra={
                "user_id": str(current_user.id),
                "entity_id": str(entity_id),
                "permission": permission.value,
            },
        )
        raise AppException(
            code="FORBIDDEN",
            message="You do not have access to this entity.",
            status_code=403,
        )


def require_entity_permission_from_duplicate_check_payload(
    permission: Permission,
) -> Callable[..., DuplicateCheckRequest]:
    def dependency(
        payload: DuplicateCheckRequest,
        current_user: AuthenticatedUser = Depends(get_current_user),
        authorizer: Authorizer = Depends(get_request_authorizer),
        db: Session = Depends(get_db),
    ) -> DuplicateCheckRequest:
        try:
            entity_id = uuid.UUID(payload.entity_id)
        except ValueError:
            raise AppException(
                code="INVALID_ENTITY_ID",
                message="entity_id must be a valid UUID.",
                status_code=422,
            )
        _authorize_for_entity(
            current_user=current_user,
            entity_id=entity_id,
            permission=permission,
            authorizer=authorizer,
            db=db,
        )
        return payload

    return dependency


def require_entity_permission_from_confirm_upload_payload(
    permission: Permission,
) -> Callable[..., ConfirmUploadRequest]:
    def dependency(
        payload: ConfirmUploadRequest,
        current_user: AuthenticatedUser = Depends(get_current_user),
        authorizer: Authorizer = Depends(get_request_authorizer),
        db: Session = Depends(get_db),
    ) -> ConfirmUploadRequest:
        try:
            entity_id = uuid.UUID(payload.entity_id)
        except ValueError:
            raise AppException(
                code="INVALID_ENTITY_ID",
                message="entity_id must be a valid UUID.",
                status_code=422,
            )
        _authorize_for_entity(
            current_user=current_user,
            entity_id=entity_id,
            permission=permission,
            authorizer=authorizer,
            db=db,
        )
        return payload

    return dependency


def require_entity_permission(permission: Permission) -> Callable[..., uuid.UUID]:
    def dependency(
        entity_id: uuid.UUID,
        current_user: AuthenticatedUser = Depends(get_current_user),
        authorizer: Authorizer = Depends(get_request_authorizer),
        db: Session = Depends(get_db),
    ) -> uuid.UUID:
        _authorize_for_entity(
            current_user=current_user,
            entity_id=entity_id,
            permission=permission,
            authorizer=authorizer,
            db=db,
        )
        return entity_id

    return dependency


def require_project_permission_from_story_edit_log_payload(
    permission: Permission,
) -> Callable[..., StoryEditLogRequest]:
    def dependency(
        payload: StoryEditLogRequest,
        current_user: AuthenticatedUser = Depends(get_current_user),
        authorizer: Authorizer = Depends(get_request_authorizer),
        db: Session = Depends(get_db),
    ) -> StoryEditLogRequest:
        _authorize_for_project(
            current_user=current_user,
            project_id=payload.project_id,
            permission=permission,
            authorizer=authorizer,
            db=db,
        )
        story_ids = [record.storyId for record in payload.edit_log]
        actual_project_ids = get_project_ids_for_story_ids(db, story_ids)
        foreign_ids = actual_project_ids - {payload.project_id}
        if foreign_ids:
            logger.warning(
                "story_edit_log_project_mismatch",
                extra={
                    "user_id": str(current_user.id),
                    "declared_project_id": str(payload.project_id),
                    "foreign_project_ids": [str(p) for p in foreign_ids],
                },
            )
            raise AppException(
                code="FORBIDDEN",
                message="One or more stories do not belong to the given project.",
                status_code=403,
            )
        return payload

    return dependency
