"""Reusable regex-based sensitive data sanitizer."""

from copy import deepcopy
from typing import Any

from app.components.sanitization.models import SanitizationRule, compile_rule
from app.core.exceptions import SanitizationError


class SensitiveDataSanitizer:
    """Sanitize sensitive values before content is sent to AI providers."""

    def __init__(self, rules: list[SanitizationRule] | None = None) -> None:
        self.rules = rules or default_sanitization_rules()

    def sanitize(self, value: Any) -> Any:
        """Return a sanitized copy of nested JSON-like data."""
        try:
            return self._sanitize_value(deepcopy(value))
        except Exception as exc:
            raise SanitizationError() from exc

    def sanitize_text(self, value: str) -> str:
        """Sanitize sensitive values in a text string."""
        sanitized = value
        for rule in self.rules:
            sanitized = rule.pattern.sub(rule.placeholder, sanitized)
        return sanitized

    def _sanitize_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.sanitize_text(value)
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._sanitize_value(item) for item in value)
        if isinstance(value, dict):
            return {
                self._sanitize_value(key): self._sanitize_value(item)
                for key, item in value.items()
            }
        return value


def default_sanitization_rules() -> list[SanitizationRule]:
    """Return ordered regex rules for common sensitive values."""
    return [
        compile_rule(
            "jwt",
            r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
            "[REDACTED_JWT]",
        ),
        compile_rule(
            "password",
            r"(?i)\b(password|passwd|pwd)\s*[:=]\s*['\"]?[^'\"\s,;]+",
            r"\1=[REDACTED_PASSWORD]",
        ),
        compile_rule(
            "api_key",
            r"(?i)\b(api[_-]?key|apikey)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}",
            r"\1=[REDACTED_API_KEY]",
        ),
        compile_rule(
            "access_token",
            r"(?i)\b(access[_-]?token|bearer)\s*[:= ]\s*['\"]?[A-Za-z0-9._\-]{12,}",
            r"\1=[REDACTED_ACCESS_TOKEN]",
        ),
        compile_rule(
            "secret",
            r"(?i)\b(secret|client[_-]?secret)\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{8,}",
            r"\1=[REDACTED_SECRET]",
        ),
        compile_rule(
            "email",
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            "[REDACTED_EMAIL]",
        ),
        compile_rule(
            "url",
            r"\bhttps?://[^\s,;]+",
            "[REDACTED_URL]",
        ),
        compile_rule(
            "ip_address",
            r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
            "[REDACTED_IP]",
        ),
        compile_rule(
            "phone_number",
            r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b",
            "[REDACTED_PHONE]",
        ),
        compile_rule(
            "client_name",
            r"(?i)\b(client[_ -]?name|company|customer)\s*[:=]\s*['\"]?[A-Za-z0-9 .&_-]{2,}",
            r"\1=[REDACTED_CLIENT_NAME]",
        ),
    ]
