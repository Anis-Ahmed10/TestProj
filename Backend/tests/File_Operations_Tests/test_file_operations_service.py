from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import BotoCoreError

from app.core.exceptions import AppException, DatabaseOperationException
from app.services.file_operations import FileOperationsService

ENTITY_ID = "entity-abc123"


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def file_upload_service(mock_db):
    with patch("app.services.file_operations.get_settings") as mock_settings:
        mock_settings.return_value.s3_bucket_name = "test-bucket"
        service = FileOperationsService(db=mock_db)
        return service


def test_normalize_folder():
    assert FileOperationsService._normalize_folder("some/path/") == "some/path/"
    assert FileOperationsService._normalize_folder("/some//path") == "some/path/"
    assert FileOperationsService._normalize_folder("some") == "some/"


def test_build_s3_key():
    assert FileOperationsService._build_s3_key("folder/", "file.txt") == "folder/file.txt"


@patch("app.services.file_operations.check_file_hash_exists")
def test_check_duplicate_exists(mock_check, file_upload_service):
    mock_existing = MagicMock()
    mock_existing.file_name = "test.txt"
    mock_existing.document_id = "doc-123"
    mock_check.return_value = mock_existing

    resp = file_upload_service.check_duplicate("hash123", ENTITY_ID)
    assert resp.is_duplicate is True
    assert resp.file_name == "test.txt"
    assert resp.id == "doc-123"


@patch("app.services.file_operations.check_file_hash_exists")
def test_check_duplicate_not_exists(mock_check, file_upload_service):
    mock_check.return_value = None

    resp = file_upload_service.check_duplicate("hash123", ENTITY_ID)
    assert resp.is_duplicate is False


@patch("app.services.file_operations.get_s3_client")
def test_generate_presigned_url_success(mock_get_s3_client, file_upload_service):
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://presigned.url"
    mock_get_s3_client.return_value = mock_client

    resp = file_upload_service.generate_presigned_url(
        file_name="test.txt", folder_path="folder", content_type="text/plain"
    )

    assert resp.presigned_url == "https://presigned.url"
    assert resp.s3_key == "folder/test.txt"
    mock_client.generate_presigned_url.assert_called_once()


@patch("app.services.file_operations.get_s3_client")
def test_generate_presigned_url_get_object_excludes_content_type(
    mock_get_s3_client, file_upload_service
):
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://presigned.url"
    mock_get_s3_client.return_value = mock_client

    resp = file_upload_service.generate_presigned_url(
        file_name="test.txt",
        folder_path="folder",
        content_type="text/plain",
        request_type="get_object",
    )

    assert resp.presigned_url == "https://presigned.url"
    call_kwargs = mock_client.generate_presigned_url.call_args
    assert call_kwargs.kwargs["ClientMethod"] == "get_object"
    assert "ContentType" not in call_kwargs.kwargs["Params"]


@patch("app.services.file_operations.get_s3_client")
def test_generate_presigned_url_exception(mock_get_s3_client, file_upload_service):
    mock_client = MagicMock()
    mock_client.generate_presigned_url.side_effect = BotoCoreError()
    mock_get_s3_client.return_value = mock_client

    with pytest.raises(AppException) as excinfo:
        file_upload_service.generate_presigned_url(
            file_name="test.txt", folder_path="folder", content_type="text/plain"
        )
    assert excinfo.value.code == "PRESIGNED_URL_FAILED"


@patch("app.services.file_operations.insert_file_metadata")
def test_create_file_record_success(mock_insert, file_upload_service):
    file_upload_service.db.query.return_value.filter.return_value.first.return_value = None
    mock_doc = MagicMock()
    mock_doc.document_id = "doc-123"
    mock_insert.return_value = mock_doc

    doc_id = file_upload_service.create_file_record(
        file_hash="hash123", file_name="test.txt", s3_key="folder/test.txt", entity_id=ENTITY_ID
    )
    assert doc_id == "doc-123"
    mock_insert.assert_called_once()


def test_create_file_record_revive_success(file_upload_service):
    existing_doc = MagicMock()
    existing_doc.is_archived = True
    existing_doc.document_id = "revived-doc-123"
    file_upload_service.db.query.return_value.filter.return_value.first.return_value = existing_doc

    doc_id = file_upload_service.create_file_record(
        file_hash="hash123",
        file_name="revived.txt",
        s3_key="folder/revived.txt",
        entity_id=ENTITY_ID,
        user_id="user-1",
    )

    assert doc_id == "revived-doc-123"
    assert existing_doc.is_archived is False
    assert existing_doc.file_name == "revived.txt"
    assert existing_doc.s3_key == "folder/revived.txt"
    assert existing_doc.user_id == "user-1"
    assert existing_doc.entity_id == ENTITY_ID
    file_upload_service.db.commit.assert_called_once()
    file_upload_service.db.refresh.assert_called_once_with(existing_doc)


def test_create_file_record_revive_exception(file_upload_service):
    existing_doc = MagicMock()
    existing_doc.is_archived = True
    file_upload_service.db.query.return_value.filter.return_value.first.return_value = existing_doc
    file_upload_service.db.commit.side_effect = Exception("DB commit fail")

    with pytest.raises(AppException) as excinfo:
        file_upload_service.create_file_record(
            file_hash="hash123",
            file_name="revived.txt",
            s3_key="folder/revived.txt",
            entity_id=ENTITY_ID,
        )

    assert excinfo.value.code == "FILE_METADATA_INSERT_FAILED"
    file_upload_service.db.rollback.assert_called_once()


@patch("app.services.file_operations.insert_file_metadata")
def test_create_file_record_exception(mock_insert, file_upload_service):
    file_upload_service.db.query.return_value.filter.return_value.first.return_value = None
    mock_insert.side_effect = DatabaseOperationException("db error")

    with pytest.raises(AppException) as excinfo:
        file_upload_service.create_file_record(
            file_hash="hash123",
            file_name="test.txt",
            s3_key="folder/test.txt",
            entity_id=ENTITY_ID,
        )
    assert excinfo.value.code == "FILE_METADATA_INSERT_FAILED"


@patch("app.services.file_operations.insert_file_metadata")
def test_create_file_record_duplicate_exception(mock_insert, file_upload_service):
    from sqlalchemy.exc import IntegrityError

    file_upload_service.db.query.return_value.filter.return_value.first.return_value = None
    mock_insert.side_effect = IntegrityError("statement", "params", "orig")

    with pytest.raises(AppException) as excinfo:
        file_upload_service.create_file_record(
            file_hash="hash123",
            file_name="test.txt",
            s3_key="folder/test.txt",
            entity_id=ENTITY_ID,
        )
    assert excinfo.value.code == "DUPLICATE_FILE"
    file_upload_service.db.rollback.assert_called_once()


@patch("app.services.file_operations.list_documents_by_entity")
def test_list_documents_returns_documents(mock_list, file_upload_service):
    doc1 = MagicMock()
    doc1.document_id = "doc-1"
    doc1.file_name = "a.txt"
    doc2 = MagicMock()
    doc2.document_id = "doc-2"
    doc2.file_name = "b.txt"
    mock_list.return_value = [doc1, doc2]

    resp = file_upload_service.list_documents(ENTITY_ID)

    mock_list.assert_called_once_with(file_upload_service.db, ENTITY_ID)
    assert resp.entity_id == ENTITY_ID
    assert len(resp.documents) == 2
    assert resp.documents[0].document_id == "doc-1"
    assert resp.documents[0].file_name == "a.txt"
    assert resp.documents[1].document_id == "doc-2"
    assert resp.documents[1].file_name == "b.txt"


@patch("app.services.file_operations.list_documents_by_entity")
def test_list_documents_empty(mock_list, file_upload_service):
    mock_list.return_value = []

    resp = file_upload_service.list_documents(ENTITY_ID)

    assert resp.entity_id == ENTITY_ID
    assert resp.documents == []


def test_rollback_file_record_success(file_upload_service):

    mock_doc = MagicMock()
    file_upload_service.db.query.return_value.filter.return_value.first.return_value = mock_doc

    file_upload_service.rollback_file_record("doc-123")

    file_upload_service.db.delete.assert_called_once_with(mock_doc)
    file_upload_service.db.commit.assert_called_once()


def test_rollback_file_record_not_found(file_upload_service):
    file_upload_service.db.query.return_value.filter.return_value.first.return_value = None
    file_upload_service.rollback_file_record("doc-not-found")
    file_upload_service.db.delete.assert_not_called()


def test_rollback_file_record_exception(file_upload_service):
    file_upload_service.db.query.side_effect = Exception("db error")

    with pytest.raises(AppException) as excinfo:
        file_upload_service.rollback_file_record("doc-123")

    assert excinfo.value.code == "FILE_METADATA_DELETE_FAILED"
    file_upload_service.db.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# delete_document (archiving)
# ---------------------------------------------------------------------------

DOCUMENT_ID = "12345678-1234-5678-1234-567812345678"


@patch("app.services.file_operations.archive_document_db")
@patch("app.services.file_operations.delete_rag_chunks_by_document_id")
@patch("app.services.file_operations.get_document_by_id")
@patch("app.services.file_operations.get_s3_client")
def test_delete_document_success(
    mock_get_s3, mock_get_doc, mock_delete_chunks, mock_archive_db, file_upload_service
):
    """Happy path: RAG chunks purged, DB row is marked archived, S3 file is untouched."""
    mock_doc = MagicMock()
    mock_doc.is_archived = False
    mock_doc.entity_id = ENTITY_ID
    mock_doc.s3_key = "client/programme/project/report.pdf"
    mock_get_doc.return_value = mock_doc
    mock_archive_db.return_value = mock_doc
    mock_s3 = MagicMock()
    mock_get_s3.return_value = mock_s3

    file_upload_service.delete_document(document_id=DOCUMENT_ID, entity_id=ENTITY_ID)

    mock_get_doc.assert_called_once_with(file_upload_service.db, DOCUMENT_ID)
    mock_delete_chunks.assert_called_once_with(file_upload_service.db, DOCUMENT_ID)
    mock_archive_db.assert_called_once_with(file_upload_service.db, DOCUMENT_ID)
    mock_s3.delete_object.assert_not_called()


@patch("app.services.file_operations.archive_document_db")
@patch("app.services.file_operations.delete_rag_chunks_by_document_id")
@patch("app.services.file_operations.get_document_by_id")
def test_delete_document_archive_db_returns_none(
    mock_get_doc, mock_delete_chunks, mock_archive_db, file_upload_service
):
    from app.core.exceptions import ResourceNotFoundError

    mock_doc = MagicMock()
    mock_doc.is_archived = False
    mock_doc.entity_id = ENTITY_ID
    mock_get_doc.return_value = mock_doc
    mock_archive_db.return_value = None

    with pytest.raises(ResourceNotFoundError):
        file_upload_service.delete_document(document_id=DOCUMENT_ID, entity_id=ENTITY_ID)

    mock_delete_chunks.assert_called_once_with(file_upload_service.db, DOCUMENT_ID)
    mock_archive_db.assert_called_once_with(file_upload_service.db, DOCUMENT_ID)
    file_upload_service.db.rollback.assert_called_once()


@patch("app.services.file_operations.get_document_by_id")
def test_delete_document_not_found(mock_get_doc, file_upload_service):
    """Document missing in DB → ResourceNotFoundError (404)."""
    from app.core.exceptions import ResourceNotFoundError

    mock_get_doc.return_value = None

    with pytest.raises(ResourceNotFoundError):
        file_upload_service.delete_document(document_id=DOCUMENT_ID, entity_id=ENTITY_ID)


@patch("app.services.file_operations.get_document_by_id")
def test_delete_document_already_archived(mock_get_doc, file_upload_service):
    """Document already archived in DB → ResourceNotFoundError (404)."""
    from app.core.exceptions import ResourceNotFoundError

    mock_doc = MagicMock()
    mock_doc.is_archived = True
    mock_doc.entity_id = ENTITY_ID
    mock_get_doc.return_value = mock_doc

    with pytest.raises(ResourceNotFoundError):
        file_upload_service.delete_document(document_id=DOCUMENT_ID, entity_id=ENTITY_ID)


@patch("app.services.file_operations.get_document_by_id")
def test_delete_document_entity_id_mismatch(mock_get_doc, file_upload_service):
    """Document entity_id mismatch → ResourceNotFoundError (404)."""
    from app.core.exceptions import ResourceNotFoundError

    mock_doc = MagicMock()
    mock_doc.is_archived = False
    mock_doc.entity_id = "other-entity-id"
    mock_get_doc.return_value = mock_doc

    with pytest.raises(ResourceNotFoundError):
        file_upload_service.delete_document(document_id=DOCUMENT_ID, entity_id=ENTITY_ID)


@patch("app.services.file_operations.delete_rag_chunks_by_document_id")
@patch("app.services.file_operations.get_document_by_id")
def test_delete_document_archive_failed_exception(
    mock_get_doc, mock_delete_chunks, file_upload_service
):
    """Failure during chunk purge or archiving → AppException with DOCUMENT_ARCHIVE_FAILED."""
    mock_doc = MagicMock()
    mock_doc.is_archived = False
    mock_doc.entity_id = ENTITY_ID
    mock_get_doc.return_value = mock_doc
    mock_delete_chunks.side_effect = Exception("DB error")

    with pytest.raises(AppException) as excinfo:
        file_upload_service.delete_document(document_id=DOCUMENT_ID, entity_id=ENTITY_ID)

    assert excinfo.value.code == "DOCUMENT_ARCHIVE_FAILED"
    file_upload_service.db.rollback.assert_called_once()
