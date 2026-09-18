"""Database access helpers for project records."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.components.authorizer import Permission
from app.core.exceptions import AppException, DatabaseOperationException
from app.core.logging import logger
from app.models.clients_models import Client
from app.models.programmes_models import Programme
from app.models.project_models import Project
from app.models.project_users_models import ProjectUser
from app.models.rbac_models import PermissionModel, RoleModel, role_permissions
from app.models.users_models import User
from app.schemas.projects import ProjectListRow

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "projects"


@lru_cache(maxsize=1)
def _read_sql_file(filename: str) -> str:
    """Return the contents of a stored SQL file."""

    try:
        return (SQL_DIR / filename).read_text(encoding="utf-8")
    except Exception as exc:
        logger.exception("project_sql_read_failed")
        raise DatabaseOperationException(f"Unable to read SQL file: {filename}") from exc


def _row_to_project(row: dict[str, Any]) -> Project:
    """Convert a row mapping into a project model instance."""

    project = Project(
        id=row["id"],
        programme_id=row["programme_id"],
        name=row["name"],
        description=row.get("description"),
        status=row["status"],
        lead_id=row.get("lead_id"),
        start_date=row.get("start_date"),
        created_at=row["created_at"],
        last_modified=row["last_modified"],
    )

    if row.get("lead_name"):
        project.lead_name = row["lead_name"]

    return project


def create_project_entry(
    db: Session,
    *,
    programme_id: UUID,
    name: str,
    description: str | None = None,
    lead_id: UUID | None = None,
    status: str = "active",
    start_date=None,
) -> Project:
    """Insert a new project row and persist it."""

    try:
        query = text(_read_sql_file("project_insert.sql"))
        row = (
            db.execute(
                query,
                {
                    "programme_id": programme_id,
                    "name": name.strip(),
                    "description": description,
                    "status": status,
                    "lead_id": lead_id,
                    "start_date": start_date,
                },
            )
            .mappings()
            .one()
        )
        db.commit()
        return _row_to_project(dict(row))
    except IntegrityError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("project_create_failed")
        raise DatabaseOperationException(f"Unable to create project: {name.strip()}") from exc


def check_project_name_exists(
    db: Session,
    *,
    programme_id: UUID,
    name: str,
) -> bool:
    """Return True when the same project name already exists for the programme."""

    try:
        query = text(_read_sql_file("check_project_name_exists.sql"))
        exists = db.execute(
            query,
            {"programme_id": programme_id, "name": name.strip()},
        ).scalar()
        return bool(exists)
    except Exception as exc:
        logger.exception("project_name_exists_check_failed")
        raise DatabaseOperationException(f"Unable to check project name: {name.strip()}") from exc


def list_projects_by_programme_id(db: Session, programme_id: UUID) -> list[Project]:
    """Return active projects for a programme."""

    try:
        query = text(_read_sql_file("project_list_by_programme_id.sql"))
        rows = db.execute(query, {"programme_id": programme_id}).mappings().all()
        return [_row_to_project(dict(row)) for row in rows]
    except Exception as exc:
        logger.exception("project_list_by_programme_failed")
        raise DatabaseOperationException(
            f"Unable to fetch projects for programme: {programme_id}"
        ) from exc


def count_visible_projects_by_programme(db: Session, project_ids: set[UUID]) -> dict[UUID, int]:
    """Return {programme_id: count} for how many of the given project_ids
    fall under each programme, in a single query."""
    if not project_ids:
        return {}

    try:
        stmt = (
            select(Project.programme_id, func.count(Project.id))
            .where(Project.id.in_(project_ids), Project.status != "archived")
            .group_by(Project.programme_id)
        )
        return dict(db.execute(stmt).all())
    except Exception as exc:
        logger.exception("count_visible_projects_by_programme_failed")
        raise DatabaseOperationException("Unable to count visible projects by programme") from exc


def list_all_projects(db: Session) -> list[ProjectListRow]:
    """Return active projects with their associated programme and client."""

    try:
        stmt = (
            select(
                Project,
                Programme.name.label("programme_name"),
                Client.id.label("client_id"),
                Client.name.label("client_name"),
                User.name.label("lead_name"),
            )
            .join(Programme, Programme.id == Project.programme_id)
            .join(Client, Client.id == Programme.client_id)
            .outerjoin(User, User.id == Project.lead_id)
            .where(Project.status == "active")
            .order_by(Project.name.asc())
        )
        rows = db.execute(stmt).all()
        return [
            ProjectListRow(
                id=row.Project.id,
                programme_id=row.Project.programme_id,
                name=row.Project.name,
                description=row.Project.description,
                status=row.Project.status,
                last_modified=row.Project.last_modified,
                programme_name=row.programme_name,
                client_id=row.client_id,
                client_name=row.client_name,
                lead_id=row.Project.lead_id,
                lead_name=row.lead_name,
            )
            for row in rows
        ]
    except Exception as exc:
        logger.exception("project_list_all_failed")
        raise DatabaseOperationException("Unable to fetch all projects") from exc


def get_project_by_id(db: Session, project_id: UUID) -> Project | None:
    """Return a project by id, excluding soft-deleted."""

    try:
        project = db.get(Project, project_id)
        if project is None or project.status == "archived":
            return None
        return project
    except Exception as exc:
        logger.exception("project_lookup_failed")
        raise DatabaseOperationException(f"Unable to fetch project: {project_id}") from exc


def update_project_entry(
    db: Session,
    project_id: UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    lead_id: UUID | None = None,
) -> Project:
    """Update allowed fields on a project and commit."""

    try:
        project = get_project_by_id(db, project_id)
        if project is None:
            raise AppException(
                code="PROJECT_NOT_FOUND",
                message=f"Project {project_id} not found",
                status_code=404,
            )

        if name is not None:
            project.name = name.strip()
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status
        if lead_id is not None:
            project.lead_id = lead_id

        db.add(project)
        db.commit()
        db.refresh(project)
        return project
    except AppException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("project_update_failed")
        raise DatabaseOperationException(f"Unable to update project: {project_id}") from exc


def update_project_jira_config(
    db: Session,
    project_id: UUID,
    *,
    jira_url: str | None = None,
    jira_project_key: str | None = None,
) -> Project:
    """Update the Jira URL / project key stored against a project."""

    try:
        project = get_project_by_id(db, project_id)
        if project is None:
            raise AppException(
                code="PROJECT_NOT_FOUND",
                message=f"Project {project_id} not found",
                status_code=404,
            )

        if jira_url is not None:
            project.jira_url = jira_url
        if jira_project_key is not None:
            project.jira_project_key = jira_project_key

        db.add(project)
        db.commit()
        db.refresh(project)
        return project
    except AppException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("project_jira_config_update_failed")
        raise DatabaseOperationException(
            f"Unable to update Jira config for project: {project_id}"
        ) from exc


def get_configured_jira_urls_for_user(db: Session, user_id: UUID) -> list[str]:
    """Return the distinct Jira URLs of projects the given user is associated
    with (as lead or team member), used to know which Jira instances to verify
    the user's Profile-level credentials against.

    A user working across several clients can be on more than one Atlassian
    tenant, so the caller tries each rather than assuming one.
    """

    try:
        stmt = (
            select(Project.jira_url)
            .outerjoin(ProjectUser, ProjectUser.project_id == Project.id)
            .where(
                Project.jira_url.isnot(None),
                Project.jira_url != "",
                or_(Project.lead_id == user_id, ProjectUser.user_id == user_id),
            )
            .distinct()
            .order_by(Project.jira_url)
        )
        return list(db.execute(stmt).scalars().all())
    except Exception as exc:
        logger.exception("project_jira_url_lookup_failed", extra={"user_id": str(user_id)})
        raise DatabaseOperationException("Unable to look up a configured Jira URL") from exc


def soft_delete_project_entry(db: Session, project_id: UUID) -> Project:
    """Soft delete a project by setting status to archived."""

    try:
        project = db.get(Project, project_id)
        if project is None or project.status == "archived":
            raise AppException(
                code="PROJECT_NOT_FOUND",
                message=f"Project {project_id} not found",
                status_code=404,
            )

        project.status = "archived"
        db.add(project)
        db.commit()
        db.refresh(project)
        return project
    except AppException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("project_soft_delete_failed")
        raise DatabaseOperationException(f"Unable to soft delete project: {project_id}") from exc


def get_project_approvers(db: Session, project_id: UUID) -> list[tuple[str, str, str]]:
    """Return the (role_label, name, email) of a project's approvers.

    The Project Manager is inherited from the owning client (`clients.manager_id`),
    the same path `list_programmes` uses for `manager_name`; the Project Lead is
    `projects.lead_id` and is absent when no lead is assigned.

    Both joins require an active user whose role grants `story:approve`. Assignment
    alone is not enough: nothing validates the role of a lead or manager at
    assignment time, so an assignee without that permission would be offered as a
    reviewer, emailed, and shown the request, only to be refused 403 by the decision
    endpoint on a request formally assigned to them.
    """

    manager = aliased(User)
    lead = aliased(User)

    roles_that_can_approve = (
        select(RoleModel.name)
        .join(role_permissions, role_permissions.c.role_id == RoleModel.id)
        .join(PermissionModel, PermissionModel.id == role_permissions.c.permission_id)
        .where(PermissionModel.name == Permission.STORY_APPROVE.value)
    )

    try:
        row = db.execute(
            select(
                manager.name.label("manager_name"),
                manager.email.label("manager_email"),
                lead.name.label("lead_name"),
                lead.email.label("lead_email"),
            )
            .select_from(Project)
            .join(Programme, Programme.id == Project.programme_id)
            .join(Client, Client.id == Programme.client_id)
            .outerjoin(
                manager,
                (manager.id == Client.manager_id)
                & manager.is_active.is_(True)
                & manager.role.in_(roles_that_can_approve),
            )
            .outerjoin(
                lead,
                (lead.id == Project.lead_id)
                & lead.is_active.is_(True)
                & lead.role.in_(roles_that_can_approve),
            )
            .where(Project.id == project_id, Project.status != "archived")
        ).first()
    except Exception as exc:
        logger.exception("project_approver_lookup_failed", extra={"project_id": str(project_id)})
        raise DatabaseOperationException(
            f"Unable to fetch approvers for project: {project_id}"
        ) from exc

    if row is None:
        return []

    approvers: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for label, name, email in (
        ("Project Manager", row.manager_name, row.manager_email),
        ("Project Lead", row.lead_name, row.lead_email),
    ):
        if email and email.lower() not in seen:
            seen.add(email.lower())
            approvers.append((label, name, email))
    return approvers
