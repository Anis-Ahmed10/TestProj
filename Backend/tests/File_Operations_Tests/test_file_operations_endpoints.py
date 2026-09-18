import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.endpoints.file_operations import (
    check_duplicate,
    confirm_upload,
    generate_presigned_url,
    list_documents,
)
from app.core.exceptions import AppException
from app.schemas.file_operations import (
    ConfirmUploadRequest,
    DocumentListResponse,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    PresignedUrlRequest,
    PresignedUrlResponse,
)

FILE_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
ENTITY_ID = "entity-abc123"


@pytest.fixture
def mock_service():
    service = MagicMock()
    service.db = MagicMock()
    return service


_DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_check_duplicate_success(mock_create_log, mock_service):
    mock_service.check_duplicate.return_value = DuplicateCheckResponse(
        is_duplicate=False, message="Not a duplicate"
    )
    req = DuplicateCheckRequest(file_hash=FILE_HASH, entity_id=ENTITY_ID)

    response = await check_duplicate(
        body=req, service=mock_service, current_user_id=_DUMMY_USER_ID
    )

    assert response.message == "Not a duplicate"
    assert response.data.is_duplicate is False
    mock_service.check_duplicate.assert_called_once_with(file_hash=FILE_HASH, entity_id=ENTITY_ID)
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_check_duplicate_app_exception(mock_create_log, mock_service):
    mock_service.check_duplicate.side_effect = AppException(
        code="SOME_ERROR", message="msg", status_code=400
    )
    req = DuplicateCheckRequest(file_hash=FILE_HASH, entity_id=ENTITY_ID)

    with pytest.raises(AppException) as excinfo:
        await check_duplicate(body=req, service=mock_service, current_user_id=_DUMMY_USER_ID)

    assert excinfo.value.status_code == 400
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_check_duplicate_generic_exception(mock_create_log, mock_service):
    mock_service.check_duplicate.side_effect = Exception("Generic")
    req = DuplicateCheckRequest(file_hash=FILE_HASH, entity_id=ENTITY_ID)

    with pytest.raises(AppException) as excinfo:
        await check_duplicate(body=req, service=mock_service, current_user_id=_DUMMY_USER_ID)

    assert excinfo.value.status_code == 500
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_generate_presigned_url_success(mock_create_log, mock_service):
    mock_service.generate_presigned_url.return_value = PresignedUrlResponse(
        presigned_url="url", s3_key="key", expires_in=900
    )
    req = PresignedUrlRequest(
        file_name="test.txt",
        folder_path="folder",
        content_type="text/plain",
    )

    response = await generate_presigned_url(
        payload=req, service=mock_service, current_user_id=_DUMMY_USER_ID
    )

    assert response.data.presigned_url == "url"
    mock_service.generate_presigned_url.assert_called_once()
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_generate_presigned_url_app_exception(mock_create_log, mock_service):
    mock_service.generate_presigned_url.side_effect = AppException(
        code="ERR", message="msg", status_code=400
    )
    req = PresignedUrlRequest(
        file_name="test.txt",
        folder_path="folder",
        content_type="text/plain",
    )

    with pytest.raises(AppException):
        await generate_presigned_url(
            payload=req, service=mock_service, current_user_id=_DUMMY_USER_ID
        )
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_generate_presigned_url_generic_exception(mock_create_log, mock_service):
    mock_service.generate_presigned_url.side_effect = Exception("Generic")
    req = PresignedUrlRequest(
        file_name="test.txt",
        folder_path="folder",
        content_type="text/plain",
    )

    with pytest.raises(AppException):
        await generate_presigned_url(
            payload=req, service=mock_service, current_user_id=_DUMMY_USER_ID
        )
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@patch("app.api.v1.endpoints.file_operations.ingest_document")
@pytest.mark.asyncio
async def test_confirm_upload_success(mock_ingest, mock_create_log, mock_service):
    mock_service.create_file_record.return_value = "12345678-1234-5678-1234-567812345678"
    req = ConfirmUploadRequest(
        file_hash=FILE_HASH,
        file_name="test.txt",
        s3_key="s3://url",
        resource_path="folder",
        content_type="text/plain",
        entity_id=ENTITY_ID,
    )

    response = await confirm_upload(
        payload=req, service=mock_service, current_user_id=_DUMMY_USER_ID
    )

    assert response.data.document_id == "12345678-1234-5678-1234-567812345678"
    mock_service.create_file_record.assert_called_once()
    mock_ingest.assert_called_once()
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_confirm_upload_invalid_uuid(mock_create_log, mock_service):
    mock_service.create_file_record.return_value = "invalid-uuid"
    req = ConfirmUploadRequest(
        file_hash=FILE_HASH,
        file_name="test.txt",
        s3_key="s3://url",
        resource_path="folder",
        content_type="text/plain",
        entity_id=ENTITY_ID,
    )

    with pytest.raises(AppException) as excinfo:
        await confirm_upload(payload=req, service=mock_service, current_user_id=_DUMMY_USER_ID)

    assert excinfo.value.code == "INVALID_UUID"
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_confirm_upload_app_exception(mock_create_log, mock_service):
    mock_service.create_file_record.side_effect = AppException(
        code="ERR", message="msg", status_code=400
    )
    req = ConfirmUploadRequest(
        file_hash=FILE_HASH,
        file_name="test.txt",
        s3_key="s3://url",
        resource_path="folder",
        content_type="text/plain",
        entity_id=ENTITY_ID,
    )

    with pytest.raises(AppException):
        await confirm_upload(payload=req, service=mock_service, current_user_id=_DUMMY_USER_ID)
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_confirm_upload_app_exception_after_record_creation(mock_create_log, mock_service):
    mock_service.create_file_record.return_value = "12345678-1234-5678-1234-567812345678"
    mock_service.generate_presigned_url.side_effect = AppException(
        code="ERR", message="msg", status_code=400
    )
    req = ConfirmUploadRequest(
        file_hash=FILE_HASH,
        file_name="test.txt",
        s3_key="s3://url",
        resource_path="folder",
        content_type="text/plain",
        entity_id=ENTITY_ID,
    )

    with pytest.raises(AppException):
        await confirm_upload(payload=req, service=mock_service, current_user_id=_DUMMY_USER_ID)

    mock_service.rollback_file_record.assert_called_once_with(
        "12345678-1234-5678-1234-567812345678"
    )
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_confirm_upload_generic_exception(mock_create_log, mock_service):
    mock_service.create_file_record.side_effect = Exception("Generic")
    req = ConfirmUploadRequest(
        file_hash=FILE_HASH,
        file_name="test.txt",
        s3_key="s3://url",
        resource_path="folder",
        content_type="text/plain",
        entity_id=ENTITY_ID,
    )

    with pytest.raises(AppException) as excinfo:
        await confirm_upload(payload=req, service=mock_service, current_user_id=_DUMMY_USER_ID)

    assert excinfo.value.code == "RAG_CHUNKS_STORE_FAILED"
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@patch("app.api.v1.endpoints.file_operations.ingest_document")
@pytest.mark.asyncio
async def test_confirm_upload_generic_exception_after_record_creation(
    mock_ingest, mock_create_log, mock_service
):
    mock_service.create_file_record.return_value = "12345678-1234-5678-1234-567812345678"
    mock_ingest.side_effect = Exception("Generic")
    req = ConfirmUploadRequest(
        file_hash=FILE_HASH,
        file_name="test.txt",
        s3_key="s3://url",
        resource_path="folder",
        content_type="text/plain",
        entity_id=ENTITY_ID,
    )

    with pytest.raises(AppException) as excinfo:
        await confirm_upload(payload=req, service=mock_service, current_user_id=_DUMMY_USER_ID)

    assert excinfo.value.code == "RAG_CHUNKS_STORE_FAILED"
    mock_service.rollback_file_record.assert_called_once_with(
        "12345678-1234-5678-1234-567812345678"
    )
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_check_duplicate_create_log_entry_fails(mock_create_log, mock_service):
    mock_service.check_duplicate.return_value = DuplicateCheckResponse(
        is_duplicate=False, message="Not a duplicate"
    )
    mock_create_log.side_effect = Exception("Log failure")
    req = DuplicateCheckRequest(file_hash=FILE_HASH, entity_id=ENTITY_ID)

    response = await check_duplicate(
        body=req, service=mock_service, current_user_id=_DUMMY_USER_ID
    )
    assert response.data.is_duplicate is False


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_generate_presigned_url_create_log_entry_fails(mock_create_log, mock_service):
    mock_service.generate_presigned_url.return_value = PresignedUrlResponse(
        presigned_url="url", s3_key="key", expires_in=900
    )
    mock_create_log.side_effect = Exception("Log failure")
    req = PresignedUrlRequest(
        file_name="test.txt",
        folder_path="folder",
        content_type="text/plain",
    )

    response = await generate_presigned_url(
        payload=req, service=mock_service, current_user_id=_DUMMY_USER_ID
    )
    assert response.data.presigned_url == "url"


@patch("app.utils.audit_log.create_log_entry")
@patch("app.api.v1.endpoints.file_operations.ingest_document")
@pytest.mark.asyncio
async def test_confirm_upload_create_log_entry_fails(mock_ingest, mock_create_log, mock_service):
    mock_service.create_file_record.return_value = "12345678-1234-5678-1234-567812345678"
    mock_create_log.side_effect = Exception("Log failure")
    req = ConfirmUploadRequest(
        file_hash=FILE_HASH,
        file_name="test.txt",
        s3_key="s3://url",
        resource_path="folder",
        content_type="text/plain",
        entity_id=ENTITY_ID,
    )

    response = await confirm_upload(
        payload=req, service=mock_service, current_user_id=_DUMMY_USER_ID
    )
    assert response.data.document_id == "12345678-1234-5678-1234-567812345678"


@pytest.mark.asyncio
async def test_list_documents_success(mock_service):
    mock_service.list_documents.return_value = DocumentListResponse(
        entity_id=ENTITY_ID, documents=[]
    )

    response = await list_documents(
        entity_id=ENTITY_ID, service=mock_service, current_user_id=_DUMMY_USER_ID
    )

    assert response.message == "Documents retrieved successfully"
    assert response.data.entity_id == ENTITY_ID
    mock_service.list_documents.assert_called_once_with(entity_id=ENTITY_ID)


@pytest.mark.asyncio
async def test_list_documents_app_exception(mock_service):
    mock_service.list_documents.side_effect = AppException(
        code="SOME_ERROR", message="msg", status_code=400
    )

    with pytest.raises(AppException) as excinfo:
        await list_documents(
            entity_id=ENTITY_ID, service=mock_service, current_user_id=_DUMMY_USER_ID
        )

    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
async def test_list_documents_generic_exception(mock_service):
    mock_service.list_documents.side_effect = Exception("Generic")

    with pytest.raises(AppException) as excinfo:
        await list_documents(
            entity_id=ENTITY_ID, service=mock_service, current_user_id=_DUMMY_USER_ID
        )

    assert excinfo.value.code == "DOCUMENT_LIST_FAILED"


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# delete_document endpoint (archiving)
# ---------------------------------------------------------------------------

from app.api.v1.endpoints.file_operations import (  # noqa: E402
    delete_document as delete_document_endpoint,
)
from app.core.exceptions import ResourceNotFoundError  # noqa: E402


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_delete_document_endpoint_success(mock_create_log, mock_service):
    """Happy path: service.delete_document succeeds → 200 with document_id and archived message."""
    mock_service.delete_document.return_value = None
    doc_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    ent_id = uuid.UUID("87654321-4321-8765-4321-876543218765")

    response = await delete_document_endpoint(
        document_id=doc_id,
        entity_id=ent_id,
        service=mock_service,
        current_user_id=_DUMMY_USER_ID,
    )

    assert response.data["document_id"] == str(doc_id)
    assert response.message == "Document archived successfully"
    mock_service.delete_document.assert_called_once_with(
        document_id=str(doc_id), entity_id=str(ent_id)
    )
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_delete_document_endpoint_not_found(mock_create_log, mock_service):
    """Document not found → ResourceNotFoundError propagates (404)."""
    mock_service.delete_document.side_effect = ResourceNotFoundError("Document not found.")
    doc_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    ent_id = uuid.UUID("87654321-4321-8765-4321-876543218765")

    with pytest.raises(ResourceNotFoundError) as excinfo:
        await delete_document_endpoint(
            document_id=doc_id,
            entity_id=ent_id,
            service=mock_service,
            current_user_id=_DUMMY_USER_ID,
        )

    assert excinfo.value.status_code == 404
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_delete_document_endpoint_archive_failure(mock_create_log, mock_service):
    """DB archive fails → AppException with DOCUMENT_ARCHIVE_FAILED propagates."""
    mock_service.delete_document.side_effect = AppException(
        code="DOCUMENT_ARCHIVE_FAILED",
        message="Unable to archive document.",
        status_code=500,
    )
    doc_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    ent_id = uuid.UUID("87654321-4321-8765-4321-876543218765")

    with pytest.raises(AppException) as excinfo:
        await delete_document_endpoint(
            document_id=doc_id,
            entity_id=ent_id,
            service=mock_service,
            current_user_id=_DUMMY_USER_ID,
        )

    assert excinfo.value.code == "DOCUMENT_ARCHIVE_FAILED"
    mock_create_log.assert_called_once()


@patch("app.utils.audit_log.create_log_entry")
@pytest.mark.asyncio
async def test_delete_document_endpoint_generic_exception(mock_create_log, mock_service):
    """Unexpected exception → wrapped as DOCUMENT_ARCHIVE_FAILED by @audit_log."""
    mock_service.delete_document.side_effect = Exception("Unexpected")
    doc_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    ent_id = uuid.UUID("87654321-4321-8765-4321-876543218765")

    with pytest.raises(AppException) as excinfo:
        await delete_document_endpoint(
            document_id=doc_id,
            entity_id=ent_id,
            service=mock_service,
            current_user_id=_DUMMY_USER_ID,
        )

    assert excinfo.value.code == "DOCUMENT_ARCHIVE_FAILED"
    mock_create_log.assert_called_once()


def test_file_operations_router_mounted():
    """Verify that file operations routes are accessible"""
    from app.api.v1.router import api_router

    paths = [route.path for route in api_router.routes]

    # Verify top-level file operation routes
    assert "/check-duplicate" in paths
    assert "/presigned-url" in paths
    assert "/documents" in paths
    assert "/confirm-upload" in paths
