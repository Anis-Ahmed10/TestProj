from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_current_user_id,
    get_file_operations_service,
    require_entity_permission,
    require_entity_permission_from_confirm_upload_payload,
    require_entity_permission_from_duplicate_check_payload,
    require_permission,
)
from app.components.authorizer import Permission
from app.core.exceptions import AppException
from app.schemas.common import SuccessResponse
from app.schemas.file_operations import (
    ConfirmUploadRequest,
    ConfirmUploadResponse,
    DocumentListResponse,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    PresignedUrlRequest,
    PresignedUrlResponse,
)
from app.services.file_operations import FileOperationsService
from app.services.rag.rag_pipline import ingest_document
from app.utils.audit_log import audit_log

router = APIRouter(tags=["File Operations"])


@router.post(
    "/check-duplicate",
    response_model=SuccessResponse[DuplicateCheckResponse],
    response_model_exclude_none=True,
    summary="Check if a file already exists by its SHA-256 hash",
    dependencies=[
        Depends(require_entity_permission_from_duplicate_check_payload(Permission.DOCUMENT_UPLOAD))
    ],
)
@audit_log(
    service="file_operations",
    method="POST",
    endpoint="/check-duplicate",
    error_code="DUPLICATE_CHECK_FAILED",
    error_message="Unable to check for duplicate file right now.",
)
async def check_duplicate(
    body: DuplicateCheckRequest,
    service: Annotated[FileOperationsService, Depends(get_file_operations_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[DuplicateCheckResponse]:
    result = service.check_duplicate(file_hash=body.file_hash, entity_id=body.entity_id)
    return SuccessResponse(message=result.message, data=result)


@router.post(
    "/presigned-url",
    response_model=SuccessResponse[PresignedUrlResponse],
    response_model_exclude_none=True,
    summary="Generate a pre-signed S3 PUT URL for direct browser upload",
    dependencies=[Depends(require_permission(Permission.DOCUMENT_UPLOAD))],
)
@audit_log(
    service="file_operations",
    method="POST",
    endpoint="/presigned-url",
    error_code="PRESIGNED_URL_FAILED",
    error_message="Unable to generate a pre-signed URL right now.",
)
async def generate_presigned_url(
    payload: PresignedUrlRequest,
    service: Annotated[FileOperationsService, Depends(get_file_operations_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[PresignedUrlResponse]:
    result = service.generate_presigned_url(
        file_name=payload.file_name,
        folder_path=payload.folder_path,
        content_type=payload.content_type,
    )
    return SuccessResponse(message="Pre-signed URL generated successfully", data=result)


@router.get(
    "/documents",
    response_model=SuccessResponse[DocumentListResponse],
    response_model_exclude_none=True,
    summary="List documents uploaded for an entity (client, programme, or project)",
    dependencies=[Depends(require_entity_permission(Permission.LIST_DOCUMENTS))],
)
@audit_log(
    service="file_operations",
    method="GET",
    endpoint="/documents",
    success_message="Documents retrieved successfully",
    error_code="DOCUMENT_LIST_FAILED",
    error_message="Unable to list documents right now.",
)
async def list_documents(
    entity_id: UUID,
    service: Annotated[FileOperationsService, Depends(get_file_operations_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    result = service.list_documents(entity_id=entity_id)
    return SuccessResponse(
        message="Documents retrieved successfully",
        data=result,
    )


@router.delete(
    "/documents",
    response_model=SuccessResponse[dict],
    response_model_exclude_none=True,
    summary="Archive a document from the library and remove its RAG chunks",
    dependencies=[Depends(require_entity_permission(Permission.DOCUMENT_DELETE))],
)
@audit_log(
    service="file_operations",
    method="DELETE",
    endpoint="/documents",
    success_message="Document archived successfully",
    error_code="DOCUMENT_ARCHIVE_FAILED",
    error_message="Unable to archive document right now.",
)
async def delete_document(
    document_id: UUID,
    entity_id: UUID,
    service: Annotated[FileOperationsService, Depends(get_file_operations_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[dict]:
    service.delete_document(document_id=str(document_id), entity_id=str(entity_id))
    return SuccessResponse(
        message="Document archived successfully",
        data={"document_id": str(document_id)},
    )


@router.post(
    "/confirm-upload",
    response_model=SuccessResponse[ConfirmUploadResponse],
    response_model_exclude_none=True,
    summary="Confirm upload and store RAG chunks",
    dependencies=[
        Depends(require_entity_permission_from_confirm_upload_payload(Permission.DOCUMENT_UPLOAD))
    ],
)
@audit_log(service="file_operations", method="POST", endpoint="/confirm-upload")
async def confirm_upload(
    payload: ConfirmUploadRequest,
    service: Annotated[FileOperationsService, Depends(get_file_operations_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SuccessResponse[ConfirmUploadResponse]:

    document_id_str = None
    try:
        document_id_str = service.create_file_record(
            file_hash=payload.file_hash,
            file_name=payload.file_name,
            s3_key=payload.s3_key,
            entity_id=payload.entity_id,
            user_id=str(current_user_id),
        )
        document_id_obj = UUID(document_id_str)
        data = service.generate_presigned_url(
            file_name=payload.file_name,
            folder_path=payload.resource_path,
            content_type=payload.content_type,
            request_type="get_object",
        )
        # Hand the request's own session to the worker thread rather than let it
        # open a second one — the pool allows a single connection per execution
        # environment. Safe because this coroutine only awaits the thread; the
        # session is never touched from two threads at once.
        await asyncio.to_thread(
            ingest_document,
            s3_url=data.presigned_url,
            name=payload.file_name,
            document_id=document_id_obj,
            db=service.db,
        )
        msg = "Document ingested and RAG chunks stored successfully"
        return SuccessResponse(
            message=msg,
            data=ConfirmUploadResponse(document_id=document_id_str, message=msg),
        )
    except ValueError:
        raise AppException(
            code="INVALID_UUID",
            message="Invalid document_id UUID format.",
            status_code=400,
        )
    except AppException:
        if document_id_str:
            service.rollback_file_record(document_id_str)
        raise
    except Exception:
        if document_id_str:
            service.rollback_file_record(document_id_str)
        raise AppException(
            code="RAG_CHUNKS_STORE_FAILED",
            message="Unable to ingest document and store RAG chunks right now.",
            status_code=500,
        )
