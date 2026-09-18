from __future__ import annotations

from functools import lru_cache

from markitdown import MarkItDown


@lru_cache(maxsize=1)
def get_markdown_converter() -> MarkItDown:
    """Return the shared MarkItDown document converter."""

    return MarkItDown(enable_plugins=False)
