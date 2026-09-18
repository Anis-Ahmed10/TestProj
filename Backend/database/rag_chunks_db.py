"""Database helpers for RAG document and chunk persistence."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseOperationException
from app.core.logging import logger
from app.models.document_models import RagChunk


def insert_rag_chunks(
    db: Session,
    *,
    document_id: UUID,
    chunks: Sequence[tuple[str, Sequence[float]]],
) -> int:
    """Insert chunk text and embeddings for a document."""

    if not chunks:
        return 0

    try:
        chunk_records = [
            RagChunk(
                document_id=document_id,
                chunk=chunk_text,
                vector_embedding=vector,
            )
            for chunk_text, vector in chunks
            if chunk_text.strip()
        ]

        db.add_all(chunk_records)
        db.flush()
        return len(chunk_records)
    except IntegrityError as exc:
        logger.exception("rag_chunks_insert_integrity_error", extra={"document_id": document_id})
        raise DatabaseOperationException(
            f"Document ID {document_id} does not exist in the documents table."
        ) from exc
    except Exception as exc:
        logger.exception("rag_chunks_insert_failed", extra={"document_id": document_id})
        raise DatabaseOperationException("Unable to persist rag chunks") from exc


def delete_rag_chunks_by_document_id(db: Session, document_id: UUID | str) -> int:
    """Delete all RAG chunk records associated with a document_id."""
    try:
        count = (
            db.query(RagChunk)
            .filter(RagChunk.document_id == document_id)
            .delete(synchronize_session=False)
        )
        return count
    except Exception as exc:
        logger.exception("rag_chunks_delete_failed", extra={"document_id": str(document_id)})
        raise DatabaseOperationException(
            f"Unable to delete RAG chunks for document: {document_id}"
        ) from exc
