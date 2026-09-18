"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the backend."""

    cloudfront_url: str = ""

    # AWS / S3 (credentials come from the Lambda execution role)
    aws_region: str = "eu-west-1"
    s3_bucket_name: str = ""

    # AWS SES (credentials come from the Lambda execution role)
    ses_sender_email: str = ""

    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""

    jira_token_encryption_key: str = ""
    jira_test_case_issue_type_id: str = "10012"
    db_host: Optional[str] = None
    db_port: int = 5432
    db_name: Optional[str] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    db_sslmode: str = "require"
    db_sslrootcert: Optional[str] = None

    app_name: str = "AI QA Engineering Backend"
    app_version: str = "1.0.0"
    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"

    request_timeout_seconds: float = Field(default=30.0, gt=0)
    rag_download_timeout_seconds: float = Field(default=60.0, gt=0)

    max_input_bytes: int = Field(default=128_000, ge=1_024)
    rag_embedding_provider: str = "gemini"
    rag_embedding_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("RAG_EMBEDDING_API_KEY", "GEMINI_API_KEY"),
    )
    rag_embedding_model_name: str = "gemini-embedding-001"
    rag_embedding_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    rag_embedding_dimensions: int = Field(default=768, ge=1)
    rag_embedding_task_type: str = "RETRIEVAL_DOCUMENT"
    rag_embedding_batch_size: int = Field(default=16, ge=1)
    rag_embedding_normalize: bool = True

    log_level: str = "INFO"
    log_file_path: Path = Path("logs/app.log")
    enable_file_logging: bool = True

    request_id_header: str = "X-Request-ID"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        origins = ["http://localhost:3000"]
        if self.cloudfront_url and self.cloudfront_url.strip():
            origins.append(self.cloudfront_url)
        return origins

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Normalize supported logging levels."""
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            msg = f"log_level must be one of: {', '.join(sorted(allowed))}"
            raise ValueError(msg)
        return normalized

    @field_validator("rag_embedding_provider")
    @classmethod
    def normalize_rag_embedding_provider(cls, value: str) -> str:
        """Normalize the configured embedding provider name."""

        normalized = value.strip().lower()
        allowed = {"gemini"}
        if normalized not in allowed:
            msg = f"rag_embedding_provider must be one of: {', '.join(sorted(allowed))}"
            raise ValueError(msg)
        return normalized

    @field_validator("rag_embedding_model_name", "rag_embedding_base_url")
    @classmethod
    def strip_required_text_fields(cls, value: str) -> str:
        """Normalize required text settings."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("Field must not be empty")
        return normalized

    @field_validator("rag_embedding_task_type")
    @classmethod
    def normalize_rag_embedding_task_type(cls, value: str) -> str:
        """Validate Gemini task types for consistent API requests."""

        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Task type must not be empty")

        gemini_task_types = {
            "RETRIEVAL_DOCUMENT",
            "RETRIEVAL_QUERY",
            "SEMANTIC_SIMILARITY",
            "CLASSIFICATION",
            "CLUSTERING",
        }
        if normalized not in gemini_task_types:
            raise ValueError("Invalid rag_embedding_task_type provided.")
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


app_settings = get_settings()
