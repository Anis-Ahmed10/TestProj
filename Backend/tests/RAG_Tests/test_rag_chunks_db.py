"""Unit tests for the RAG chunks database helpers."""

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import DatabaseOperationException
from app.database.rag_chunks_db import insert_rag_chunks


def test_insert_rag_chunks_empty():
    db = MagicMock()
    assert insert_rag_chunks(db, document_id=uuid.uuid4(), chunks=[]) == 0
    db.add_all.assert_not_called()


def test_insert_rag_chunks_success():
    db = MagicMock()
    doc_id = uuid.uuid4()
    chunks = [("chunk1", [0.1]), ("  ", [0.2]), ("chunk3", [0.3])]
    count = insert_rag_chunks(db, document_id=doc_id, chunks=chunks)
    assert count == 2  # The empty text chunk is skipped
    db.add_all.assert_called_once()
    db.flush.assert_called_once()


def test_insert_rag_chunks_integrity_error():
    db = MagicMock()
    db.flush.side_effect = IntegrityError("statement", "params", "orig")
    doc_id = uuid.uuid4()
    with pytest.raises(DatabaseOperationException, match=f"Document ID {doc_id} does not exist"):
        insert_rag_chunks(db, document_id=doc_id, chunks=[("c1", [0.1])])


def test_insert_rag_chunks_failure():
    db = MagicMock()
    db.flush.side_effect = Exception("DB error")
    with pytest.raises(DatabaseOperationException, match="Unable to persist rag chunks"):
        insert_rag_chunks(db, document_id=uuid.uuid4(), chunks=[("c1", [0.1])])
