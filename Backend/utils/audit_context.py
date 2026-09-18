"""Client-name resolution helpers shared by audit-logged programme/project routes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.database.programmes_db import get_client_by_id, get_programme_by_id
from app.database.projects_db import get_project_by_id


def client_name_for_client_id(db: Session, client_id: UUID | None) -> str | None:
    if client_id is None:
        return None
    client = get_client_by_id(db, client_id)
    return client.name if client else None


def client_name_for_programme_id(db: Session, programme_id: UUID | None) -> str | None:
    if programme_id is None:
        return None
    programme = get_programme_by_id(db, programme_id)
    if programme is None:
        return None
    return client_name_for_client_id(db, programme.client_id)


def client_name_for_project_id(db: Session, project_id: UUID | None) -> str | None:
    if project_id is None:
        return None
    project = get_project_by_id(db, project_id)
    if project is None:
        return None
    return client_name_for_programme_id(db, project.programme_id)
