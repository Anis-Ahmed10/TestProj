"""Sanitization rule models."""

import re
from dataclasses import dataclass
from typing import Pattern


@dataclass(frozen=True)
class SanitizationRule:
    """Regex replacement rule for sensitive data."""

    name: str
    pattern: Pattern[str]
    placeholder: str


def compile_rule(name: str, pattern: str, placeholder: str, flags: int = 0) -> SanitizationRule:
    """Compile a sanitization rule."""
    return SanitizationRule(
        name=name,
        pattern=re.compile(pattern, flags),
        placeholder=placeholder,
    )
