"""Synthetic documents for tests and evaluation: render a small Markdown subset to PDF.

Needs the `reportlab` development dependency.
"""

from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

PAGE_BREAK = "---"
_TEXT_WIDTH = 451  # points: A4 width minus the default 1-inch margins


def render_pdf(markdown: str, path: Path, title: str | None = None) -> Path:
    """Render `#` headings, blank-line separated paragraphs, `|` tables and `---` page breaks."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

    styles = getSampleStyleSheet()
    story: list[Any] = []
    paragraph: list[str] = []
    rows: list[list[str]] = []

    def flush() -> None:
        if paragraph:
            story.append(Paragraph(escape(" ".join(paragraph)), styles["BodyText"]))
            paragraph.clear()
        if rows:
            # Column widths proportional to the longest cell, so long cells wrap inside the page.
            longest = [
                max(len(row[i]) for row in rows if i < len(row)) for i in range(len(rows[0]))
            ]
            widths = [_TEXT_WIDTH * max(n, 8) / sum(max(m, 8) for m in longest) for n in longest]
            cells = [[Paragraph(escape(cell), styles["BodyText"]) for cell in row] for row in rows]
            table = Table(cells, colWidths=widths, hAlign="LEFT")
            table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
            story.append(table)
            rows.clear()

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped == PAGE_BREAK:
            flush()
            story.append(PageBreak())
        elif stripped.startswith("#"):
            flush()
            level = min(len(stripped) - len(stripped.lstrip("#")), 3)
            story.append(Paragraph(escape(stripped.lstrip("#").strip()), styles[f"Heading{level}"]))
        elif stripped.startswith("|"):
            if paragraph:
                flush()
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if not all(set(cell) <= set("-: ") for cell in cells):  # skip separator rows
                rows.append(cells)
        elif not stripped:
            flush()
        else:
            if rows:
                flush()
            paragraph.append(stripped)
    flush()

    path.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(path), pagesize=A4, title=title or "", author="fonti").build(story)
    return path
