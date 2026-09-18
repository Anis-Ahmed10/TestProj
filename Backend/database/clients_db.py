"""Database access helpers for client records."""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import select as sa_select
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, DatabaseOperationException, InvalidInputError
from app.core.logging import logger
from app.models.clients_models import Client
from app.models.programmes_models import Programme
from app.models.project_models import Project

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "clients"


@lru_cache(maxsize=1)
def _read_sql_file(filename: str) -> str:
    """Return the contents of a stored SQL file."""

    try:
        return (SQL_DIR / filename).read_text(encoding="utf-8")
    except Exception as exc:
        logger.exception("client_sql_read_failed")
        raise DatabaseOperationException(f"Unable to read SQL file: {filename}") from exc


def _row_to_client(row: dict[str, Any]) -> Client:
    """Convert a SQL row into a client object with count metadata."""

    try:
        client = Client(
            id=row["id"],
            name=row["name"],
            industry=row["industry"],
            location=row["location"],
            contact=row["contact"],
            status=row["status"],
            manager_id=row.get("manager_id"),
            created_at=row["created_at"],
            last_modified=row["last_modified"],
        )
        client.manager_name = row.get("manager_name")
        client.programmes_count = int(row.get("programmes_count", 0) or 0)
        client.projects_count = int(row.get("projects_count", 0) or 0)
        client.active_members_count = int(row.get("active_members_count", 0) or 0)
        return client
    except Exception as exc:
        logger.exception("client_row_mapping_failed")
        raise DatabaseOperationException(f"Unable to map client row: {exc}") from exc


def get_client_by_name(db: Session, name: str) -> Client | None:
    """Return an existing client by name using case-insensitive matching."""
    try:
        query = select(Client).from_statement(text(_read_sql_file("get_client_by_name.sql")))
        result = db.execute(query, {"client_name": name.strip()})
        return result.scalars().first()
    except Exception as exc:
        logger.exception("client_lookup_failed")
        raise DatabaseOperationException(
            f"Unable to fetch client by name: {name.strip()}"
        ) from exc


def create_client_entry(
    db: Session,
    *,
    name: str,
    industry: str,
    contact: str,
    location: str | None = None,
    status: str = "active",
    manager_id: str | None = None,
) -> Client:
    """Insert a new client row and persist it."""

    try:
        params = {
            "name": name.strip(),
            "industry": industry.strip(),
            "location": location.strip() if location else None,
            "contact": contact.strip(),
            "status": status,
            "manager_id": str(manager_id) if manager_id else None,
        }
        query = text(_read_sql_file("client_insert.sql"))
        row = db.execute(query, params).mappings().one()
        db.commit()
        client = _row_to_client(dict(row))
        client.programmes_count = 0
        client.projects_count = 0
        client.active_members_count = 0
        return client
    except IntegrityError:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("client_create_entry_failed")
        raise DatabaseOperationException(f"Unable to create client entry: {name.strip()}") from exc


def list_client_entries(db: Session) -> list[Client]:
    """Return all clients ordered by most recent update."""

    try:
        query = text(_read_sql_file("client_list_with_counts.sql"))
        rows = db.execute(query).mappings().all()
        return [_row_to_client(dict(row)) for row in rows]
    except Exception as exc:
        logger.exception("client_list_entries_failed")
        raise DatabaseOperationException("Unable to list client entries") from exc


def get_programs_by_client_id(db: Session, client_id) -> list[dict]:
    """Return programmes associated with the client."""
    try:
        query = text(_read_sql_file("get_programs_by_client_id.sql"))
        result = db.execute(query, {"client_id": client_id})

        return [
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
            }
            for row in result.mappings().all()
        ]
    except Exception as exc:
        logger.exception("get_programs_by_client_id_failed")
        raise DatabaseOperationException(
            f"Unable to fetch programs for client: {client_id}"
        ) from exc


def update_client_in_db(db: Session, client_name: str, update_data: Mapping) -> Client:
    """Apply updates to a client and commit."""
    try:
        client = get_client_by_name(db, client_name)
        if client is None:
            raise AppException(
                code="NOT_FOUND",
                message=f"Client {client_name} not found",
                status_code=404,
            )

        # Only update known fields; ignore any unexpected keys.
        allowed_fields = {"name", "industry", "location", "contact", "status", "manager_id"}
        for key, value in update_data.items():
            if key in allowed_fields:
                setattr(client, key, value)

        db.add(client)
        db.commit()
        db.refresh(client)
        return client
    except AppException:
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.warning("update_client_integrity_error")
        raise InvalidInputError("Client name already exists") from exc
    except Exception as exc:
        db.rollback()
        logger.exception("update_client_in_db_failed")
        raise DatabaseOperationException(f"Unable to update client: {client_name}") from exc


def soft_delete_client(db: Session, client_name: str) -> Client:
    """Archive a client (soft delete)."""
    try:
        client = get_client_by_name(db, client_name)
        if client is None:
            raise AppException(
                code="NOT_FOUND",
                message=f"Client {client_name} not found",
                status_code=404,
            )

        client.status = "archived"
        db.add(client)

        archive_programmes_stmt = (
            update(Programme)
            .where(Programme.client_id == client.id)
            .where(Programme.status != "archived")
            .values(status="archived")
        )
        db.execute(archive_programmes_stmt)

        db.commit()
        db.refresh(client)
        return client
    except AppException:
        raise
    except Exception as exc:
        logger.exception("soft_delete_client_failed")
        db.rollback()
        raise DatabaseOperationException(f"Unable to archive client: {client_name}") from exc


def check_client_name_exists(
    db: Session,
    name: str,
    exclude_name: str | None = None,
) -> bool:
    """Return True if a different client with the same name already exists."""
    try:
        query = text(_read_sql_file("check_client_name_exists.sql"))
        exists = db.execute(query, {"name": name, "exclude_name": exclude_name}).scalar()
        return bool(exists)
    except Exception as exc:
        raise DatabaseOperationException(f"Unable to check client name: {name}") from exc


def count_active_projects_by_client(db: Session, client_id) -> int:
    """Return count of non-archived projects across all programmes for a client."""
    try:

        stmt = (
            sa_select(func.count())
            .select_from(Project)
            .join(Programme, Programme.id == Project.programme_id)
            .where(Programme.client_id == client_id)
            .where(Project.status.notin_(["archived", "complete"]))
        )
        count = db.execute(stmt).scalar_one()
        return int(count or 0)
    except Exception as exc:
        logger.exception("client_active_project_count_failed")
        raise DatabaseOperationException(
            f"Unable to check active projects for client: {client_id}"
        ) from exc
