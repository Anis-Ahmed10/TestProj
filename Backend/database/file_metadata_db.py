"""Database access helpers for file metadata (deduplication)."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseOperationException
from app.core.logging import logger
from app.models.document_models import Document


def check_file_hash_exists(db: Session, file_hash: str, entity_id: str) -> Document | None:
    """Return existing active file metadata if a file with this hash exists, else None."""
    try:
        return (
            db.query(Document)
            .filter(
                Document.file_hash == file_hash,
                Document.entity_id == entity_id,
                Document.is_archived.is_(False),
            )
            .first()
        )
    except Exception as exc:
        logger.exception("file_hash_lookup_failed")
        raise DatabaseOperationException(f"Unable to check file hash: {file_hash}") from exc


def insert_file_metadata(
    db: Session,
    *,
    file_hash: str,
    file_name: str,
    s3_key: str,
    user_id: str,
    entity_id: str,
) -> Document:
    """Insert a new file metadata record and return it."""
    try:
        record = Document(
            file_hash=file_hash,
            file_name=file_name,
            s3_key=s3_key,
            user_id=user_id,
            entity_id=entity_id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except IntegrityError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("file_metadata_insert_failed")
        raise DatabaseOperationException(f"Unable to insert file metadata: {file_name}") from exc


def list_documents_by_entity(db: Session, entity_id: str) -> list[Document]:
    """Return all non-archived documents uploaded for a given entity_id.

    entity_id is the client/programme/project id — DocumentsSection is reused
    at every level, so this same query backs the client, programme, and
    project Documents tabs.
    """
    try:
        return (
            db.query(Document)
            .filter(Document.entity_id == entity_id, Document.is_archived.is_(False))
            .order_by(Document.uploaded_at.desc())
            .all()
        )
    except Exception as exc:
        logger.exception("document_list_failed")
        raise DatabaseOperationException(
            f"Unable to list documents for entity: {entity_id}"
        ) from exc


def get_document_by_id(db: Session, document_id: str) -> Document | None:
    """Return the document record for the given document_id, or None if not found."""
    try:
        return db.query(Document).filter(Document.document_id == document_id).first()
    except Exception as exc:
        logger.exception("document_lookup_failed")
        raise DatabaseOperationException(f"Unable to look up document: {document_id}") from exc


def archive_document(db: Session, document_id: str) -> Document | None:
    """Set is_archived to True for the specified document_id and return the record."""
    try:
        doc = db.query(Document).filter(Document.document_id == document_id).first()
        if doc is None:
            return None
        doc.is_archived = True
        return doc
    except Exception as exc:
        logger.exception("document_archive_failed")
        raise DatabaseOperationException(f"Unable to archive document: {document_id}") from exc
