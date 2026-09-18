from __future__ import annotations


def normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional text inputs."""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
