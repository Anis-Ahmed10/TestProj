"""Unit tests for configuration loading and validation."""

import pytest

from app.core.config import Settings, get_settings


def test_settings_cors_origins_empty_cloudfront():
    settings = Settings(cloudfront_url="")
    assert settings.cors_origins == ["http://localhost:3000"]


def test_settings_cors_origins_with_cloudfront():
    settings = Settings(cloudfront_url="https://d123.cloudfront.net")
    assert "https://d123.cloudfront.net" in settings.cors_origins


def test_normalize_log_level():
    assert Settings.normalize_log_level("debug") == "DEBUG"
    with pytest.raises(ValueError, match="log_level must be one of"):
        Settings.normalize_log_level("invalid")


def test_normalize_rag_embedding_provider():
    assert Settings.normalize_rag_embedding_provider(" GemIni ") == "gemini"
    with pytest.raises(ValueError, match="rag_embedding_provider must be one of"):
        Settings.normalize_rag_embedding_provider("openai")


def test_strip_required_text_fields():
    assert Settings.strip_required_text_fields(" text ") == "text"
    with pytest.raises(ValueError, match="Field must not be empty"):
        Settings.strip_required_text_fields("   ")


def test_normalize_rag_embedding_task_type():
    assert Settings.normalize_rag_embedding_task_type(" retrieval_query ") == "RETRIEVAL_QUERY"
    with pytest.raises(ValueError, match="must not be empty"):
        Settings.normalize_rag_embedding_task_type("   ")


def test_normalize_rag_embedding_task_type_invalid():
    with pytest.raises(ValueError, match="Invalid rag_embedding_task_type provided."):
        Settings.normalize_rag_embedding_task_type("INVALID_TASK")


def test_get_settings_caching():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_settings_cors_origins_whitespace_cloudfront():
    settings = Settings(cloudfront_url="   ")
    assert settings.cors_origins == ["http://localhost:3000"]
