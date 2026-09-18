"""Unit tests for the RAG ingestion pipeline helpers."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.services.rag.helpers import (
    _batched_texts,
    _is_heading_only_node,
    build_chunk_payloads,
    derive_document_name,
    download_to_temp_file,
    extract_text_content,
    get_markdown_converter,
    get_node_parser,
    get_sentence_splitter,
    normalize_optional_text,
    source_for_logs,
    split_markdown,
    validate_s3_url,
)


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all lru_cache wrapped functions before each test to prevent test bleeding."""
    get_settings.cache_clear()
    get_markdown_converter.cache_clear()
    get_node_parser.cache_clear()
    get_sentence_splitter.cache_clear()
    yield


def test_normalize_optional_text():
    assert normalize_optional_text(None) is None
    assert normalize_optional_text("   ") is None
    assert normalize_optional_text(" txt ") == "txt"


def test_validate_s3_url():
    with pytest.raises(AppException, match="Provide a valid"):
        validate_s3_url(None)
    with pytest.raises(AppException, match="Provide a valid"):
        validate_s3_url("   ")
    with pytest.raises(AppException, match="s3_url must be"):
        validate_s3_url("s3://a")


def test_validate_s3_url_success():
    url = "https://example.com/file.txt"
    assert validate_s3_url(url) == url


def test_derive_document_name():
    assert (
        derive_document_name(document_name="explicit.txt", s3_url="s3://b/f.txt") == "explicit.txt"
    )
    assert derive_document_name(document_name=None, s3_url="s3://b/f.txt") == "f.txt"
    with pytest.raises(AppException, match="Unable to determine a document name"):
        derive_document_name(document_name=None, s3_url="s3://b/")


def test_source_for_logs():
    assert source_for_logs("s3://b/f.txt") == "f.txt"
    assert source_for_logs("s3://b/") == "<remote-document>"


@patch("socket.getaddrinfo")
@patch("app.services.rag.helpers.httpx.Client")
@patch("app.services.rag.helpers.tempfile.mkstemp")
@patch("app.services.rag.helpers.os.fdopen")
def test_download_to_temp_file_success(
    mock_fdopen,
    mock_mkstemp,
    mock_client_cls,
    mock_getaddrinfo,
):
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("8.8.8.8", 443))]
    mock_mkstemp.return_value = (1, "/tmp/t.txt")

    # Mock httpx streaming response
    mock_stream_resp = MagicMock()
    mock_stream_resp.iter_bytes.return_value = [b"data"]
    mock_stream_resp.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.stream.return_value.__enter__.return_value = mock_stream_resp
    mock_client_cls.return_value.__enter__.return_value = mock_client

    mock_file = MagicMock()
    mock_fdopen.return_value.__enter__.return_value = mock_file

    path = download_to_temp_file("https://example.com/b/f.txt")
    assert path == Path("/tmp/t.txt")
    mock_file.write.assert_called_with(b"data")


@patch("socket.getaddrinfo")
@patch("app.services.rag.helpers.httpx.Client")
def test_download_to_temp_file_failure(
    mock_client_cls,
    mock_getaddrinfo,
):
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("8.8.8.8", 443))]
    # Simulate httpx failing before streaming body is read.
    mock_client = MagicMock()
    mock_stream_cm = MagicMock()
    mock_stream_cm.__enter__.side_effect = Exception("boom")
    mock_client.stream.return_value = mock_stream_cm
    mock_client_cls.return_value.__enter__.return_value = mock_client

    with pytest.raises(AppException, match="Unable to download"):
        download_to_temp_file("https://example.com/b/f.txt")


def test_get_markdown_converter():
    assert get_markdown_converter() is not None


def test_split_markdown_by_headings():
    chunks = split_markdown("intro\n\n# One\nbody one\n\n## Two\nbody two")
    assert [c.strip() for c in chunks] == [
        "intro",
        "# One\nbody one",
        "## Two\nbody two",
    ]


def test_split_markdown_plain_text_breaks_on_sentences():
    chunks = split_markdown("The quick brown fox jumps over the lazy dog. " * 250)

    assert len(chunks) > 1
    assert all(chunk.rstrip().endswith("dog.") for chunk in chunks)
    assert all(len(chunk) < 2000 for chunk in chunks)


def test_split_markdown_empty():
    assert split_markdown("") == []


def test_split_markdown_small_table_stays_one_chunk():
    header = "| TestID | Scenario |"
    divider = "| --- | --- |"
    rows = [f"| TC-{index:02d} | scenario {index} |" for index in range(4)]
    markdown = "\n".join([header, divider, *rows])

    chunks = split_markdown(markdown)

    assert chunks == [markdown]


def test_split_markdown_large_table_splits_with_header_repeated():
    header = "| TestID | Scenario |"
    divider = "| --- | --- |"
    rows = [
        f"| TC-{index:04d} | scenario number {index} description text |" for index in range(200)
    ]
    markdown = "\n".join([header, divider, *rows])

    chunks = split_markdown(markdown)

    assert len(chunks) > 1
    for chunk in chunks:
        lines = chunk.split("\n")
        assert lines[0] == header
        assert lines[1] == divider

    packed_rows = [line for chunk in chunks for line in chunk.split("\n")[2:]]
    assert packed_rows == rows


def test_split_markdown_table_fragment_with_zero_data_rows_falls_through():
    header = "| A | B |"
    divider = "| --- | --- |"
    markdown = f"{header}\n{divider}\nSome following prose that is not a table row."

    chunks = split_markdown(markdown)

    assert f"{header}\n{divider}" not in chunks
    assert not any(
        chunk.split("\n")[:2] == [header, divider] and len(chunk.split("\n")) == 2
        for chunk in chunks
    )


def test_split_markdown_mixed_prose_and_table_in_one_section():
    header = "| Col A | Col B |"
    divider = "| --- | --- |"
    markdown = (
        "## Overview\n"
        "Some intro text about the sheet.\n\n"
        f"{header}\n{divider}\n"
        "| a1 | b1 |\n"
        "| a2 | b2 |\n\n"
        "Trailing note after the table."
    )

    chunks = split_markdown(markdown)

    assert any("Some intro text about the sheet." in chunk for chunk in chunks)
    assert any("Trailing note after the table." in chunk for chunk in chunks)
    table_chunks = [
        chunk for chunk in chunks if chunk.startswith(f"## Overview\n{header}\n{divider}")
    ]
    assert len(table_chunks) == 1
    assert "| a1 | b1 |" in table_chunks[0]
    assert "| a2 | b2 |" in table_chunks[0]
    assert chunks.count("## Overview") == 0


def test_split_markdown_heading_directly_before_table_has_no_bare_chunk():
    """A heading, then only a blank line, then a table must not emit a heading-only chunk."""

    markdown = "## Overview\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n## Next\nBody text."

    chunks = split_markdown(markdown)

    assert "## Overview" not in chunks
    assert chunks == [
        "## Overview\n| A | B |\n| --- | --- |\n| 1 | 2 |",
        "## Next\nBody text.",
    ]


def test_split_markdown_adjacent_tables_no_blank_line():
    markdown = (
        "| H1 | H2 |\n"
        "| --- | --- |\n"
        "| r1 | r2 |\n"
        "| H3 | H4 |\n"
        "| --- | --- |\n"
        "| r3 | r4 |"
    )

    chunks = split_markdown(markdown)

    assert len(chunks) == 2
    assert chunks[0] == "| H1 | H2 |\n| --- | --- |\n| r1 | r2 |"
    assert chunks[1] == "| H3 | H4 |\n| --- | --- |\n| r3 | r4 |"


def test_split_markdown_blank_data_row_does_not_break_table():
    """A blank row (markitdown's shape for an empty cell row) must not look like a divider.

    A row of empty cells like `| | | |` matches the outer `|...|` shape of
    a real divider row unless the divider pattern requires an actual dash,
    which would otherwise cut the table run short and promote a data row
    to the header.
    """

    header = "| Region | Q1 | Q2 |"
    divider = "| --- | --- | --- |"
    markdown = (
        f"{header}\n{divider}\n"
        "| North | 10 | 12 |\n"
        "| | | |\n"
        "| South | 20 | 22 |\n"
        "| East | 30 | 32 |"
    )

    chunks = split_markdown(markdown)

    assert len(chunks) == 1
    lines = chunks[0].split("\n")
    assert lines[0] == header
    assert lines[1] == divider
    assert lines[2] == "| North | 10 | 12 |"


def test_is_heading_only_node():
    assert _is_heading_only_node(["# H"]) is True
    assert _is_heading_only_node(["# H", "body"]) is False
    assert _is_heading_only_node(["# H", ""]) is True
    assert _is_heading_only_node(["body"]) is False


def test_split_markdown_orphaned_heading_folds_into_next_section():
    markdown = (
        "# 4. Scope\n\n"
        "## 4.1 In Scope\n"
        "* Requirement ingestion\n"
        "* User story and epic management\n\n"
        "## 4.2 Out of Scope\n"
        "* Source-code deployment"
    )

    chunks = split_markdown(markdown)

    assert [chunk.strip() for chunk in chunks] == [
        "# 4. Scope\n## 4.1 In Scope\n* Requirement ingestion\n* User story and epic management",
        "## 4.2 Out of Scope\n* Source-code deployment",
    ]
    assert "# 4. Scope" not in chunks


def test_split_markdown_orphaned_heading_deeper_level():
    markdown = "## Section A\n\n### Sub A.1\n* item one\n* item two"

    chunks = split_markdown(markdown)

    assert [chunk.strip() for chunk in chunks] == [
        "## Section A\n### Sub A.1\n* item one\n* item two",
    ]
    assert "## Section A" not in chunks


def test_split_markdown_multiple_consecutive_orphaned_headings():
    markdown = "# 1. Top\n\n## 1.1 Mid\n\n### 1.1.1 Deep\nActual body text here."

    chunks = split_markdown(markdown)

    assert [chunk.strip() for chunk in chunks] == [
        "# 1. Top\n## 1.1 Mid\n### 1.1.1 Deep\nActual body text here.",
    ]


def test_split_markdown_orphaned_heading_before_table():
    markdown = (
        "# 5. Data Model\n\n"
        "## 5.1 Entities\n"
        "| ID | Name |\n"
        "| --- | --- |\n"
        "| E1 | Story |\n"
        "| E2 | Epic |"
    )

    chunks = split_markdown(markdown)

    assert len(chunks) == 1
    lines = chunks[0].split("\n")
    assert lines[0] == "# 5. Data Model"
    assert lines[1] == "## 5.1 Entities"
    assert lines[2] == "| ID | Name |"
    assert lines[3] == "| --- | --- |"
    assert "| E1 | Story |" in chunks[0]
    assert "| E2 | Epic |" in chunks[0]


def test_split_markdown_trailing_orphaned_headings_not_dropped():
    markdown = "Some real content here.\n\n# Trailing Heading\n\n## Another Trailing"

    chunks = split_markdown(markdown)

    assert any("Some real content here." in chunk for chunk in chunks)
    assert chunks[-1] == "# Trailing Heading\n## Another Trailing"


def test_batched_texts():
    assert _batched_texts(["a", "b", "c"], 2) == [["a", "b"], ["c"]]


@patch("app.services.rag.helpers.extract_word_markdown")
def test_extract_text_content_success(mock_extract_word):
    mock_extract_word.return_value = "# Title\nbody"
    assert extract_text_content(Path("test.docx")) == "# Title\nbody"


@patch("app.services.rag.helpers.extract_word_markdown")
def test_extract_text_content_conversion_failure(mock_extract_word):
    mock_extract_word.side_effect = Exception("err")
    with pytest.raises(AppException, match="Failed to extract text from the document."):
        extract_text_content(Path("test.docx"))


@patch("app.services.rag.helpers.extract_pdf_markdown")
def test_extract_text_content_pdf_uses_font_aware_extraction(mock_pdf_extract):
    """markitdown's PDF table reconstruction corrupts wrapped table cells; bypass it."""
    mock_pdf_extract.return_value = "# Title\nbody"
    assert extract_text_content(Path("test.pdf")) == "# Title\nbody"
    mock_pdf_extract.assert_called_once_with(Path("test.pdf"))


@patch("app.services.rag.helpers.extract_pdf_markdown")
def test_extract_text_content_pdf_failure(mock_pdf_extract):
    mock_pdf_extract.side_effect = Exception("err")
    with pytest.raises(AppException, match="Failed to extract text from the document."):
        extract_text_content(Path("test.pdf"))


@patch("app.services.rag.helpers.extract_word_markdown")
def test_extract_text_content_collapses_whitespace_runs(mock_extract_word):
    mock_extract_word.return_value = "System    Context    Document\nnormal text"
    assert extract_text_content(Path("test.docx")) == "System Context Document\nnormal text"


@patch("app.services.rag.helpers.get_settings")
@patch("app.services.rag.helpers.split_markdown")
@patch("app.services.rag.helpers.get_embedding_client")
def test_build_chunk_payloads_success(mock_get_client, mock_split, mock_get_settings):
    mock_settings = MagicMock()
    mock_settings.rag_embedding_batch_size = 10
    mock_get_settings.return_value = mock_settings
    mock_split.return_value = ["chunk"]
    mock_client = MagicMock()
    mock_client.embed_texts.return_value = [[0.1, 0.2]]
    mock_get_client.return_value = mock_client

    assert build_chunk_payloads("content") == [("chunk", [0.1, 0.2])]


@patch("app.services.rag.helpers.split_markdown")
def test_build_chunk_payloads_no_nodes(mock_split):
    mock_split.return_value = []
    with pytest.raises(AppException, match="Unable to chunk document content."):
        build_chunk_payloads("content")


@patch("app.services.rag.helpers.split_markdown")
def test_build_chunk_payloads_empty_chunks(mock_split):
    mock_split.return_value = ["   "]
    with pytest.raises(AppException, match="No valid chunks were produced"):
        build_chunk_payloads("content")


@patch("app.services.rag.helpers.get_settings")
@patch("app.services.rag.helpers.split_markdown")
@patch("app.services.rag.helpers.get_embedding_client")
def test_build_chunk_payloads_batch_mismatch(mock_get_client, mock_split, mock_get_settings):
    mock_settings = MagicMock()
    mock_settings.rag_embedding_batch_size = 10
    mock_get_settings.return_value = mock_settings
    mock_split.return_value = ["chunk"]
    mock_client = MagicMock()
    mock_client.embed_texts.return_value = (
        []
    )  # Returns empty, causing mismatch with batch length of 1
    mock_get_client.return_value = mock_client
    with pytest.raises(AppException, match="unexpected number of embeddings"):
        build_chunk_payloads("content")


@patch("socket.getaddrinfo")
@patch("app.services.rag.helpers.httpx.Client")
@patch("app.services.rag.helpers.tempfile.mkstemp")
@patch("app.services.rag.helpers.os.fdopen")
def test_download_to_temp_file_empty_chunk(
    mock_fdopen,
    mock_mkstemp,
    mock_client_cls,
    mock_getaddrinfo,
):
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("8.8.8.8", 443))]
    mock_mkstemp.return_value = (1, "/tmp/t.txt")

    mock_stream_resp = MagicMock()
    mock_stream_resp.iter_bytes.return_value = [
        b"data",
        b"",
    ]
    mock_stream_resp.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.stream.return_value.__enter__.return_value = mock_stream_resp
    mock_client_cls.return_value.__enter__.return_value = mock_client

    mock_file = MagicMock()
    mock_fdopen.return_value.__enter__.return_value = mock_file

    path = download_to_temp_file("https://example.com/b/f.txt")
    assert path == Path("/tmp/t.txt")
    mock_file.write.assert_called_once_with(b"data")


@patch("app.services.rag.helpers.get_markdown_converter")
def test_extract_text_content_txt_success(mock_get_converter):
    mock_get_converter.return_value.convert.return_value.markdown = "txt content"
    assert extract_text_content(Path("test.txt")) == "txt content"


def test_extract_text_content_unsupported_format():
    with pytest.raises(AppException, match="Unsupported file format: .jpg"):
        extract_text_content(Path("test.jpg"))


@patch("app.services.rag.helpers.get_settings")
@patch("app.services.rag.helpers.get_embedding_client")
@patch("app.services.rag.helpers._batched_texts")
@patch("app.services.rag.helpers.split_markdown")
def test_build_chunk_payloads_empty_payloads(
    mock_split, mock_batched_texts, mock_get_client, mock_get_settings
):
    mock_split.return_value = ["chunk"]
    mock_batched_texts.return_value = (
        []
    )  # Force empty batches so loop body doesn't append payloads
    mock_settings = MagicMock()
    mock_settings.rag_embedding_batch_size = 10
    mock_get_settings.return_value = mock_settings
    mock_get_client.return_value = MagicMock()
    with pytest.raises(AppException, match="No valid chunks were produced from the document"):
        build_chunk_payloads("content")


def test_download_to_temp_file_non_https():
    with pytest.raises(AppException, match="URL must use HTTPS"):
        download_to_temp_file("http://example.com/file.txt")


def test_download_to_temp_file_no_hostname():
    with pytest.raises(AppException, match="URL must have a valid hostname"):
        download_to_temp_file("https://:80/file.txt")


@patch("socket.getaddrinfo")
def test_download_to_temp_file_resolve_error(mock_getaddrinfo):
    import socket

    mock_getaddrinfo.side_effect = socket.gaierror("err")
    with pytest.raises(AppException, match="Unable to resolve URL hostname"):
        download_to_temp_file("https://unknown-domain.com/file.txt")


@patch("socket.getaddrinfo")
def test_download_to_temp_file_private_ip(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [(None, None, None, None, ("127.0.0.1", 0))]
    with pytest.raises(AppException, match="Refusing to download from a private network address"):
        download_to_temp_file("https://localhost/file.txt")


@patch("socket.getaddrinfo")
@patch("app.services.rag.helpers.httpx.Client")
@patch("app.services.rag.helpers.tempfile.mkstemp")
@patch("app.services.rag.helpers.os.fdopen")
def test_download_to_temp_file_httperror_with_tmp_path(
    mock_fdopen, mock_mkstemp, mock_client_cls, mock_getaddrinfo
):
    mock_getaddrinfo.return_value = [(None, None, None, None, ("8.8.8.8", 0))]

    mock_path = MagicMock()
    mock_path_cls = MagicMock(return_value=mock_path)
    mock_mkstemp.return_value = (1, "/tmp/t.txt")

    mock_stream_resp = MagicMock()
    mock_stream_resp.iter_bytes.side_effect = httpx.HTTPError("stream error")
    mock_stream_resp.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.stream.return_value.__enter__.return_value = mock_stream_resp
    mock_client_cls.return_value.__enter__.return_value = mock_client

    mock_file = MagicMock()
    mock_fdopen.return_value.__enter__.return_value = mock_file

    with patch("app.services.rag.helpers.Path", mock_path_cls):
        with pytest.raises(AppException, match="Unable to download the provided S3 document."):
            download_to_temp_file("https://example.com/b/f.txt")

    mock_path.unlink.assert_called_once_with(missing_ok=True)


@patch("socket.getaddrinfo")
@patch("app.services.rag.helpers.httpx.Client")
@patch("app.services.rag.helpers.tempfile.mkstemp")
@patch("app.services.rag.helpers.os.fdopen")
def test_download_to_temp_file_general_exception_with_tmp_path(
    mock_fdopen, mock_mkstemp, mock_client_cls, mock_getaddrinfo
):
    mock_getaddrinfo.return_value = [(None, None, None, None, ("8.8.8.8", 0))]

    mock_path = MagicMock()
    mock_path_cls = MagicMock(return_value=mock_path)
    mock_mkstemp.return_value = (1, "/tmp/t.txt")

    mock_stream_resp = MagicMock()
    mock_stream_resp.iter_bytes.side_effect = ValueError("weird error")
    mock_stream_resp.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.stream.return_value.__enter__.return_value = mock_stream_resp
    mock_client_cls.return_value.__enter__.return_value = mock_client

    mock_file = MagicMock()
    mock_fdopen.return_value.__enter__.return_value = mock_file

    with patch("app.services.rag.helpers.Path", mock_path_cls):
        with pytest.raises(AppException, match="Unable to download the provided S3 document."):
            download_to_temp_file("https://example.com/b/f.txt")

    mock_path.unlink.assert_called_once_with(missing_ok=True)


@patch("app.services.rag.helpers.get_settings")
@patch("app.services.rag.helpers.split_markdown")
@patch("app.services.rag.helpers.get_embedding_client")
def test_build_chunk_payloads_dimension_mismatch(mock_get_client, mock_split, mock_get_settings):
    mock_settings = MagicMock()
    mock_settings.rag_embedding_batch_size = 10
    mock_settings.rag_embedding_dimensions = 100
    mock_get_settings.return_value = mock_settings

    mock_split.return_value = ["chunk"]

    mock_client = MagicMock()
    mock_client.embed_texts.return_value = [[0.1, 0.2]]
    mock_get_client.return_value = mock_client

    with pytest.raises(AppException, match="Embedding dimension mismatch"):
        build_chunk_payloads("content")


@patch("app.services.rag.helpers.get_settings")
@patch("app.services.rag.helpers.split_markdown")
@patch("app.services.rag.helpers.get_embedding_client")
def test_build_chunk_payloads_dimension_not_int(mock_get_client, mock_split, mock_get_settings):
    mock_settings = MagicMock()
    mock_settings.rag_embedding_batch_size = 10
    mock_settings.rag_embedding_dimensions = "not-an-int"
    mock_get_settings.return_value = mock_settings

    mock_split.return_value = ["chunk"]

    mock_client = MagicMock()
    mock_client.embed_texts.return_value = [[0.1, 0.2]]
    mock_get_client.return_value = mock_client

    payloads = build_chunk_payloads("content")
    assert payloads == [("chunk", [0.1, 0.2])]


@patch("socket.getaddrinfo")
@patch("app.services.rag.helpers.httpx.Client")
def test_download_to_temp_file_httperror_no_tmp_path(mock_client_cls, mock_getaddrinfo):
    mock_getaddrinfo.return_value = [(None, None, None, None, ("8.8.8.8", 0))]

    mock_stream_resp = MagicMock()
    # Raise the HTTP error immediately, leaving tmp_path as None
    mock_stream_resp.raise_for_status.side_effect = httpx.HTTPError("bad status")

    mock_client = MagicMock()
    mock_client.stream.return_value.__enter__.return_value = mock_stream_resp
    mock_client_cls.return_value.__enter__.return_value = mock_client

    with pytest.raises(AppException, match="Unable to download the provided S3 document."):
        download_to_temp_file("https://example.com/b/f.txt")


def test_validate_s3_url_https_no_netloc():
    with pytest.raises(AppException, match="s3_url must be an HTTPS presigned URL."):
        validate_s3_url("https:///file.txt")


def test_split_markdown_prose_chunks_all_repeat_section_heading():
    """Prose chunks after the first must keep the section heading, like table chunks already do."""

    body = "The system shall validate every request against the configured policy. " * 40
    markdown = f"## Overview\n\n{body}\n\n| A | B |\n| --- | --- |\n| 1 | 2 |"

    chunks = split_markdown(markdown)

    assert len(chunks) > 2
    assert all(chunk.startswith("## Overview") for chunk in chunks)
