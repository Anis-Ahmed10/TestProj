"""Business service for S3 file upload operations."""

from __future__ import annotations

from http import HTTPStatus

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppException, DatabaseOperationException, ResourceNotFoundError
from app.core.logging import logger
from app.core.s3_client import get_s3_client
from app.database.file_metadata_db import archive_document as archive_document_db
from app.database.file_metadata_db import (
    check_file_hash_exists,
    get_document_by_id,
    insert_file_metadata,
    list_documents_by_entity,
)
from app.database.rag_chunks_db import delete_rag_chunks_by_document_id
from app.models.document_models import Document
from app.schemas.file_operations import (
    DocumentListItem,
    DocumentListResponse,
    DuplicateCheckResponse,
    PresignedUrlResponse,
)

_DEFAULT_EXPIRY_SECONDS = 1200


class FileOperationsService:
    """Handle presigned-URL generation and direct file uploads to S3."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._bucket = get_settings().s3_bucket_name

    def check_duplicate(self, file_hash: str, entity_id: str) -> DuplicateCheckResponse:
        """Check whether a file with the given SHA-256 hash already exists."""
        existing = check_file_hash_exists(self.db, file_hash, entity_id)

        if existing:
            return DuplicateCheckResponse(
                is_duplicate=True,
                id=str(existing.document_id),
                file_name=existing.file_name,
                message="File already exists. Upload skipped.",
            )

        return DuplicateCheckResponse(
            is_duplicate=False,
            message="File is new. Proceed with upload.",
        )

    def generate_presigned_url(
        self,
        *,
        file_name: str,
        folder_path: str,
        content_type: str,
        request_type: str = "put_object",
    ) -> PresignedUrlResponse:
        """Generate an S3 pre-signed PUT URL. Metadata is recorded upon confirmation."""
        folder_prefix = self._normalize_folder(folder_path)
        s3_key = self._build_s3_key(folder_prefix, file_name)

        try:
            s3_client = get_s3_client()
            params: dict = {"Bucket": self._bucket, "Key": s3_key}
            if request_type == "put_object":
                params["ContentType"] = content_type

            presigned_url = s3_client.generate_presigned_url(
                ClientMethod=request_type,
                Params=params,
                ExpiresIn=_DEFAULT_EXPIRY_SECONDS,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("s3_presigned_url_generation_failed")
            raise AppException(
                code="PRESIGNED_URL_FAILED",
                message="Unable to generate pre-signed upload URL.",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            ) from exc

        return PresignedUrlResponse(
            presigned_url=presigned_url,
            s3_key=s3_key,
            expires_in=_DEFAULT_EXPIRY_SECONDS,
        )

    def create_file_record(
        self,
        *,
        file_hash: str,
        file_name: str,
        s3_key: str,
        entity_id: str,
        user_id: str | None = None,
    ) -> str:
        """Insert file metadata into the database return the document ID."""
        existing = self.db.query(Document).filter(Document.file_hash == file_hash).first()
        if existing and existing.is_archived is True:

            try:
                existing.is_archived = False
                existing.file_name = file_name
                existing.s3_key = s3_key
                if user_id:
                    existing.user_id = user_id
                existing.entity_id = entity_id
                self.db.commit()
                self.db.refresh(existing)
                return str(existing.document_id)
            except Exception as exc:
                self.db.rollback()
                logger.exception("file_metadata_revive_failed")
                raise AppException(
                    code="FILE_METADATA_INSERT_FAILED",
                    message="Unable to insert file metadata.",
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                ) from exc

        try:
            doc = insert_file_metadata(
                self.db,
                file_hash=file_hash,
                file_name=file_name,
                s3_key=s3_key,
                user_id=user_id,
                entity_id=entity_id,
            )
            return str(doc.document_id)
        except IntegrityError:
            self.db.rollback()
            raise AppException(
                code="DUPLICATE_FILE", message="File already uploaded.", status_code=409
            )
        except DatabaseOperationException:
            logger.exception("file_metadata_insert_failed")
            raise AppException(
                code="FILE_METADATA_INSERT_FAILED",
                message="Unable to insert file metadata.",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def list_documents(self, entity_id: str) -> DocumentListResponse:
        """List all documents uploaded for an entity (client/programme/project)."""
        docs = list_documents_by_entity(self.db, entity_id)
        return DocumentListResponse(
            entity_id=entity_id,
            documents=[
                DocumentListItem(
                    document_id=str(doc.document_id),
                    file_name=doc.file_name,
                )
                for doc in docs
            ],
        )

    def rollback_file_record(self, document_id: str) -> None:
        """Delete file metadata from the database (compensating rollback only — no S3 cleanup)."""
        try:
            doc = self.db.query(Document).filter(Document.document_id == document_id).first()
            if doc:
                self.db.delete(doc)
                self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.exception("file_metadata_delete_failed")
            raise AppException(
                code="FILE_METADATA_DELETE_FAILED",
                message="Unable to delete file metadata.",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            ) from exc

    def delete_document(self, document_id: str, entity_id: str) -> None:
        """Archive a document and delete its associated RAG chunks.

        The S3 file payload is retained in storage. The document's is_archived
        flag is set to True, and associated chunk vector embeddings in
        document_chunks are purged.
        """
        doc = get_document_by_id(self.db, document_id)
        if doc is None or doc.is_archived or str(doc.entity_id) != str(entity_id):
            raise ResourceNotFoundError(f"Document {document_id} not found.")

        try:
            delete_rag_chunks_by_document_id(self.db, document_id)
            archived = archive_document_db(self.db, document_id)
            if archived is None:
                raise ResourceNotFoundError(f"Document {document_id} not found.")
            self.db.commit()
        except ResourceNotFoundError:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            logger.exception("document_archive_failed")
            raise AppException(
                code="DOCUMENT_ARCHIVE_FAILED",
                message="Unable to archive document.",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            ) from exc

    @staticmethod
    def _normalize_folder(folder_path: str) -> str:
        segments = [
            seg.strip() for seg in folder_path.split("/") if seg.strip() and seg.strip() != ".."
        ]
        return "/".join(segments) + "/"

    @staticmethod
    def _build_s3_key(folder_prefix: str, file_name: str) -> str:
        return f"{folder_prefix}{file_name}"
