"""Unit tests for RAG data models."""

import uuid

from app.models.document_models import Document, RagChunk


def test_document_model():
    doc_id = uuid.uuid4()
    user_id = uuid.uuid4()
    doc = Document(
        document_id=doc_id,
        file_name="test.txt",
        s3_key="s3://b/test.txt",
        user_id=user_id,
    )
    assert doc.document_id == doc_id
    assert doc.file_name == "test.txt"


def test_rag_chunk_model():
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk = RagChunk(
        chunk_id=chunk_id, document_id=doc_id, chunk="text", vector_embedding=[0.1, 0.2]
    )
    assert chunk.chunk_id == chunk_id
    assert chunk.chunk == "text"
