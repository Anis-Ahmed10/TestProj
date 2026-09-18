"""Assignment-based data visibility helpers.

Centralizes the rules for which Client / Programme / Project rows a given
user is allowed to see. A row is visible through any of three assignments,
and they are additive — a user gets the union of whichever apply to them:

- they manage the owning client (Client.manager_id)
- they lead the project (Project.lead_id)
- they are on the project team (project_users)

Role gates what a user may *do* (see app.components.authorizer), never which
of these rules is consulted. Keying visibility off the role instead would
mean adding a Lead or Manager to a project team granted them nothing,
because only the team-membership rule would have been skipped for them.

Each function returns a `set[UUID]` of visible IDs, or `None` to mean
"no restriction" — callers should treat `None` as "show everything" and
skip filtering. A user whose role does not map to a known Role fails
closed with an empty set.

The three levels are independent, not derived from one another: being able
to see a Client (because of one project somewhere under it) does NOT make
every Programme/Project under that Client visible — only the ones the user
is actually assigned to.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.components.authorizer.models import Role, parse_role
from app.core.exceptions import DatabaseOperationException
from app.database.users_db import get_user_by_id
from app.models.clients_models import Client
from app.models.programmes_models import Programme
from app.models.project_models import Project
from app.models.project_users_models import ProjectUser

logger = logging.getLogger(__name__)


def _client_ids_managed(db: Session, user_id: UUID) -> set[UUID]:
    """Clients this user manages."""

    stmt = select(Client.id).where(Client.manager_id == user_id)
    return set(db.execute(stmt).scalars().all())


def _client_ids_led(db: Session, user_id: UUID) -> set[UUID]:
    """Clients with at least one project, under any of its programmes,
    where this user is the assigned lead."""

    stmt = (
        select(Programme.client_id)
        .join(Project, Project.programme_id == Programme.id)
        .where(Project.lead_id == user_id)
        .distinct()
    )
    return set(db.execute(stmt).scalars().all())


def _client_ids_via_membership(db: Session, user_id: UUID) -> set[UUID]:
    """Clients with at least one project, under any of its programmes,
    where this user is a team member (project_users)."""

    stmt = (
        select(Programme.client_id)
        .join(Project, Project.programme_id == Programme.id)
        .join(ProjectUser, ProjectUser.project_id == Project.id)
        .where(ProjectUser.user_id == user_id)
        .distinct()
    )
    return set(db.execute(stmt).scalars().all())


def get_visible_client_ids(db: Session, user_id: UUID) -> set[UUID] | None:
    """Return the set of Client IDs visible to this user."""

    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            # Unknown user -> fail closed, show nothing.
            logger.warning("get_visible_client_ids_unknown_user", extra={"user_id": str(user_id)})
            return set()

        if parse_role(user.role) is None:
            logger.warning("get_visible_client_ids_unmapped_role", extra={"user_id": str(user_id)})
            return set()

        return (
            _client_ids_managed(db, user_id)
            | _client_ids_led(db, user_id)
            | _client_ids_via_membership(db, user_id)
        )
    except DatabaseOperationException:
        raise
    except Exception as exc:
        logger.exception("get_visible_client_ids_failed", extra={"user_id": str(user_id)})
        raise DatabaseOperationException("Unable to resolve visible clients") from exc


# ---------------------------------------------------------------------------
# Programme-level visibility
# ---------------------------------------------------------------------------


def _programme_ids_managed(db: Session, user_id: UUID) -> set[UUID]:
    """All programmes under clients this user manages."""

    stmt = (
        select(Programme.id)
        .join(Client, Client.id == Programme.client_id)
        .where(Client.manager_id == user_id)
    )
    return set(db.execute(stmt).scalars().all())


def _programme_ids_led(db: Session, user_id: UUID) -> set[UUID]:
    """Programmes containing at least one project this user leads."""

    stmt = select(Project.programme_id).where(Project.lead_id == user_id).distinct()
    return set(db.execute(stmt).scalars().all())


def _programme_ids_via_membership(db: Session, user_id: UUID) -> set[UUID]:
    """Programmes containing at least one project this user is a team member of."""

    stmt = (
        select(Project.programme_id)
        .join(ProjectUser, ProjectUser.project_id == Project.id)
        .where(ProjectUser.user_id == user_id)
        .distinct()
    )
    return set(db.execute(stmt).scalars().all())


def get_visible_programme_ids(db: Session, user_id: UUID) -> set[UUID] | None:
    """Return the set of Programme IDs visible to this user."""

    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            logger.warning(
                "get_visible_programme_ids_unknown_user", extra={"user_id": str(user_id)}
            )
            return set()

        if parse_role(user.role) is None:
            logger.warning(
                "get_visible_programme_ids_unmapped_role", extra={"user_id": str(user_id)}
            )
            return set()

        return (
            _programme_ids_managed(db, user_id)
            | _programme_ids_led(db, user_id)
            | _programme_ids_via_membership(db, user_id)
        )
    except DatabaseOperationException:
        raise
    except Exception as exc:
        logger.exception("get_visible_programme_ids_failed", extra={"user_id": str(user_id)})
        raise DatabaseOperationException("Unable to resolve visible programmes") from exc


# ---------------------------------------------------------------------------
# Project-level visibility
# ---------------------------------------------------------------------------


def _project_ids_managed(db: Session, user_id: UUID) -> set[UUID]:
    """All projects under clients this user manages."""

    stmt = (
        select(Project.id)
        .join(Programme, Programme.id == Project.programme_id)
        .join(Client, Client.id == Programme.client_id)
        .where(Client.manager_id == user_id)
    )
    return set(db.execute(stmt).scalars().all())


def _project_ids_led(db: Session, user_id: UUID) -> set[UUID]:
    """Projects this user leads."""

    stmt = select(Project.id).where(Project.lead_id == user_id)
    return set(db.execute(stmt).scalars().all())


def _project_ids_via_membership(db: Session, user_id: UUID) -> set[UUID]:
    """Projects this user is a team member of."""

    stmt = (
        select(Project.id)
        .join(ProjectUser, ProjectUser.project_id == Project.id)
        .where(ProjectUser.user_id == user_id)
    )
    return set(db.execute(stmt).scalars().all())


def get_visible_project_ids(db: Session, user_id: UUID) -> set[UUID] | None:
    """Return the set of Project IDs visible to this user."""

    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            logger.warning("get_visible_project_ids_unknown_user", extra={"user_id": str(user_id)})
            return set()

        if parse_role(user.role) is None:
            logger.warning(
                "get_visible_project_ids_unmapped_role", extra={"user_id": str(user_id)}
            )
            return set()

        return (
            _project_ids_managed(db, user_id)
            | _project_ids_led(db, user_id)
            | _project_ids_via_membership(db, user_id)
        )
    except DatabaseOperationException:
        raise
    except Exception as exc:
        logger.exception("get_visible_project_ids_failed", extra={"user_id": str(user_id)})
        raise DatabaseOperationException("Unable to resolve visible projects") from exc


# ---------------------------------------------------------------------------
# Per-client counts (Programmes / Projects / Active Members badges)
# ---------------------------------------------------------------------------


def get_visible_counts_by_client(db: Session, user_id: UUID) -> dict[UUID, dict[str, int]] | None:
    """Return {client_id: {"programmes_count", "projects_count",
    "active_members_count"}} scoped to what this user can see, or None if
    the caller's counts should stay as the unfiltered client-wide totals.
    """
    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            return {}

        role = parse_role(user.role)

        if role == Role.TEST_MANAGER:
            return None

        if role not in (Role.TEST_LEAD, Role.TEST_ENGINEER):
            return {}

        visible_programme_ids = get_visible_programme_ids(db, user_id)
        visible_project_ids = get_visible_project_ids(db, user_id)

        # Defensive: Lead/Engineer are always scoped by the functions above,
        # but if either ever returns None (unrestricted), don't attempt to
        # override — fall back to unfiltered totals rather than guessing.
        if visible_programme_ids is None or visible_project_ids is None:
            return None

        programmes: dict[UUID, set[UUID]] = {}
        projects: dict[UUID, set[UUID]] = {}
        members: dict[UUID, set[UUID]] = {}

        if visible_programme_ids:
            stmt = select(Programme.client_id, Programme.id).where(
                Programme.id.in_(visible_programme_ids)
            )
            for client_id, programme_id in db.execute(stmt).all():
                programmes.setdefault(client_id, set()).add(programme_id)

        if visible_project_ids:
            stmt = (
                select(Programme.client_id, Project.id)
                .join(Project, Project.programme_id == Programme.id)
                .where(Project.id.in_(visible_project_ids))
            )
            for client_id, project_id in db.execute(stmt).all():
                projects.setdefault(client_id, set()).add(project_id)

            stmt = (
                select(Programme.client_id, ProjectUser.user_id)
                .join(Project, Project.programme_id == Programme.id)
                .join(ProjectUser, ProjectUser.project_id == Project.id)
                .where(Project.id.in_(visible_project_ids))
            )
            for client_id, member_id in db.execute(stmt).all():
                members.setdefault(client_id, set()).add(member_id)

        client_ids = set(programmes) | set(projects) | set(members)
        return {
            client_id: {
                "programmes_count": len(programmes.get(client_id, set())),
                "projects_count": len(projects.get(client_id, set())),
                "active_members_count": len(members.get(client_id, set())),
            }
            for client_id in client_ids
        }
    except DatabaseOperationException:
        raise
    except Exception as exc:
        logger.exception("get_visible_counts_by_client_failed", extra={"user_id": str(user_id)})
        raise DatabaseOperationException("Unable to resolve visible client counts") from exc
