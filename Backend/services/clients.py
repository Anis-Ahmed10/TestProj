"""Business service for client management."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, DatabaseOperationException, InvalidInputError
from app.core.logging import logger
from app.database.access_scope_db import (
    get_visible_client_ids,
    get_visible_counts_by_client,
    get_visible_programme_ids,
)
from app.database.clients_db import (
    check_client_name_exists,
    count_active_projects_by_client,
    create_client_entry,
    get_client_by_name,
    get_programs_by_client_id,
    list_client_entries,
    soft_delete_client,
    update_client_in_db,
)
from app.database.users_db import get_user_by_id
from app.models.clients_models import Client
from app.schemas.clients import (
    ClientCreateRequest,
    ClientDetailResponseNoTimestamps,
    ClientListResponse,
    ClientResponse,
    ClientUpdate,
    ProgramResponse,
)


class ClientService:
    """Handle client creation and retrieval logic."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_client(
        self,
        db: Session,
        payload: ClientCreateRequest,
        manager_id: UUID | str,
    ) -> ClientResponse:
        """Create a new client after validating business rules."""

        existing_client = get_client_by_name(db, payload.name)
        if existing_client is not None:
            raise AppException(
                code="CLIENT_ALREADY_EXISTS",
                message="A client with this name already exists.",
                status_code=HTTPStatus.CONFLICT,
            )

        try:
            client = create_client_entry(
                self.db,
                name=payload.name,
                industry=payload.industry,
                location=payload.location,
                contact=payload.contact,
                manager_id=manager_id,
            )
        except IntegrityError as exc:
            logger.exception("client_create_failed")
            db.rollback()
            raise AppException(
                code="CLIENT_ALREADY_EXISTS",
                message="A client with this name already exists.",
                status_code=HTTPStatus.CONFLICT,
            ) from exc

        manager_user = get_user_by_id(self.db, manager_id)
        client.manager_name = manager_user.name if manager_user else None

        return ClientResponse.model_validate(client)

    def list_clients(
        self,
        db: Session,
        current_user_id: UUID,
    ) -> ClientListResponse:
        """Return all clients without pagination."""

        try:
            clients = list_client_entries(db)
        except DatabaseOperationException as exc:
            logger.exception("client_list_failed")
            raise AppException(
                code="CLIENT_LIST_FAILED",
                message="Unable to fetch clients right now.",
                status_code=500,
            ) from exc

        visible_ids = get_visible_client_ids(db, current_user_id)
        if visible_ids is not None:
            clients = [c for c in clients if c.id in visible_ids]

        scoped_counts = get_visible_counts_by_client(db, current_user_id)

        items = []
        for client in clients:
            item = ClientResponse.model_validate(client)
            if scoped_counts is not None:
                counts = scoped_counts.get(client.id, {})
                item.programmes_count = counts.get("programmes_count", 0)
                item.projects_count = counts.get("projects_count", 0)
                item.active_members_count = counts.get("active_members_count", 0)
            items.append(item)

        return ClientListResponse(
            items=items,
            total=len(items),
        )

    @staticmethod
    def _normalize_client_name(client_name: str) -> str:
        """Normalize client names received from API routes."""

        normalized_name = client_name.strip()
        if not normalized_name:
            raise InvalidInputError("Client name is required")
        return normalized_name

    def get_client_details(
        self,
        client_name: str,
        current_user_id: UUID,
    ) -> ClientDetailResponseNoTimestamps:
        """Return a client with associated programs.if visible to the user."""
        try:
            normalized_name = self._normalize_client_name(client_name)
            client = get_client_by_name(self.db, normalized_name)
            if client is None:
                raise AppException(
                    code="NOT_FOUND",
                    message=f"Client {normalized_name} not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )

            visible_ids = get_visible_client_ids(self.db, current_user_id)
            if visible_ids is not None and client.id not in visible_ids:
                raise AppException(
                    code="FORBIDDEN",
                    message="You do not have access to this client.",
                    status_code=HTTPStatus.FORBIDDEN,
                )

            scoped_counts = get_visible_counts_by_client(self.db, current_user_id)

            programs_payload = get_programs_by_client_id(self.db, client.id)

            visible_programme_ids = get_visible_programme_ids(self.db, current_user_id)
            if visible_programme_ids is not None:
                programs_payload = [
                    p for p in programs_payload if p["id"] in visible_programme_ids
                ]
            programs = [ProgramResponse(**p) for p in programs_payload]

            manager_name = None
            if client.manager_id:
                user = get_user_by_id(self.db, client.manager_id)
                manager_name = user.name if user else None

            response = ClientDetailResponseNoTimestamps(
                id=client.id,
                name=client.name,
                industry=client.industry,
                location=client.location,
                contact=client.contact,
                status=client.status,
                manager_id=client.manager_id,
                manager_name=manager_name,
                programs=programs,
            )

            if scoped_counts is not None and hasattr(response, "programmes_count"):
                counts = scoped_counts.get(client.id, {})
                response.programmes_count = counts.get("programmes_count", 0)
                response.projects_count = counts.get("projects_count", 0)
                response.active_members_count = counts.get("active_members_count", 0)

            return response

        except AppException:
            logger.warning("get_client_details_failed")
            raise
        except Exception as exc:
            logger.exception("get_client_details_unexpected_failure")
            raise AppException(
                code="CLIENT_DETAILS_FETCH_FAILED",
                message="Failed to fetch client details",
                status_code=500,
            ) from exc

    def update_client(
        self, client_name: str, payload: ClientUpdate, current_user_id: UUID
    ) -> ClientResponse:
        """Update client details with validation and uniqueness constraints."""
        try:
            normalized_name = self._normalize_client_name(client_name)
            client = get_client_by_name(self.db, normalized_name)
            if client is None:
                raise AppException(
                    code="NOT_FOUND",
                    message=f"Client {normalized_name} not found",
                    status_code=404,
                )

            visible_ids = get_visible_client_ids(self.db, current_user_id)
            if visible_ids is not None and client.id not in visible_ids:
                raise AppException(
                    code="FORBIDDEN",
                    message="You do not have access to this client.",
                    status_code=HTTPStatus.FORBIDDEN,
                )

            update_dict: dict[str, Any] = payload.model_dump(mode="json", exclude_unset=True)

            if "manager_id" in update_dict and update_dict["manager_id"] is not None:
                new_manager_id = update_dict["manager_id"]
                manager_user = get_user_by_id(self.db, new_manager_id)
                if not manager_user:
                    raise AppException(
                        code="MANAGER_NOT_FOUND",
                        message=f"Manager user '{new_manager_id}' not found.",
                        status_code=HTTPStatus.BAD_REQUEST,
                    )

            if "name" in update_dict and update_dict["name"] is not None:
                new_name = str(update_dict["name"]).strip()
                if new_name != client.name:
                    if check_client_name_exists(self.db, new_name, exclude_name=client.name):
                        raise InvalidInputError("Client name already exists")
                    update_dict["name"] = new_name

            updated = update_client_in_db(self.db, client.name, update_dict)
            if updated.manager_id:
                user = get_user_by_id(self.db, updated.manager_id)
                if user:
                    updated.manager_name = user.name
            return ClientResponse.model_validate(updated)
        except AppException:
            logger.warning("update_client_failed")
            raise
        except Exception as exc:
            logger.exception("update_client_unexpected_failure")
            raise AppException(
                code="CLIENT_UPDATE_FAILED",
                message="Failed to update client",
                status_code=500,
            ) from exc

    def archive_client(self, client_name: str, current_user_id: UUID) -> str:
        """Soft-delete (archive) the client only if it has no active projects."""
        try:
            normalized_name = self._normalize_client_name(client_name)
            client = get_client_by_name(self.db, normalized_name)
            if client is None:
                raise AppException(
                    code="NOT_FOUND",
                    message=f"Client {normalized_name} not found",
                    status_code=HTTPStatus.NOT_FOUND,
                )

            visible_ids = get_visible_client_ids(self.db, current_user_id)
            if visible_ids is not None and client.id not in visible_ids:
                raise AppException(
                    code="FORBIDDEN",
                    message="You do not have access to this client.",
                    status_code=HTTPStatus.FORBIDDEN,
                )

            active_projects = count_active_projects_by_client(self.db, client.id)
            if active_projects > 0:
                raise AppException(
                    code="CLIENT_DELETE_BLOCKED",
                    message=(
                        "Client cannot be deleted because it has active projects. "
                        "Archive or complete all projects first."
                    ),
                    status_code=HTTPStatus.CONFLICT,
                )

            archived: Client = soft_delete_client(self.db, normalized_name)
            logger.info("client_archived")
            return archived.name
        except AppException as exc:
            if exc.code == "CLIENT_DELETE_BLOCKED":
                logger.info("client_delete_blocked_active_projects")
            else:
                logger.warning("archive_client_failed")
            raise
        except Exception as exc:
            logger.exception("archive_client_unexpected_failure")
            raise AppException(
                code="CLIENT_ARCHIVE_FAILED",
                message="Failed to archive client",
                status_code=500,
            ) from exc
