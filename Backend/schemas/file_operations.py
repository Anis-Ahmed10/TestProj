"""Schemas for S3 file upload operations."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DuplicateCheckRequest(BaseModel):
    """Request body for checking whether a file already exists by hash."""

    file_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hex digest of the file content",
    )
    entity_id: str = Field(..., description="ID of the entity to which the file belongs")


class DuplicateCheckResponse(BaseModel):
    """Response indicating whether the file is a duplicate."""

    is_duplicate: bool
    id: Optional[str] = None
    file_name: Optional[str] = None
    message: str


class PresignedUrlRequest(BaseModel):
    """Request body for generating an S3 pre-signed upload URL."""

    file_name: str = Field(..., min_length=1, description="Original file name")
    folder_path: str = Field(
        ...,
        min_length=1,
        description=(
            "S3 folder path, e.g. 'client/programme/project'. "
            "Can be partial — 'client' or 'client/programme'."
        ),
    )
    content_type: str = Field(
        default="application/octet-stream",
        description="MIME type of the file",
    )


class PresignedUrlResponse(BaseModel):
    """Response containing the pre-signed PUT URL and the final S3 key."""

    presigned_url: str
    s3_key: str
    expires_in: int = Field(description="URL validity in seconds")


class ConfirmUploadRequest(BaseModel):
    """Request body for confirming upload and storing RAG chunks."""

    s3_key: str = Field(..., description="S3 key of the document")
    file_name: str = Field(..., description="Name of the file")
    file_hash: str = Field(
        ..., min_length=64, max_length=64, description="SHA-256 hash of the file"
    )
    resource_path: str = Field(..., description="Resource path or folder path")
    content_type: str = Field(..., description="MIME type of the file")
    entity_id: str = Field(..., description="ID of the entity to which the file belongs")


class ConfirmUploadResponse(BaseModel):
    """Response after successfully storing RAG chunks."""

    document_id: str
    message: str


class DocumentListItem(BaseModel):
    """A single document's metadata, as shown in the Documents tab."""

    document_id: str
    file_name: str


class DocumentListResponse(BaseModel):
    """List of documents uploaded against a given entity (client/programme/project)."""

    entity_id: str
    documents: list[DocumentListItem]
