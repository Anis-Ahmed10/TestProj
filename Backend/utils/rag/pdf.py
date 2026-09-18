from __future__ import annotations

from collections import Counter
from pathlib import Path

PDF_HEADING_SIZE_RATIO = 1.10

PDF_MAX_HEADING_CHARS = 80

LINE_BASELINE_TOLERANCE = 3.0


def _markdown_row(cells: list[str]) -> str:
    """Render one Markdown table row."""

    return "| " + " | ".join(cells) + " |"


def _table_to_markdown(rows: list[list[str | None]]) -> list[str]:
    """Render an extracted table as Markdown rows, header first."""

    cleaned = [
        [" ".join((cell or "").split()) for cell in row]
        for row in rows
        if any((cell or "").strip() for cell in row)
    ]
    if not cleaned:
        return []

    width = max(len(row) for row in cleaned)
    padded = [row + [""] * (width - len(row)) for row in cleaned]
    header, *body = padded

    return [
        _markdown_row(header),
        _markdown_row(["---"] * width),
        *(_markdown_row(row) for row in body),
    ]


def _dominant_size(row: list[dict]) -> float:
    """Return a line's char-weighted dominant font size.

    A line's size drives heading detection, so it must reflect the size
    that most of the line's TEXT is set in — using the largest word's size
    would let a single bigger word (e.g. a bold inline label) promote an
    otherwise-ordinary body line to a heading.
    """

    weights: Counter[float] = Counter()
    for word in row:
        weights[round(float(word["size"]), 1)] += len(word["text"])

    return weights.most_common(1)[0][0]


def _within(word: dict, box: tuple[float, float, float, float]) -> bool:
    """Return True when a word's centre falls inside a bounding box."""

    left, top, right, bottom = box
    centre_x = (float(word["x0"]) + float(word["x1"])) / 2
    centre_y = (float(word["top"]) + float(word["bottom"])) / 2

    return left <= centre_x <= right and top <= centre_y <= bottom


def _group_into_lines(words: list[dict]) -> list[list[dict]]:
    """Group words into visual lines by baseline, tolerant of mixed font sizes.

    Words sharing a line can have different `top` values when font sizes
    differ — e.g. a bold label next to smaller body text — so lines are
    grouped by `bottom` (close to the baseline, which stays consistent
    across sizes) against a fixed per-line reference, rather than bucketed
    on an absolute grid.
    """

    ordered = sorted(words, key=lambda word: (float(word["bottom"]), float(word["x0"])))
    lines: list[list[dict]] = []
    reference_bottom: float | None = None

    for word in ordered:
        bottom = float(word["bottom"])
        if reference_bottom is None or abs(bottom - reference_bottom) > LINE_BASELINE_TOLERANCE:
            lines.append([])
            reference_bottom = bottom
        lines[-1].append(word)

    for line in lines:
        line.sort(key=lambda word: word["x0"])

    return lines


def _pdf_lines(source_path: Path) -> list[tuple[str, float, bool]]:
    """Read a PDF as (text, font size, bold) per visual line.

    Ruled tables are emitted as Markdown rows so the shared chunker can keep
    their headers attached; a table row carries no font size because it is
    never a heading candidate.
    """

    import pdfplumber

    lines: list[tuple[str, float, bool]] = []
    with pdfplumber.open(source_path) as pdf:
        for page in pdf.pages:
            tables = page.find_tables()
            boxes = [table.bbox for table in tables]
            blocks: list[tuple[float, list[tuple[str, float, bool]]]] = []

            for table in tables:
                rendered = _table_to_markdown(table.extract())
                if rendered:
                    blocks.append((table.bbox[1], [(row, 0.0, False) for row in rendered]))

            words = page.extract_words(extra_attrs=["size", "fontname"])
            words = [word for word in words if not any(_within(word, box) for box in boxes)]

            for row in _group_into_lines(words):
                text = " ".join(word["text"] for word in row).strip()
                if not text:
                    continue
                size = _dominant_size(row)
                bold = any("bold" in str(word["fontname"]).lower() for word in row)
                top = min(float(word["top"]) for word in row)
                blocks.append((top, [(text, size, bold)]))

            blocks.sort(key=lambda block: block[0])
            for _, block in blocks:
                lines.extend(block)

            page.close()

    return lines


def extract_pdf_markdown(source_path: Path) -> str:
    """Extract PDF text, restoring headings from font size so sections can be chunked.

    A PDF heading carries no markup — it is only text drawn in a larger font — so
    heading levels are inferred by comparing each line's size against body text.
    markitdown is bypassed here because its table reconstruction misassigns words
    across columns for cells that wrap onto multiple lines.
    """

    lines = _pdf_lines(source_path)
    if not lines:
        return ""

    prose = [(text, size) for text, size, _ in lines if not text.startswith("|")]

    weights: Counter[float] = Counter()
    for text, size in prose:
        weights[size] += len(text)
    body_size = weights.most_common(1)[0][0] if weights else 0.0

    heading_sizes = sorted(
        {size for _, size in prose if size >= body_size * PDF_HEADING_SIZE_RATIO},
        reverse=True,
    )
    levels = {size: min(index + 1, 6) for index, size in enumerate(heading_sizes)}

    rendered: list[str] = []
    for text, size, bold in lines:
        level = None if text.startswith("|") else levels.get(size)
        if level is None and not heading_sizes and not text.startswith("|"):
            # No size variation to key on; fall back to short bold lines.
            if bold and size >= body_size and len(text) < PDF_MAX_HEADING_CHARS:
                level = 1

        if level is None:
            rendered.append(text)
        else:
            rendered.extend(["", f"{'#' * level} {text}"])

    return "\n".join(rendered).strip()
