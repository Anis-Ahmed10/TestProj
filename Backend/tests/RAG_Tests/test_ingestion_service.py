"""Unit tests for the RAG ingestion service orchestration."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import AppException, DatabaseOperationException
from app.services.rag.rag_pipline import ingest_document


def test_ingest_document_s3_url_none():
    with pytest.raises(AppException, match="Provide a valid presigned S3 URL."):
        ingest_document(s3_url=None, document_id=uuid.uuid4())


@patch("app.services.rag.rag_pipline.validate_s3_url")
@patch("app.services.rag.rag_pipline.derive_document_name")
@patch("app.services.rag.rag_pipline.download_to_temp_file")
@patch("app.services.rag.rag_pipline.postgres_session")
@patch("app.services.rag.rag_pipline.extract_text_content")
@patch("app.services.rag.rag_pipline.build_chunk_payloads")
@patch("app.services.rag.rag_pipline.insert_rag_chunks")
def test_ingest_document_s3_success(
    mock_insert,
    mock_build,
    mock_extract,
    mock_session,
    mock_download,
    mock_derive,
    mock_validate,
):
    mock_validate.return_value = "s3://b/f.txt"
    mock_derive.return_value = "f.txt"
    mock_temp_path = MagicMock()
    mock_download.return_value = mock_temp_path
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db

    doc_id = uuid.uuid4()
    mock_extract.return_value = "text"
    mock_build.return_value = [("chunk", [0.1])]
    mock_insert.return_value = 1

    res = ingest_document(s3_url="s3://b/f.txt", document_id=doc_id)

    assert res == doc_id
    mock_db.commit.assert_called_once()
    mock_temp_path.unlink.assert_called_once_with(missing_ok=True)


@patch("app.services.rag.rag_pipline.validate_s3_url")
@patch("app.services.rag.rag_pipline.derive_document_name")
@patch("app.services.rag.rag_pipline.download_to_temp_file")
@patch("app.services.rag.rag_pipline.postgres_session")
@patch("app.services.rag.rag_pipline.extract_text_content")
@patch("app.services.rag.rag_pipline.build_chunk_payloads")
@patch("app.services.rag.rag_pipline.insert_rag_chunks")
def test_ingest_document_app_exception_rollback(
    mock_insert, mock_build, mock_extract, mock_session, mock_download, mock_derive, mock_validate
):
    mock_validate.return_value = "s3://b/f.txt"
    mock_derive.return_value = "f.txt"
    mock_download.return_value = MagicMock()
    mock_extract.return_value = "text"
    mock_build.return_value = [("chunk", [0.1])]
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    mock_insert.side_effect = AppException(code="ERR", message="msg", status_code=500)

    with pytest.raises(AppException):
        ingest_document(s3_url="s3://b/f.txt", document_id=uuid.uuid4())
    mock_db.rollback.assert_called_once()


@patch("app.services.rag.rag_pipline.validate_s3_url")
@patch("app.services.rag.rag_pipline.derive_document_name")
@patch("app.services.rag.rag_pipline.download_to_temp_file")
@patch("app.services.rag.rag_pipline.postgres_session")
@patch("app.services.rag.rag_pipline.extract_text_content")
@patch("app.services.rag.rag_pipline.build_chunk_payloads")
@patch("app.services.rag.rag_pipline.insert_rag_chunks")
def test_ingest_document_general_exception_rollback(
    mock_insert, mock_build, mock_extract, mock_session, mock_download, mock_derive, mock_validate
):
    mock_validate.return_value = "s3://b/f.txt"
    mock_derive.return_value = "f.txt"
    mock_download.return_value = MagicMock()
    mock_extract.return_value = "text"
    mock_build.return_value = [("chunk", [0.1])]
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    mock_insert.side_effect = ValueError("Some weird system error")
    with pytest.raises(AppException, match="Failed to ingest and index the document."):
        ingest_document(s3_url="s3://b/f.txt", document_id=uuid.uuid4())
    mock_db.rollback.assert_called_once()


@patch("app.services.rag.rag_pipline.validate_s3_url")
@patch("app.services.rag.rag_pipline.derive_document_name")
@patch("app.services.rag.rag_pipline.download_to_temp_file")
@patch("app.services.rag.rag_pipline.postgres_session")
@patch("app.services.rag.rag_pipline.extract_text_content")
@patch("app.services.rag.rag_pipline.build_chunk_payloads")
def test_ingest_document_database_operation_exception_outer(
    mock_build, mock_extract, mock_session, mock_download, mock_derive, mock_validate
):
    mock_validate.return_value = "s3://b/f.txt"
    mock_derive.return_value = "f.txt"
    mock_download.return_value = MagicMock()
    mock_extract.return_value = "text"
    mock_build.return_value = [("chunk", [0.1])]
    mock_session.side_effect = DatabaseOperationException("err")

    with pytest.raises(AppException, match="Failed to store the document and embeddings."):
        ingest_document(s3_url="s3://b/f.txt", document_id=uuid.uuid4())


@patch("app.services.rag.rag_pipline.validate_s3_url")
@patch("app.services.rag.rag_pipline.derive_document_name")
@patch("app.services.rag.rag_pipline.download_to_temp_file")
@patch("app.services.rag.rag_pipline.postgres_session")
@patch("app.services.rag.rag_pipline.extract_text_content")
@patch("app.services.rag.rag_pipline.build_chunk_payloads")
@patch("app.services.rag.rag_pipline.insert_rag_chunks")
@patch("app.services.rag.rag_pipline.logger.warning")
def test_ingest_document_unlink_exception(
    mock_logger_warning,
    mock_insert,
    mock_build,
    mock_extract,
    mock_session,
    mock_download,
    mock_derive,
    mock_validate,
):
    mock_validate.return_value = "s3://b/f.txt"
    mock_derive.return_value = "f.txt"
    mock_temp_path = MagicMock()
    mock_temp_path.unlink.side_effect = Exception("OS permission denied")
    mock_download.return_value = mock_temp_path
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    doc_id = uuid.uuid4()
    mock_extract.return_value = "text"
    mock_build.return_value = [("chunk", [0.1])]
    mock_insert.return_value = 1
    ingest_document(s3_url="s3://b/f.txt", document_id=doc_id)
    mock_logger_warning.assert_called_once()


@patch("app.services.rag.rag_pipline.validate_s3_url")
@patch("app.services.rag.rag_pipline.derive_document_name")
@patch("app.services.rag.rag_pipline.download_to_temp_file")
def test_ingest_document_temp_file_none(mock_download, mock_derive, mock_validate):
    mock_validate.return_value = "s3://b/f.txt"
    mock_derive.return_value = "f.txt"
    mock_download.return_value = None

    with pytest.raises(AppException, match="Unable to download the provided S3 document."):
        ingest_document(s3_url="s3://b/f.txt", document_id=uuid.uuid4())


@patch("app.services.rag.rag_pipline.validate_s3_url")
@patch("app.services.rag.rag_pipline.derive_document_name")
@patch("app.services.rag.rag_pipline.download_to_temp_file")
@patch("app.services.rag.rag_pipline.postgres_session")
@patch("app.services.rag.rag_pipline.extract_text_content")
@patch("app.services.rag.rag_pipline.build_chunk_payloads")
@patch("app.services.rag.rag_pipline.insert_rag_chunks")
def test_ingest_document_database_operation_exception_rollback(
    mock_insert, mock_build, mock_extract, mock_session, mock_download, mock_derive, mock_validate
):
    mock_validate.return_value = "s3://b/f.txt"
    mock_derive.return_value = "f.txt"
    mock_download.return_value = MagicMock()
    mock_extract.return_value = "text"
    mock_build.return_value = [("chunk", [0.1])]
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db
    mock_insert.side_effect = DatabaseOperationException("err")

    with pytest.raises(AppException, match="Failed to store the document and embeddings."):
        ingest_document(s3_url="s3://b/f.txt", document_id=uuid.uuid4())
    mock_db.rollback.assert_called_once()


@patch("app.services.rag.rag_pipline.validate_s3_url")
@patch("app.services.rag.rag_pipline.derive_document_name")
@patch("app.services.rag.rag_pipline.download_to_temp_file")
@patch("app.services.rag.rag_pipline.postgres_session")
@patch("app.services.rag.rag_pipline.extract_text_content")
@patch("app.services.rag.rag_pipline.build_chunk_payloads")
@patch("app.services.rag.rag_pipline.insert_rag_chunks")
def test_ingest_document_reuses_caller_session(
    mock_insert,
    mock_build,
    mock_extract,
    mock_session,
    mock_download,
    mock_derive,
    mock_validate,
):
    """A caller-supplied session must not trigger a second pool checkout."""
    mock_validate.return_value = "s3://b/f.txt"
    mock_derive.return_value = "f.txt"
    mock_download.return_value = MagicMock()
    mock_extract.return_value = "text"
    mock_build.return_value = [("chunk", [0.1])]

    caller_db = MagicMock()
    doc_id = uuid.uuid4()

    assert ingest_document(s3_url="s3://b/f.txt", document_id=doc_id, db=caller_db) == doc_id

    mock_session.assert_not_called()
    assert mock_insert.call_args.args[0] is caller_db
    caller_db.commit.assert_called_once()
    caller_db.close.assert_not_called()
