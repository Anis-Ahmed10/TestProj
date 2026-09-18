"""SQLAlchemy models for the RAG persistence tables."""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import UUID, Boolean, Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.sql import func

from app.core.config import app_settings
from app.core.connection import Base


class Document(Base):
    """Persisted document metadata used by the RAG ingestion pipeline."""

    __tablename__ = "documents"

    document_id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    file_name = Column(String(512), nullable=False)
    file_hash = Column(String(64), nullable=False, unique=True, index=True)
    s3_key = Column(Text, nullable=False)
    user_id = Column(UUID, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_archived = Column(Boolean, nullable=False, server_default=text("false"), default=False)
    entity_id = Column(UUID, nullable=False)


class RagChunk(Base):
    """Persisted chunk text and embedding vectors for a document."""

    __tablename__ = "document_chunks"

    chunk_id = Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    document_id = Column(
        UUID,
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk = Column(Text, nullable=False)
    vector_embedding = Column(Vector(app_settings.rag_embedding_dimensions), nullable=True)
