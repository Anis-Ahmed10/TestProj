from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, Sequence

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import logger
from app.utils.rag.text import normalize_optional_text


class EmbeddingClient(Protocol):
    """Minimal interface for text embedding providers."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding per text input."""


@dataclass(frozen=True)
class GeminiEmbeddingClient:
    """Gemini Developer API client for text embeddings.

    The client is designed to be instantiated once (via get_embedding_client()) and
    reused across multiple embed_texts calls.
    """

    api_key: str
    endpoint: str
    model_name: str

    output_dimensionality: int = 0
    task_type: str = ""
    request_timeout_seconds: float = 0.0
    normalize_embeddings: bool = False

    # Persist one HTTP client for connection reuse.
    _client: httpx.Client = httpx.Client()

    @classmethod
    def from_settings(cls) -> "GeminiEmbeddingClient":
        """Build a configured Gemini embedding client."""

        settings = get_settings()
        api_key = normalize_optional_text(settings.rag_embedding_api_key)
        if not api_key:
            raise AppException(
                code="RAG_EMBEDDING_CONFIG_ERROR",
                message=(
                    "RAG embedding is not configured. "
                    "Set `RAG_EMBEDDING_API_KEY` or `GEMINI_API_KEY`."
                ),
                status_code=500,
            )

        model_name = settings.rag_embedding_model_name.strip()
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        return cls(
            api_key=api_key,
            endpoint=(
                f"{settings.rag_embedding_base_url.rstrip('/')}/"
                f"{model_name}:batchEmbedContents"
            ),
            model_name=model_name,
            output_dimensionality=settings.rag_embedding_dimensions,
            task_type=settings.rag_embedding_task_type,
            request_timeout_seconds=settings.request_timeout_seconds,
            normalize_embeddings=settings.rag_embedding_normalize,
        )

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Generate one embedding per input text."""

        clean_texts = [text.strip() for text in texts if text and text.strip()]

        if not clean_texts:
            return []

        payload = {
            "requests": [
                {
                    "model": self.model_name,
                    "content": {"parts": [{"text": text}]},
                    "taskType": self.task_type,
                    # Backwards-compat for older unit tests that expected snake_case
                    "outputDimensionality": self.output_dimensionality,
                }
                for text in clean_texts
            ]
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        try:
            # Reuse the persistent client for connection pooling.
            response = self._client.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=self.request_timeout_seconds or None,
            )
            response.raise_for_status()
            data = response.json()

        except httpx.HTTPError as exc:
            logger.exception(
                "rag_embedding_request_failed",
                extra={
                    "provider": "gemini",
                    "status_code": getattr(exc, "response", None) and exc.response.status_code,
                },
            )
            raise AppException(
                code="RAG_EMBEDDING_FAILED",
                message="Failed to generate embeddings for the document chunks.",
                status_code=502,
            ) from exc
        except ValueError as exc:
            logger.exception("rag_embedding_response_invalid", extra={"provider": "gemini"})
            raise AppException(
                code="RAG_EMBEDDING_FAILED",
                message="Embedding provider returned an invalid response.",
                status_code=502,
            ) from exc

        embeddings = data.get("embeddings") or []
        vectors: list[list[float]] = []

        for embedding in embeddings:
            values = embedding.get("values") if isinstance(embedding, dict) else None
            if not values:
                logger.error("rag_embedding_missing_values", extra={"provider": "gemini"})
                raise AppException(
                    code="RAG_EMBEDDING_FAILED",
                    message="Embedding provider returned an incomplete response.",
                    status_code=502,
                )

            vector = [float(value) for value in values]
            if self.normalize_embeddings:
                vector = _normalize_vector(vector)
            vectors.append(vector)

        if len(vectors) != len(clean_texts):
            logger.error(
                "rag_embedding_count_mismatch",
                extra={
                    "provider": "gemini",
                    "requested": len(clean_texts),
                    "received": len(vectors),
                },
            )
            raise AppException(
                code="RAG_EMBEDDING_FAILED",
                message="Embedding provider returned an unexpected number of embeddings.",
                status_code=502,
            )

        return vectors


@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    """Return the configured embedding provider client."""

    settings = get_settings()
    if settings.rag_embedding_provider == "gemini":
        return GeminiEmbeddingClient.from_settings()

    raise AppException(
        code="RAG_EMBEDDING_CONFIG_ERROR",
        message=f"Unsupported RAG embedding provider: {settings.rag_embedding_provider}",
        status_code=500,
    )


def _normalize_vector(values: Sequence[float]) -> list[float]:
    """L2-normalize an embedding vector for cosine-similarity search."""

    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude == 0:
        return [float(value) for value in values]
    return [float(value) / magnitude for value in values]
