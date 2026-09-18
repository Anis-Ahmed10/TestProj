"""Unit tests for the Gemini embedding client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.utils.rag.embedding import GeminiEmbeddingClient, _normalize_vector, get_embedding_client


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear lru_cache wrapped functions before each test to prevent test bleeding."""
    get_settings.cache_clear()
    get_embedding_client.cache_clear()
    yield


@patch("app.utils.rag.embedding.get_settings")
def test_gemini_client_from_settings_no_key(mock_get_settings):
    mock_settings = MagicMock()
    mock_settings.rag_embedding_api_key = ""
    mock_get_settings.return_value = mock_settings
    with pytest.raises(AppException, match="RAG embedding is not configured"):
        GeminiEmbeddingClient.from_settings()


@patch("app.utils.rag.embedding.get_settings")
def test_gemini_client_from_settings_success(mock_get_settings):
    mock_settings = MagicMock()
    mock_settings.rag_embedding_api_key = "key"
    mock_settings.rag_embedding_model_name = "test-model"
    mock_settings.rag_embedding_base_url = "https://example.com"
    mock_settings.rag_embedding_dimensions = 768
    mock_settings.rag_embedding_task_type = "TASK"
    mock_settings.request_timeout_seconds = 10.0
    mock_settings.rag_embedding_normalize = True
    mock_get_settings.return_value = mock_settings
    client = GeminiEmbeddingClient.from_settings()
    assert client.api_key == "key"
    assert client.model_name == "models/test-model"


@patch("app.utils.rag.embedding.get_settings")
def test_gemini_client_from_settings_already_has_models_prefix(mock_get_settings):
    mock_settings = MagicMock()
    mock_settings.rag_embedding_api_key = "key"
    mock_settings.rag_embedding_model_name = "models/existing-model"
    mock_settings.rag_embedding_base_url = "https://example.com"
    mock_settings.rag_embedding_dimensions = 768
    mock_settings.rag_embedding_task_type = "TASK"
    mock_settings.request_timeout_seconds = 10.0
    mock_settings.rag_embedding_normalize = True
    mock_get_settings.return_value = mock_settings
    client = GeminiEmbeddingClient.from_settings()
    assert client.model_name == "models/existing-model"


def test_gemini_embed_texts_empty():
    client = GeminiEmbeddingClient(api_key="key", endpoint="ep", model_name="models/test-model")
    assert client.embed_texts([]) == []

    assert client.embed_texts(["   ", ""]) == []


def test_gemini_embed_texts_success():
    client = GeminiEmbeddingClient(api_key="key", endpoint="ep", model_name="models/m")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"embeddings": [{"values": [0.1, 0.2]}]}

    # Replace the persistent client
    client._client.post = MagicMock(return_value=mock_resp)

    res = client.embed_texts(["text"])
    assert res == [[0.1, 0.2]]


def test_gemini_embed_texts_with_normalization():

    client = GeminiEmbeddingClient(
        api_key="key", endpoint="ep", model_name="models/m", normalize_embeddings=True
    )

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"embeddings": [{"values": [3.0, 4.0]}]}

    client._client.post = MagicMock(return_value=mock_resp)

    res = client.embed_texts(["text"])
    assert res == [[0.6, 0.8]]


def test_gemini_embed_texts_request_exception():

    client = GeminiEmbeddingClient(api_key="key", endpoint="ep", model_name="models/m")

    client._client.post = MagicMock(side_effect=httpx.HTTPError("err"))

    with pytest.raises(AppException, match="Failed to generate embeddings"):
        client.embed_texts(["text"])


def test_gemini_embed_texts_request_exception_no_response():

    client = GeminiEmbeddingClient(api_key="key", endpoint="ep", model_name="models/m")
    # Create an exception without a `.response` attribute to test fallback status_code logic
    client._client.post = MagicMock(side_effect=httpx.HTTPError("Network Error"))

    with pytest.raises(AppException, match="Failed to generate embeddings"):
        client.embed_texts(["text"])


def test_gemini_embed_texts_value_error():

    client = GeminiEmbeddingClient(api_key="key", endpoint="ep", model_name="models/m")
    mock_resp = MagicMock()
    mock_resp.json.side_effect = ValueError("err")

    client._client.post = MagicMock(return_value=mock_resp)

    with pytest.raises(AppException, match="invalid response"):
        client.embed_texts(["text"])


def test_gemini_embed_texts_missing_values():

    client = GeminiEmbeddingClient(api_key="key", endpoint="ep", model_name="models/m")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"embeddings": [{}]}

    client._client.post = MagicMock(return_value=mock_resp)

    with pytest.raises(AppException, match="incomplete response"):
        client.embed_texts(["text"])


def test_gemini_embed_texts_count_mismatch():

    client = GeminiEmbeddingClient(api_key="key", endpoint="ep", model_name="models/m")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"embeddings": [{"values": [0.1]}]}

    client._client.post = MagicMock(return_value=mock_resp)

    with pytest.raises(AppException, match="unexpected number of embeddings"):
        client.embed_texts(["text", "text2"])


def test_normalize_vector():
    assert _normalize_vector([0, 0]) == [0.0, 0.0]
    assert _normalize_vector([3, 4]) == [0.6, 0.8]


@patch("app.utils.rag.embedding.get_settings")
def test_get_embedding_client_unsupported(mock_get_settings):
    mock_settings = MagicMock()
    mock_settings.rag_embedding_provider = "openai"
    mock_get_settings.return_value = mock_settings
    with pytest.raises(AppException, match="Unsupported RAG embedding provider"):
        get_embedding_client()


@patch("app.utils.rag.embedding.get_settings")
@patch("app.utils.rag.embedding.GeminiEmbeddingClient.from_settings")
def test_get_embedding_client_gemini(mock_from_settings, mock_get_settings):

    mock_settings = MagicMock()
    mock_settings.rag_embedding_provider = "gemini"
    mock_get_settings.return_value = mock_settings
    mock_from_settings.return_value = "client"

    assert get_embedding_client() == "client"


def test_gemini_embed_texts_invalid_embedding_type():
    client = GeminiEmbeddingClient(api_key="key", endpoint="ep", model_name="models/m")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"embeddings": ["not-a-dict"]}  # Force instance check to fail
    client._client.post = MagicMock(return_value=mock_resp)

    with pytest.raises(AppException, match="incomplete response"):
        client.embed_texts(["text"])


def test_gemini_embed_texts_empty_embeddings_list():

    client = GeminiEmbeddingClient(api_key="key", endpoint="ep", model_name="models/m")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {}  # Empty dict causes data.get("embeddings") to be None
    client._client.post = MagicMock(return_value=mock_resp)

    with pytest.raises(AppException, match="unexpected number of embeddings"):
        client.embed_texts(["text"])


def test_gemini_embed_texts_request_exception_with_response():
    client = GeminiEmbeddingClient(api_key="key", endpoint="ep", model_name="models/m")
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    err = httpx.HTTPError("server error")
    err.response = mock_resp
    client._client.post = MagicMock(side_effect=err)

    with pytest.raises(AppException, match="Failed to generate embeddings"):
        client.embed_texts(["text"])
