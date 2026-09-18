from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseOperationException
from app.database.file_metadata_db import (
    archive_document,
    check_file_hash_exists,
    insert_file_metadata,
    list_documents_by_entity,
)
from app.database.rag_chunks_db import delete_rag_chunks_by_document_id
from app.models.document_models import Document, RagChunk

ENTITY_ID = "entity-abc123"
DOC_ID = "12345678-1234-5678-1234-567812345678"


def test_check_file_hash_exists_success():
    mock_db = MagicMock(spec=Session)
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_doc = Document()
    mock_filter.first.return_value = mock_doc

    result = check_file_hash_exists(mock_db, "somehash", ENTITY_ID)

    assert result is mock_doc
    mock_db.query.assert_called_once_with(Document)
    mock_query.filter.assert_called_once()
    mock_filter.first.assert_called_once()


def test_check_file_hash_exists_exception():
    mock_db = MagicMock(spec=Session)
    mock_db.query.side_effect = Exception("DB error")

    with pytest.raises(DatabaseOperationException, match="Unable to check file hash: somehash"):
        check_file_hash_exists(mock_db, "somehash", ENTITY_ID)


def test_insert_file_metadata_success():
    mock_db = MagicMock(spec=Session)

    result = insert_file_metadata(
        mock_db,
        file_hash="hash123",
        file_name="test.txt",
        s3_key="folder/test.txt",
        user_id="user123",
        entity_id=ENTITY_ID,
    )

    assert result.file_hash == "hash123"
    assert result.file_name == "test.txt"
    assert result.s3_key == "folder/test.txt"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(result)


def test_insert_file_metadata_exception():
    mock_db = MagicMock(spec=Session)
    mock_db.add.side_effect = Exception("Insert error")

    with pytest.raises(
        DatabaseOperationException, match="Unable to insert file metadata: test.txt"
    ):
        insert_file_metadata(
            mock_db,
            file_hash="hash123",
            file_name="test.txt",
            s3_key="folder/test.txt",
            user_id="user123",
            entity_id=ENTITY_ID,
        )
    mock_db.rollback.assert_called_once()


def test_insert_file_metadata_integrity_error():
    from sqlalchemy.exc import IntegrityError

    mock_db = MagicMock(spec=Session)
    mock_db.commit.side_effect = IntegrityError("stmt", "params", "orig")

    with pytest.raises(IntegrityError):
        insert_file_metadata(
            mock_db,
            file_hash="hash123",
            file_name="test.txt",
            s3_key="folder/test.txt",
            user_id="user123",
            entity_id=ENTITY_ID,
        )
    mock_db.rollback.assert_called_once()


def test_list_documents_by_entity_success():
    mock_db = MagicMock(spec=Session)
    mock_query = mock_db.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_order_by = mock_filter.order_by.return_value
    docs = [Document(), Document()]
    mock_order_by.all.return_value = docs

    result = list_documents_by_entity(mock_db, ENTITY_ID)

    assert result == docs
    mock_db.query.assert_called_once_with(Document)
    mock_query.filter.assert_called_once()
    mock_filter.order_by.assert_called_once()
    mock_order_by.all.assert_called_once()


def test_list_documents_by_entity_exception():
    mock_db = MagicMock(spec=Session)
    mock_db.query.side_effect = Exception("DB error")

    with pytest.raises(
        DatabaseOperationException,
        match=f"Unable to list documents for entity: {ENTITY_ID}",
    ):
        list_documents_by_entity(mock_db, ENTITY_ID)


def test_archive_document_success():
    mock_db = MagicMock(spec=Session)
    mock_doc = Document()
    mock_doc.is_archived = False
    mock_db.query.return_value.filter.return_value.first.return_value = mock_doc

    res = archive_document(mock_db, DOC_ID)

    assert res is mock_doc
    assert mock_doc.is_archived is True


def test_archive_document_not_found():
    mock_db = MagicMock(spec=Session)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    res = archive_document(mock_db, DOC_ID)

    assert res is None


def test_archive_document_exception():
    mock_db = MagicMock(spec=Session)
    mock_db.query.side_effect = Exception("DB error")

    with pytest.raises(DatabaseOperationException, match=f"Unable to archive document: {DOC_ID}"):
        archive_document(mock_db, DOC_ID)


def test_delete_rag_chunks_by_document_id_success():
    mock_db = MagicMock(spec=Session)
    mock_db.query.return_value.filter.return_value.delete.return_value = 5

    count = delete_rag_chunks_by_document_id(mock_db, DOC_ID)

    assert count == 5
    mock_db.query.assert_called_once_with(RagChunk)


def test_delete_rag_chunks_by_document_id_exception():
    mock_db = MagicMock(spec=Session)
    mock_db.query.side_effect = Exception("DB error")

    with pytest.raises(
        DatabaseOperationException, match=f"Unable to delete RAG chunks for document: {DOC_ID}"
    ):
        delete_rag_chunks_by_document_id(mock_db, DOC_ID)


def test_get_document_by_id_success():
    from app.database.file_metadata_db import get_document_by_id

    mock_db = MagicMock(spec=Session)
    mock_doc = Document()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_doc

    res = get_document_by_id(mock_db, DOC_ID)
    assert res is mock_doc


def test_get_document_by_id_exception():
    from app.database.file_metadata_db import get_document_by_id

    mock_db = MagicMock(spec=Session)
    mock_db.query.side_effect = Exception("Lookup failed")

    with pytest.raises(DatabaseOperationException, match=f"Unable to look up document: {DOC_ID}"):
        get_document_by_id(mock_db, DOC_ID)


def test_insert_rag_chunks_empty():
    from uuid import UUID

    from app.database.rag_chunks_db import insert_rag_chunks

    mock_db = MagicMock(spec=Session)
    count = insert_rag_chunks(mock_db, document_id=UUID(DOC_ID), chunks=[])
    assert count == 0


def test_insert_rag_chunks_success():
    from uuid import UUID

    from app.database.rag_chunks_db import insert_rag_chunks

    mock_db = MagicMock(spec=Session)
    count = insert_rag_chunks(
        mock_db, document_id=UUID(DOC_ID), chunks=[("text1", [0.1, 0.2]), ("text2", [0.3, 0.4])]
    )
    assert count == 2
    mock_db.add_all.assert_called_once()
    mock_db.flush.assert_called_once()


def test_insert_rag_chunks_integrity_error():
    from uuid import UUID

    from sqlalchemy.exc import IntegrityError

    from app.database.rag_chunks_db import insert_rag_chunks

    mock_db = MagicMock(spec=Session)
    mock_db.add_all.side_effect = IntegrityError("stmt", "params", "orig")

    with pytest.raises(DatabaseOperationException, match="does not exist in the documents table"):
        insert_rag_chunks(mock_db, document_id=UUID(DOC_ID), chunks=[("text1", [0.1, 0.2])])


def test_insert_rag_chunks_generic_exception():
    from uuid import UUID

    from app.database.rag_chunks_db import insert_rag_chunks

    mock_db = MagicMock(spec=Session)
    mock_db.add_all.side_effect = Exception("DB fail")

    with pytest.raises(DatabaseOperationException, match="Unable to persist rag chunks"):
        insert_rag_chunks(mock_db, document_id=UUID(DOC_ID), chunks=[("text1", [0.1, 0.2])])
