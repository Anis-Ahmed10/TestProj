"""Database access helpers for programme records."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from http import HTTPStatus
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, DatabaseOperationException
from app.core.logging import logger
from app.models.clients_models import Client
from app.models.programmes_models import Programme
from app.models.project_models import Project
from app.models.users_models import User

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "programmes"


@lru_cache(maxsize=1)
def _read_sql_file(filename: str) -> str:
    """Return SQL text kept for parity with the client module."""

    try:
        return (SQL_DIR / filename).read_text(encoding="utf-8")
    except Exception as exc:
        logger.exception("programme_sql_read_failed")
        raise DatabaseOperationException(f"Unable to read SQL file: {filename}") from exc


def _row_to_programme(row: dict[str, Any]) -> Programme:
    """Convert a row mapping into a programme model instance."""

    return Programme(
        id=row["id"],
        client_id=row["client_id"],
        name=row["name"],
        description=row.get("description"),
        status=row.get("status", "active"),
        created_at=row["created_at"],
        last_modified=row["last_modified"],
    )


def get_programme_by_id(db: Session, programme_id: UUID) -> Programme | None:
    """Return a programme by id."""

    try:
        query = text(_read_sql_file("get_programme_by_id.sql"))
        row = db.execute(query, {"programme_id": programme_id}).mappings().first()
        return _row_to_programme(dict(row)) if row is not None else None
    except Exception as exc:
        logger.exception("programme_lookup_failed")
        raise DatabaseOperationException(f"Unable to fetch programme: {programme_id}") from exc


def get_programme_with_details_db(
    db: Session, programme_id: UUID
) -> tuple[Programme, int, str | None] | None:
    """Return a single programme joined with active project count and
    inherited Client manager name."""

    try:
        subq = (
            sa_select(
                Project.programme_id.label("programme_id"),
                func.count().label("project_count"),
            )
            .where(Project.status != "archived")
            .group_by(Project.programme_id)
            .subquery()
        )

        stmt = (
            sa_select(
                Programme,
                func.coalesce(subq.c.project_count, 0).label("project_count"),
                User.name.label("manager_name"),
            )
            .outerjoin(subq, subq.c.programme_id == Programme.id)
            .outerjoin(Client, Client.id == Programme.client_id)
            .outerjoin(User, User.id == Client.manager_id)
            .where(Programme.id == programme_id)
            .where(Programme.status != "archived")
        )

        row = db.execute(stmt).first()
        if row is None:
            return None
        return (row[0], int(row[1]), row[2])
    except Exception as exc:
        logger.exception("programme_details_lookup_failed")
        raise DatabaseOperationException(
            f"Unable to fetch programme details: {programme_id}"
        ) from exc


def get_client_by_id(db: Session, client_id: UUID) -> Client | None:
    client = db.get(Client, client_id)
    if client is None or client.status == "archived":
        return None
    return client


def get_programme(db: Session, programme_id: UUID) -> Programme:
    programme = get_programme_by_id(db, programme_id)
    if programme is None:
        raise AppException(
            code="PROGRAMME_NOT_FOUND",
            message=f"Programme {programme_id} not found",
            status_code=HTTPStatus.NOT_FOUND,
        )
    return programme


def create_programme_entry(
    db: Session,
    *,
    client_id: UUID,
    name: str,
    description: str | None = None,
    status: str = "active",
) -> Programme:
    """Insert a new programme row and persist it."""

    try:
        query = text(_read_sql_file("programme_insert.sql"))
        row = (
            db.execute(
                query,
                {
                    "client_id": client_id,
                    "name": name.strip(),
                    "description": description,
                    "status": status,
                },
            )
            .mappings()
            .one()
        )
        db.commit()
        return _row_to_programme(dict(row))
    except IntegrityError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("programme_create_failed")
        raise DatabaseOperationException(f"Unable to create programme: {name.strip()}") from exc


def check_programme_name_exists(
    db: Session,
    *,
    client_id: UUID,
    name: str,
) -> bool:
    """Return True when the same programme name already exists for the client."""

    try:
        query = text(_read_sql_file("check_programme_name_exists.sql"))
        exists = db.execute(
            query,
            {"client_id": client_id, "name": name.strip()},
        ).scalar()
        return bool(exists)
    except Exception as exc:
        logger.exception("programme_name_exists_check_failed")
        raise DatabaseOperationException(
            f"Unable to check programme name: {name.strip()}"
        ) from exc


def count_active_projects_by_programme(db: Session, programme_id: UUID) -> int:
    """Return active project count for a programme."""

    try:
        query = text(_read_sql_file("programme_count_active_projects.sql"))
        count = db.execute(query, {"programme_id": programme_id}).scalar_one()
        return int(count or 0)
    except Exception as exc:
        logger.exception("programme_active_project_count_failed")
        raise DatabaseOperationException(
            f"Unable to check active projects for programme: {programme_id}"
        ) from exc


def delete_programme_entry(db: Session, programme_id: UUID) -> Programme:
    """Soft delete a programme and return the archived row."""

    try:
        programme = db.get(Programme, programme_id)
        if programme is None or programme.status == "archived":
            raise AppException(
                code="PROGRAMME_NOT_FOUND",
                message=f"Programme {programme_id} not found",
                status_code=404,
            )

        programme.status = "archived"

        db.add(programme)
        db.commit()
        db.refresh(programme)
        return programme
    except AppException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("programme_delete_failed")
        raise DatabaseOperationException(f"Unable to delete programme: {programme_id}") from exc


def update_programme_entry(
    db: Session,
    programme_id: UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
) -> Programme:
    """Update allowed fields on a programme and commit."""

    try:
        programme = db.get(Programme, programme_id)
        if programme is None or programme.status == "archived":
            raise AppException(
                code="PROGRAMME_NOT_FOUND",
                message=f"Programme {programme_id} not found",
                status_code=404,
            )

        if name is not None:
            programme.name = name.strip()
        if description is not None:
            programme.description = description
        if status is not None:
            programme.status = status

        programme.last_modified = datetime.now(timezone.utc)

        db.add(programme)
        db.commit()
        db.refresh(programme)
        return programme
    except AppException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("programme_update_failed")
        raise DatabaseOperationException(f"Unable to update programme: {programme_id}") from exc


def list_all_programmes(db: Session, client_id: UUID | None = None):
    """Return all non-archived programmes with active project counts."""

    try:
        subq = (
            sa_select(
                Project.programme_id.label("programme_id"),
                func.count().label("project_count"),
            )
            .where(Project.status != "archived")
            .group_by(Project.programme_id)
            .subquery()
        )

        stmt = (
            sa_select(
                Programme,
                func.coalesce(subq.c.project_count, 0).label("project_count"),
                User.name.label("manager_name"),
            )
            .outerjoin(subq, subq.c.programme_id == Programme.id)
            .outerjoin(Client, Client.id == Programme.client_id)
            .outerjoin(User, User.id == Client.manager_id)
            .where(Programme.status != "archived")
        )
        if client_id is not None:
            stmt = stmt.where(Programme.client_id == client_id)
        stmt = stmt.order_by(Programme.name.asc())
        return db.execute(stmt).all()
    except Exception as exc:
        logger.exception("programme_list_all_failed")
        raise DatabaseOperationException("Unable to list all programmes") from exc
