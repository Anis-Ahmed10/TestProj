"""Database access helpers for application request log records."""

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseOperationException
from app.core.logging import logger
from app.models.application_log_model import ApplicationLog
from app.models.users_models import User


def create_log_entry(
    db: Session,
    service_name: str,
    http_method: str,
    endpoint: str,
    status_code: int | None = None,
    user_id: uuid.UUID | None = None,
    message: str | None = None,
    project_id: uuid.UUID | None = None,
    client_name: str | None = None,
) -> ApplicationLog:
    """Insert a new application log row and persist it."""

    try:
        log = ApplicationLog(
            service_name=service_name,
            user_id=user_id,
            http_method=http_method,
            endpoint=endpoint,
            status_code=status_code,
            message=message,
            project_id=project_id,
            client_name=client_name,
        )
        db.add(log)
        db.commit()
        return log
    except Exception as exc:
        db.rollback()
        logger.exception("application_log_create_entry_failed")
        raise DatabaseOperationException("Unable to persist application log entry") from exc


def list_log_entries(
    db: Session,
    service_name: str | None = None,
    project_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ApplicationLog], int]:
    try:
        query = db.query(ApplicationLog)
        if service_name:
            services = [s.strip().lower() for s in service_name.split(",") if s.strip()]
            if len(services) == 1:
                query = query.filter(ApplicationLog.service_name == services[0])
            elif len(services) > 1:
                query = query.filter(ApplicationLog.service_name.in_(services))
        if project_id:
            query = query.filter(ApplicationLog.project_id == project_id)
        total = query.count()
        entries = query.order_by(ApplicationLog.logged_at.desc()).offset(offset).limit(limit).all()

        user_ids = {entry.user_id for entry in entries if entry.user_id}
        users_by_id: dict[uuid.UUID, User] = {}
        if user_ids:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            users_by_id = {user.id: user for user in users}

        for entry in entries:
            user = users_by_id.get(entry.user_id) if entry.user_id else None
            entry.user_email = user.email if user else None
            entry.user_name = user.name if user else None

        return entries, total
    except Exception as exc:
        logger.exception("application_log_list_failed")
        raise DatabaseOperationException("Unable to fetch application logs") from exc
