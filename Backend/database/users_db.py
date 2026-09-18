"""Database access helpers for user records."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.components.authorizer import parse_role
from app.core.crypto import encrypt_token
from app.core.exceptions import DatabaseOperationException, ResourceNotFoundError
from app.models.rbac_models import RoleModel
from app.models.users_models import User

logger = logging.getLogger(__name__)


def get_user_by_email(db: Session, email: str) -> User | None:
    try:
        return (
            db.execute(select(User).where(User.email == email.lower().strip())).scalars().first()
        )
    except Exception as exc:
        logger.exception("get_user_by_email_failed", extra={"email": email})
        raise DatabaseOperationException("Unable to fetch user by email") from exc


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Fetch a user by primary key."""
    try:
        return db.get(User, user_id)
    except Exception as exc:
        logger.exception("get_user_by_id_failed", extra={"user_id": str(user_id)})
        raise DatabaseOperationException("Unable to fetch user by id") from exc


def update_user_jira_credentials(
    db: Session,
    user_id: uuid.UUID,
    *,
    jira_email: str | None = None,
    jira_api_token: str | None = None,
) -> User:
    """Update the caller's own Jira email/API token (Profile page).

    Each field is only touched when explicitly provided (non-``None``); an
    empty string clears the stored value. The Profile form leaves the token
    blank to keep the saved one, so overwriting unconditionally would wipe it.
    """
    try:
        user = get_user_by_id(db, user_id)

        if user is None:
            raise DatabaseOperationException(f"User {user_id} not found")

        if jira_email is not None:
            user.jira_email = jira_email or None
        if jira_api_token is not None:
            user.jira_api_token = encrypt_token(jira_api_token) if jira_api_token else None

        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    except DatabaseOperationException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception(
            "update_user_jira_credentials_failed",
            extra={"user_id": str(user_id)},
        )
        raise DatabaseOperationException("Unable to update Jira credentials") from exc


def list_users(db: Session) -> list[User]:
    """Return all active users, ordered by name."""
    try:
        return (
            db.execute(select(User).where(User.is_active.is_(True)).order_by(User.name))
            .scalars()
            .all()
        )
    except Exception as exc:
        logger.exception("list_users_failed")
        raise DatabaseOperationException("Unable to fetch users") from exc


def create_user_on_signup(
    db: Session, cognito_id: uuid.UUID, name: str, email: str, role: str = "Test Lead"
) -> User:
    try:
        parsed_role = parse_role(role)
        role_value = parsed_role.value if parsed_role else role
        user = User(id=cognito_id, name=name or "", email=email.lower().strip(), role=role_value)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as exc:
        db.rollback()
        existing = get_user_by_email(db, email)
        if existing:
            return existing
        raise DatabaseOperationException("Unable to create user record") from exc
    except Exception as exc:
        db.rollback()
        logger.exception("create_user_on_signup_failed", extra={"email": email})
        raise DatabaseOperationException("Unable to create user record") from exc


def list_roles(db: Session) -> list[RoleModel]:
    """Return all roles ordered by name."""
    try:
        return db.execute(select(RoleModel).order_by(RoleModel.name)).scalars().all()
    except Exception as exc:
        logger.exception("list_roles_failed")
        raise DatabaseOperationException("Unable to fetch roles") from exc


def update_user_role(db: Session, user_id: uuid.UUID, role_name: str) -> User:
    """Update role for a user. Returns the updated user record."""
    try:
        user = get_user_by_id(db, user_id)
        if user is None:
            raise ResourceNotFoundError(f"User {user_id} not found")

        role = db.execute(select(RoleModel).where(RoleModel.name == role_name)).scalars().first()
        if role is None:
            raise ResourceNotFoundError(f"Role '{role_name}' not found")

        user.role = role.name
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except ResourceNotFoundError:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception(
            "update_user_role_failed",
            extra={"user_id": str(user_id), "role_name": role_name},
        )
        raise DatabaseOperationException("Unable to update user role") from exc
