from __future__ import annotations

import re
from pathlib import Path

from app.utils.rag.markitdown_converter import get_markdown_converter

_TABLE_ROW_PATTERN = re.compile(r"^\|.*\|\s*$")

_TABLE_DIVIDER_PATTERN = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+\s*$")

_BLANK_ROW_PATTERN = re.compile(r"^\|(?:\s*\|)+$")


def extract_word_markdown(source_path: Path) -> str:
    """Convert a Word document to Markdown with usable table headers."""

    markdown = get_markdown_converter().convert(source_path).markdown
    return promote_blank_table_headers(markdown)


def promote_blank_table_headers(markdown: str) -> str:
    """Replace a table's blank header row with the first data row.

    Word tables convert with an empty header row and the real column names as
    the first body row, which would strand every later chunk without them.
    """

    lines = markdown.split("\n")
    promoted: list[str] = []
    index = 0

    while index < len(lines):
        if (
            index + 2 < len(lines)
            and _BLANK_ROW_PATTERN.match(lines[index])
            and _TABLE_DIVIDER_PATTERN.match(lines[index + 1])
            and _TABLE_ROW_PATTERN.match(lines[index + 2])
        ):
            promoted.extend([lines[index + 2], lines[index + 1]])
            index += 3
        else:
            promoted.append(lines[index])
            index += 1

    return "\n".join(promoted)
