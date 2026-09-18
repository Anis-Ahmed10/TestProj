"""Unit tests for Word document extraction."""

from pathlib import Path
from unittest.mock import patch

from app.services.rag.helpers import split_markdown
from app.utils.rag.word import extract_word_markdown, promote_blank_table_headers


def test_promote_blank_table_headers_uses_first_data_row():
    """Word tables convert with a blank header row and the real names one row down."""

    markdown = "\n".join(
        [
            "| | | |",
            "| --- | --- | --- |",
            "| ID | Requirement | Description |",
            "| FR-001 | Import | Import requirements from source |",
        ]
    )

    promoted = promote_blank_table_headers(markdown)

    assert promoted.split("\n") == [
        "| ID | Requirement | Description |",
        "| --- | --- | --- |",
        "| FR-001 | Import | Import requirements from source |",
    ]


def test_promote_blank_table_headers_leaves_real_headers_alone():
    markdown = "\n".join(
        [
            "| ID | Requirement |",
            "| --- | --- |",
            "| FR-001 | Import |",
        ]
    )

    assert promote_blank_table_headers(markdown) == markdown


def test_promote_blank_table_headers_ignores_blank_row_without_table():
    markdown = "Some prose.\n| | | |\nMore prose."

    assert promote_blank_table_headers(markdown) == markdown


def test_word_table_chunks_carry_real_column_names():
    """Every chunk of a split Word table must repeat the real header, not the blank row."""

    header_lines = ["| | | |", "| --- | --- | --- |", "| ID | Requirement | Description |"]
    rows = [
        f"| FR-{index:03d} | Requirement {index} | "
        f"Some longer description text for requirement number {index} that adds enough "
        "length to force a split eventually. |"
        for index in range(30)
    ]

    promoted = promote_blank_table_headers("\n".join(header_lines + rows))
    chunks = split_markdown(promoted)

    assert len(chunks) > 1
    for chunk in chunks:
        lines = chunk.split("\n")
        assert lines[0] == "| ID | Requirement | Description |"
        assert lines[1] == "| --- | --- | --- |"

    packed_rows = [line for chunk in chunks for line in chunk.split("\n")[2:]]
    assert packed_rows == rows


@patch("app.utils.rag.word.get_markdown_converter")
def test_extract_word_markdown_promotes_headers(mock_get_converter):
    mock_get_converter.return_value.convert.return_value.markdown = (
        "| | |\n| --- | --- |\n| ID | Name |\n| 1 | Story |"
    )

    assert extract_word_markdown(Path("test.docx")) == (
        "| ID | Name |\n| --- | --- |\n| 1 | Story |"
    )
