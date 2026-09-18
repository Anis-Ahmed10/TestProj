"""Unit tests for PDF extraction with font-size heading reconstruction."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.rag.helpers import extract_text_content, split_markdown
from app.utils.rag.pdf import PDF_MAX_HEADING_CHARS, _pdf_lines, extract_pdf_markdown


@patch("app.utils.rag.pdf._pdf_lines")
def test_extract_pdf_markdown_detects_headings_by_font_size(mock_pdf_lines):
    mock_pdf_lines.return_value = [
        ("System Context Document", 20.0, True),
        ("Purpose", 14.0, True),
        ("This document gives background context for the reader.", 10.0, False),
        ("1.1 Gateway", 11.5, True),
        ("The gateway terminates TLS before forwarding requests.", 10.0, False),
    ]

    markdown = extract_pdf_markdown(Path("test.pdf"))

    assert markdown.split("\n") == [
        "# System Context Document",
        "",
        "## Purpose",
        "This document gives background context for the reader.",
        "",
        "### 1.1 Gateway",
        "The gateway terminates TLS before forwarding requests.",
    ]


@patch("app.utils.rag.pdf._pdf_lines")
def test_extract_pdf_markdown_bold_fallback_when_sizes_uniform(mock_pdf_lines):
    mock_pdf_lines.return_value = [
        ("Purpose", 10.0, True),
        ("This document gives background context for the reader.", 10.0, False),
        ("System Overview", 10.0, True),
        ("The platform has a web front end and an API service.", 10.0, False),
    ]

    markdown = extract_pdf_markdown(Path("test.pdf"))

    assert "# Purpose" in markdown
    assert "# System Overview" in markdown
    assert "# This document" not in markdown


@patch("app.utils.rag.pdf._pdf_lines")
def test_extract_pdf_markdown_no_signal_emits_no_headings(mock_pdf_lines):
    mock_pdf_lines.return_value = [
        ("Purpose", 10.0, False),
        ("This document gives background context for the reader.", 10.0, False),
    ]

    markdown = extract_pdf_markdown(Path("test.pdf"))

    assert "#" not in markdown


@patch("app.utils.rag.pdf._pdf_lines")
def test_extract_pdf_markdown_long_bold_line_is_not_a_heading(mock_pdf_lines):
    long_bold = (
        "This entire sentence is emphasised in bold from start to finish, and it runs "
        "well past the heading length guard so it must stay ordinary body text."
    )
    assert len(long_bold) > PDF_MAX_HEADING_CHARS
    mock_pdf_lines.return_value = [
        ("Purpose", 10.0, True),
        (long_bold, 10.0, True),
    ]

    markdown = extract_pdf_markdown(Path("test.pdf"))

    assert "# Purpose" in markdown
    assert f"# {long_bold}" not in markdown


@patch("app.utils.rag.pdf._pdf_lines")
def test_extract_pdf_markdown_empty_document(mock_pdf_lines):
    mock_pdf_lines.return_value = []

    assert extract_pdf_markdown(Path("test.pdf")) == ""


def test_extract_pdf_markdown_end_to_end_splits_into_sections(tmp_path):
    """A real PDF must chunk by section rather than collapsing into one node."""

    reportlab_styles = pytest.importorskip("reportlab.lib.styles")
    platypus = pytest.importorskip("reportlab.platypus")

    base = reportlab_styles.getSampleStyleSheet()["Normal"]
    heading_style = reportlab_styles.ParagraphStyle(
        "H", parent=base, fontSize=16, fontName="Helvetica-Bold"
    )
    body_style = reportlab_styles.ParagraphStyle("B", parent=base, fontSize=10)

    pdf_path = tmp_path / "sample.pdf"
    platypus.SimpleDocTemplate(str(pdf_path)).build(
        [
            platypus.Paragraph("Purpose", heading_style),
            platypus.Paragraph("This document explains the shared context.", body_style),
            platypus.Paragraph("1. System Overview", heading_style),
            platypus.Paragraph("The platform has a front end and an API service.", body_style),
        ]
    )

    markdown = extract_text_content(pdf_path)
    chunks = split_markdown(markdown)

    assert "# Purpose" in markdown
    assert "# 1. System Overview" in markdown
    assert "\t" not in markdown
    assert len(chunks) == 2


def _build_table_pdf(pdf_path, colours, platypus, styles):
    """Build a PDF with a heading, a lead-in line and a ruled table."""

    base = styles.getSampleStyleSheet()["Normal"]
    heading = styles.ParagraphStyle("H", parent=base, fontSize=16, fontName="Helvetica-Bold")
    body = styles.ParagraphStyle("B", parent=base, fontSize=10)
    cell = styles.ParagraphStyle("C", parent=base, fontSize=9)

    rows = [
        [platypus.Paragraph(text, cell) for text in ("Entity", "Key attributes", "Used in")],
        [
            platypus.Paragraph("Student", cell),
            platypus.Paragraph("Student ID, Student Type (UG / PGT / PGR), Programme", cell),
            platypus.Paragraph("All epics", cell),
        ],
        [
            platypus.Paragraph("Programme", cell),
            platypus.Paragraph("Title, Faculty, Study Level", cell),
            platypus.Paragraph("OLE, SMT", cell),
        ],
    ]
    table = platypus.Table(rows, colWidths=[90, 250, 110])
    table.setStyle(
        platypus.TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colours.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    platypus.SimpleDocTemplate(str(pdf_path)).build(
        [
            platypus.Paragraph("1. System Overview", heading),
            platypus.Paragraph("Core entities shared across stories:", body),
            platypus.Spacer(1, 8),
            table,
        ]
    )


def test_extract_pdf_markdown_preserves_ruled_table_structure(tmp_path):
    """A ruled PDF table must survive as a Markdown table with cells intact."""

    styles = pytest.importorskip("reportlab.lib.styles")
    platypus = pytest.importorskip("reportlab.platypus")
    colours = pytest.importorskip("reportlab.lib.colors")

    pdf_path = tmp_path / "table.pdf"
    _build_table_pdf(pdf_path, colours, platypus, styles)

    markdown = extract_pdf_markdown(pdf_path)

    assert "| Entity | Key attributes | Used in |" in markdown
    assert "| --- | --- | --- |" in markdown
    assert "| Programme | Title, Faculty, Study Level | OLE, SMT |" in markdown
    # The wrapped cell must stay in its own column rather than bleeding across.
    student_row = next(line for line in markdown.split("\n") if line.startswith("| Student |"))
    assert student_row.endswith("| All epics |")


def test_pdf_table_chunks_keep_header_and_heading(tmp_path):
    """Chunked PDF tables must carry both the section heading and the column header."""

    styles = pytest.importorskip("reportlab.lib.styles")
    platypus = pytest.importorskip("reportlab.platypus")
    colours = pytest.importorskip("reportlab.lib.colors")

    pdf_path = tmp_path / "table.pdf"
    _build_table_pdf(pdf_path, colours, platypus, styles)

    chunks = split_markdown(extract_pdf_markdown(pdf_path))

    table_chunks = [chunk for chunk in chunks if "| Entity |" in chunk]
    assert table_chunks
    for chunk in table_chunks:
        assert chunk.startswith("# 1. System Overview")

    assert all(chunk.startswith("# 1. System Overview") for chunk in chunks)


@patch("app.utils.rag.pdf._pdf_lines")
def test_extract_pdf_markdown_table_rows_are_never_headings(mock_pdf_lines):
    """Table rows carry no font size and must not be promoted to headings."""

    mock_pdf_lines.return_value = [
        ("Overview", 16.0, True),
        ("Body text that sets the body size for this document.", 10.0, False),
        ("| ID | Name |", 0.0, False),
        ("| --- | --- |", 0.0, False),
        ("| 1 | Story |", 0.0, False),
    ]

    markdown = extract_pdf_markdown(Path("test.pdf"))

    assert "# Overview" in markdown
    assert "| ID | Name |" in markdown
    assert "# | ID | Name |" not in markdown


def test_pdf_lines_keeps_mixed_font_size_words_on_one_line(tmp_path):
    """A bold label followed by smaller body text on the same baseline must stay one line.

    Words on a shared baseline get different `top` values when their font
    sizes differ, since `top` reflects each glyph's own ascent height. Line
    grouping must key on `bottom` (near the baseline, stable across sizes),
    not an absolute grid over `top`.
    """

    reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")

    pdf_path = tmp_path / "mixed.pdf"
    canvas = reportlab_canvas.Canvas(str(pdf_path))
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(72, 700, "Status:")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(120, 700, "Approved and ready for review")
    canvas.save()

    lines = _pdf_lines(pdf_path)

    assert len(lines) == 1
    assert lines[0][0] == "Status: Approved and ready for review"


def test_pdf_lines_uses_dominant_size_not_max(tmp_path):
    """A line's size must reflect its dominant text, not its single largest word.

    A bold inline label (e.g. "Status:") next to smaller body text must not
    make the whole line report the label's larger size, or an ordinary
    sentence gets promoted to a heading just because one word is bigger.
    """

    reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")

    pdf_path = tmp_path / "mixed_size.pdf"
    canvas = reportlab_canvas.Canvas(str(pdf_path))
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(72, 700, "Status:")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(120, 700, "Approved and ready for review")
    canvas.save()

    lines = _pdf_lines(pdf_path)

    assert len(lines) == 1
    assert lines[0][1] == 10.0


def test_extract_pdf_markdown_inline_bold_label_stays_body_text(tmp_path):
    """A short bold label inline with longer body text must not become a heading

    when the document has real heading-sized text elsewhere to key off.
    """

    canvas_module = pytest.importorskip("reportlab.pdfgen.canvas")

    pdf_path = tmp_path / "label.pdf"
    canvas = canvas_module.Canvas(str(pdf_path))
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(72, 750, "Request Summary")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(72, 720, "This request was submitted for review.")
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(72, 690, "Status:")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(115, 690, "Approved and ready for review")
    canvas.save()

    markdown = extract_pdf_markdown(pdf_path)

    assert "# Request Summary" in markdown
    assert "Status: Approved and ready for review" in markdown
    assert "# Status" not in markdown
