"""Helper utilities for the RAG ingestion pipeline."""

from __future__ import annotations

import os
import re
import tempfile
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Sequence
from urllib.parse import urlparse

import httpx
from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.utils.rag.embedding import get_embedding_client
from app.utils.rag.markitdown_converter import get_markdown_converter
from app.utils.rag.pdf import extract_pdf_markdown
from app.utils.rag.text import normalize_optional_text
from app.utils.rag.word import extract_word_markdown

SUPPORTED_EXTENSIONS = frozenset(
    {
        ".csv",
        ".docx",
        ".md",
        ".pdf",
        ".txt",
        ".xls",
        ".xlsx",
    }
)

CHUNK_SIZE_TOKENS = 250

CHUNK_OVERLAP_TOKENS = 20

MIN_TABLE_DATA_ROWS = 1

TABLE_CHUNK_MAX_CHARS = 1200

_WHITESPACE_RUN_PATTERN = re.compile(r"(?<=\S)[ \t]{2,}")

_TABLE_ROW_PATTERN = re.compile(r"^\|.*\|\s*$")

_TABLE_DIVIDER_PATTERN = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+\s*$")

_HEADING_PATTERN = re.compile(r"^#{1,6}\s")


def validate_s3_url(s3_url: str | None) -> str:
    """Validate an HTTPS presigned S3 URL."""

    normalized = normalize_optional_text(s3_url)
    if not normalized:
        raise AppException(
            code="RAG_INVALID_INPUT",
            message="Provide a valid presigned S3 URL.",
            status_code=400,
        )

    parsed = urlparse(normalized)
    if parsed.scheme != "https" or not parsed.netloc:
        raise AppException(
            code="RAG_INVALID_INPUT",
            message="s3_url must be an HTTPS presigned URL.",
            status_code=400,
        )

    return normalized


def derive_document_name(
    *,
    document_name: str | None,
    s3_url: str,
) -> str:
    """Determine the persisted document name."""

    explicit_name = normalize_optional_text(document_name)
    if explicit_name:
        return explicit_name

    parsed_url = urlparse(s3_url)
    candidate = PurePosixPath(parsed_url.path).name

    if candidate:
        return candidate

    raise AppException(
        code="RAG_INVALID_INPUT",
        message="Unable to determine a document name from the provided source.",
        status_code=400,
    )


def source_for_logs(s3_url: str) -> str:
    """Return a non-sensitive source description for logs."""

    return PurePosixPath(urlparse(s3_url).path).name or "<remote-document>"


def download_to_temp_file(url: str) -> Path:
    """Download an S3 URL into a temporary file.

    Ensures we don't leave temp files behind on partial download failures.
    Also blocks private/loopback/link-local targets to mitigate SSRF.
    """

    import ipaddress
    import socket
    from urllib.parse import urlparse as _urlparse

    settings = get_settings()

    parsed = _urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        # Keep backward-compatible behavior for unit tests that pass non-HTTPS URLs.
        # Production callers are expected to validate via `validate_s3_url` first.
        raise AppException(
            code="RAG_INVALID_INPUT",
            message="URL must use HTTPS.",
            status_code=400,
        )

    hostname = parsed.hostname
    if not hostname:
        raise AppException(
            code="RAG_INVALID_INPUT",
            message="URL must have a valid hostname.",
            status_code=400,
        )

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise AppException(
            code="RAG_INVALID_INPUT",
            message="Unable to resolve URL hostname.",
            status_code=400,
        ) from exc

    for family, _, _, _, sockaddr in addr_infos:
        ip = sockaddr[0]
        ip_obj = ipaddress.ip_address(ip)
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
            or ip_obj.is_reserved
        ):
            raise AppException(
                code="RAG_INVALID_INPUT",
                message="Refusing to download from a private network address.",
                status_code=400,
            )

    suffix = PurePosixPath(parsed.path).suffix

    tmp_path: Path | None = None
    try:

        with httpx.Client(timeout=settings.rag_download_timeout_seconds) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()

                fd, raw_path = tempfile.mkstemp(suffix=suffix)
                tmp_path = Path(raw_path)
                with os.fdopen(fd, "wb") as handle:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)

                return tmp_path
    except httpx.HTTPError as exc:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise AppException(
            code="RAG_DOWNLOAD_FAILED",
            message="Unable to download the provided S3 document.",
            status_code=400,
        ) from exc

    except Exception as exc:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise AppException(
            code="RAG_DOWNLOAD_FAILED",
            message="Unable to download the provided S3 document.",
            status_code=400,
        ) from exc


@lru_cache(maxsize=1)
def get_node_parser() -> MarkdownNodeParser:
    """Return the structure-aware Markdown section parser."""

    return MarkdownNodeParser()


@lru_cache(maxsize=1)
def get_sentence_splitter() -> SentenceSplitter:
    """Return the splitter that enforces chunk size on sentence boundaries."""

    return SentenceSplitter(
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
        paragraph_separator="\n\n",
    )


def split_markdown(markdown: str) -> list[str]:
    """Chunk Markdown by heading structure, then by sentence or table row within each section."""

    chunks: list[str] = []
    pending_heading_lines: list[str] = []
    for node in get_node_parser()([Document(text=markdown)]):
        lines = node.get_content().split("\n")
        if _is_heading_only_node(lines):
            pending_heading_lines.append(lines[0])
            continue
        if pending_heading_lines:
            lines = pending_heading_lines + lines
            pending_heading_lines = []
        chunks.extend(_split_section("\n".join(lines)))

    if pending_heading_lines:
        chunks.append("\n".join(pending_heading_lines))

    return chunks


def _is_heading_only_node(lines: list[str]) -> bool:
    """Return True if a parsed section is a heading line with no body content."""

    return (
        bool(lines)
        and _HEADING_PATTERN.match(lines[0]) is not None
        and not any(line.strip() for line in lines[1:])
    )


def _prose_chunks(heading: list[str], raw_lines: list[str]) -> list[str]:
    """Sentence-split prose, repeating the section heading on every resulting chunk.

    `SentenceSplitter` can split one block of prose into several chunks; the
    heading must be re-applied to each one (as `_pack_table_rows` already
    does for table chunks) rather than prepended once to the raw text, or
    every chunk after the first loses its section context.
    """

    bodies = [
        body for body in get_sentence_splitter().split_text("\n".join(raw_lines)) if body.strip()
    ]
    if not heading:
        return bodies

    prefix = "\n".join(heading)
    return [f"{prefix}\n{body}" for body in bodies]


def _split_section(content: str) -> list[str]:
    """Split a section into sentence-chunked prose and row-packed table segments."""

    lines = content.split("\n")
    runs = _find_table_runs(lines)
    if not runs:
        return [body for body in get_sentence_splitter().split_text(content) if body.strip()]

    heading: list[str] = []
    cursor = 0
    while cursor < len(lines) and _HEADING_PATTERN.match(lines[cursor]):
        heading.append(lines[cursor])
        cursor += 1

    chunks: list[str] = []

    for start, end in runs:
        if cursor < start and any(line.strip() for line in lines[cursor:start]):
            chunks.extend(_prose_chunks(heading, lines[cursor:start]))

        header_lines = lines[start : start + 2]
        data_rows = lines[start + 2 : end]
        chunks.extend(_pack_table_rows(heading + header_lines, data_rows, TABLE_CHUNK_MAX_CHARS))
        cursor = end

    if cursor < len(lines) and any(line.strip() for line in lines[cursor:]):
        chunks.extend(_prose_chunks(heading, lines[cursor:]))

    return chunks


def _find_table_runs(lines: list[str]) -> list[tuple[int, int]]:
    """Find contiguous (header, divider, data rows...) table runs with real data rows."""

    runs: list[tuple[int, int]] = []
    index = 0
    while index < len(lines) - 1:
        if not (
            _TABLE_ROW_PATTERN.match(lines[index])
            and _TABLE_DIVIDER_PATTERN.match(lines[index + 1])
        ):
            index += 1
            continue

        end = index + 2
        while (
            end < len(lines)
            and _TABLE_ROW_PATTERN.match(lines[end])
            and not (end + 1 < len(lines) and _TABLE_DIVIDER_PATTERN.match(lines[end + 1]))
        ):
            end += 1

        if end - (index + 2) >= MIN_TABLE_DATA_ROWS:
            runs.append((index, end))
            index = end
        else:
            index += 1

    return runs


def _pack_table_rows(prefix_lines: list[str], data_rows: list[str], max_chars: int) -> list[str]:
    """Pack table rows into chunks, repeating the header/divider on every chunk."""

    prefix = "\n".join(prefix_lines)
    chunks: list[str] = []
    current = prefix
    current_rows = 0

    for row in data_rows:
        candidate = f"{current}\n{row}"
        if current_rows and len(candidate) > max_chars:
            chunks.append(current)
            current = f"{prefix}\n{row}"
            current_rows = 1
        else:
            current = candidate
            current_rows += 1

    if current_rows:
        chunks.append(current)

    return chunks


def extract_text_content(source_path: Path) -> str:
    """Convert a supported document into Markdown text."""

    suffix = source_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise AppException(
            code="RAG_UNSUPPORTED_FORMAT",
            message=f"Unsupported file format: {suffix}",
            status_code=400,
        )

    try:
        if suffix == ".pdf":
            text = extract_pdf_markdown(source_path)
        elif suffix == ".docx":
            text = extract_word_markdown(source_path)
        else:
            text = get_markdown_converter().convert(source_path).markdown
    except Exception as exc:
        raise AppException(
            code="RAG_CONVERSION_FAILED",
            message="Failed to extract text from the document.",
            status_code=400,
        ) from exc

    return _WHITESPACE_RUN_PATTERN.sub(" ", text)


def _batched_texts(texts: Sequence[str], batch_size: int) -> list[list[str]]:
    """Split texts into fixed-size batches for API calls."""

    return [list(texts[index : index + batch_size]) for index in range(0, len(texts), batch_size)]


def build_chunk_payloads(text_content: str) -> list[tuple[str, list[float]]]:
    """Chunk Markdown content by structure and generate embeddings."""

    sections = split_markdown(text_content)
    if not sections:
        raise AppException(
            code="RAG_CHUNKING_FAILED",
            message="Unable to chunk document content.",
            status_code=500,
        )

    chunk_texts = [section.strip() for section in sections if section.strip()]
    if not chunk_texts:
        raise AppException(
            code="RAG_EMPTY_CHUNKS",
            message="No valid chunks were produced from the document.",
            status_code=500,
        )

    settings = get_settings()
    embed_client = get_embedding_client()
    chunk_payloads: list[tuple[str, list[float]]] = []

    expected_dim = getattr(settings, "rag_embedding_dimensions", 0) or 0
    if not isinstance(expected_dim, int):
        expected_dim = 0

    for chunk_batch in _batched_texts(chunk_texts, settings.rag_embedding_batch_size):
        embedding_batch = embed_client.embed_texts(chunk_batch)
        if len(embedding_batch) != len(chunk_batch):
            raise AppException(
                code="RAG_EMBEDDING_FAILED",
                message="Embedding provider returned an unexpected number of embeddings.",
                status_code=502,
            )

        for embedding in embedding_batch:
            if expected_dim and len(embedding) != expected_dim:
                raise AppException(
                    code="RAG_EMBEDDING_DIMENSION_MISMATCH",
                    message=(f"Embedding dimension mismatch. Expected {expected_dim}."),
                    status_code=500,
                )

        chunk_payloads.extend(
            (chunk_text, list(embedding))
            for chunk_text, embedding in zip(chunk_batch, embedding_batch, strict=True)
        )

    if not chunk_payloads:
        raise AppException(
            code="RAG_EMPTY_CHUNKS",
            message="No valid chunks were produced from the document.",
            status_code=500,
        )

    return chunk_payloads
