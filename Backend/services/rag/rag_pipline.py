"""RAG ingestion service for S3 URLs and local file paths."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.connection import postgres_session
from app.core.exceptions import AppException, DatabaseOperationException
from app.core.logging import logger
from app.database.rag_chunks_db import insert_rag_chunks
from app.services.rag.helpers import (
    build_chunk_payloads,
    derive_document_name,
    download_to_temp_file,
    extract_text_content,
    source_for_logs,
    validate_s3_url,
)


def ingest_document(
    *,
    s3_url: str | None = None,
    name: str | None = None,
    document_id: UUID,
    db: Session | None = None,
) -> UUID:
    """Ingest a document from S3.

    Pass ``db`` to reuse the caller's session. A request that already holds one
    (the ``get_db`` dependency keeps its connection for the whole request) would
    otherwise need a second connection, and the engine pool is sized at one per
    Lambda execution environment. Without ``db`` this opens its own session, for
    callers that have none.
    """

    valid_s3_url = validate_s3_url(s3_url)
    resolved_document_name = derive_document_name(
        document_name=name,
        s3_url=valid_s3_url,
    )

    logger.info(
        "rag_ingest_start",
        extra={
            "document_name": resolved_document_name,
            "source_reference": source_for_logs(valid_s3_url),
        },
    )

    temp_file_path: Path | None = download_to_temp_file(valid_s3_url)

    try:
        if temp_file_path is None:
            raise AppException(
                code="DOCUMENT_DOWNLOAD_FAILED",
                message="Unable to download the provided S3 document.",
                status_code=400,
            )
        text_content = extract_text_content(temp_file_path)

        chunk_payloads = build_chunk_payloads(text_content)
        scope = nullcontext(db) if db is not None else postgres_session()
        with scope as session:
            try:
                insert_rag_chunks(
                    session,
                    document_id=document_id,
                    chunks=chunk_payloads,
                )
                session.commit()
            except (AppException, DatabaseOperationException):
                session.rollback()
                raise
            except Exception as exc:
                session.rollback()
                logger.exception("rag_ingest_transaction_failed")
                raise AppException(
                    code="RAG_INGEST_FAILED",
                    message="Failed to ingest and index the document.",
                    status_code=500,
                ) from exc

        return document_id
    except DatabaseOperationException as exc:
        logger.exception("rag_persistence_failed")
        raise AppException(
            code="RAG_PERSIST_FAILED",
            message="Failed to store the document and embeddings.",
            status_code=500,
        ) from exc
    finally:
        if temp_file_path is not None:
            try:
                temp_file_path.unlink(missing_ok=True)
            except Exception:
                logger.warning("rag_temp_cleanup_failed", extra={"path": str(temp_file_path)})
