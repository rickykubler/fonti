"""File parsers: PDF (text layer, via pypdfium2) and plain text / Markdown."""

import re
from pathlib import Path

import pypdfium2 as pdfium

from fonti.domain import Block, BlockKind, ParsedDocument
from fonti.errors import FontiError
from fonti.ingest.structure import heading_level, lines_to_blocks
from fonti.ingest.text import normalize

SUPPORTED_SUFFIXES = frozenset({".pdf", ".txt", ".md"})

_MARKDOWN_HEADING = re.compile(r"(#{1,6})\s+(.+?)\s*#*")
# Lines that are only a page number or a footnote reference ("12", "- 12 -", "pag. 12").
_PAGE_NUMBER = re.compile(
    r"\d{1,4}|[-–]\s*\d{1,4}\s*[-–]|(?:pag\.|pagina)\s*\d{1,4}", re.IGNORECASE
)


class ParseError(FontiError):
    """The file could not be read; the message is meant for the user."""


def parse_file(path: Path) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix in (".txt", ".md"):
        return parse_text(path)
    raise ParseError(f"Formato non supportato: {path.name}")


def parse_pdf(path: Path) -> ParsedDocument:
    """Extract the text layer page by page; scanned pages yield no text (OCR is separate)."""
    try:
        pdf = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as exc:
        raise ParseError(f"Impossibile aprire il PDF {path.name}: {exc}") from exc
    try:
        title = (pdf.get_metadata_dict().get("Title") or "").strip() or None
        blocks: list[Block] = []
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                textpage = page.get_textpage()
                try:
                    raw = textpage.get_text_range()
                finally:
                    textpage.close()
            finally:
                page.close()
            lines = [
                line for line in normalize(raw).split("\n") if not _PAGE_NUMBER.fullmatch(line)
            ]
            blocks.extend(lines_to_blocks(lines, page=index + 1))
        return ParsedDocument(tuple(blocks), page_count=len(pdf), title=title, parser="fast")
    finally:
        pdf.close()


def parse_text(path: Path) -> ParsedDocument:
    """Plain text or Markdown as a single page; `#` headings become heading blocks."""
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError(f"{path.name} non è un file di testo UTF-8") from exc
    blocks: list[Block] = []
    lines: list[str] = []
    for line in normalize(raw).split("\n"):
        markdown = _MARKDOWN_HEADING.fullmatch(line)
        if markdown:
            blocks.extend(lines_to_blocks(lines, page=1))
            lines.clear()
            text, level = markdown.group(2), len(markdown.group(1))
            blocks.append(Block(BlockKind.HEADING, text, 1, heading_level(text) or level))
        else:
            lines.append(line)
    blocks.extend(lines_to_blocks(lines, page=1))
    return ParsedDocument(tuple(blocks), page_count=1, title=None, parser="text")
