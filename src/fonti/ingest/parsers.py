"""File parsers: PDF (text layer, via pypdfium2) and plain text / Markdown."""

import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import pypdfium2 as pdfium

from fonti.domain import Block, BlockKind, ParsedDocument
from fonti.errors import FontiError
from fonti.ingest.structure import heading_level, lines_to_blocks
from fonti.ingest.text import normalize

SUPPORTED_SUFFIXES = frozenset({".pdf", ".txt", ".md", ".docx"})
# Bump when parsing output changes, so that indexes built by older versions are not reused.
PARSER_VERSION = "2"

_DIGITS = re.compile(r"\d+")
_EDGE_LINES = 3
_MAX_COUNTER_LETTERS = 12  # "Pagina 3 di 40" is a counter, a sentence is not

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
    if suffix == ".docx":
        raise ParseError(f"{path.name}: i file .docx si leggono con il parser docling")
    raise ParseError(f"Formato non supportato: {path.name}")


def parse_pdf(path: Path) -> ParsedDocument:
    """Extract the text layer page by page; scanned pages yield no text (OCR is separate)."""
    try:
        pdf = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as exc:
        raise ParseError(f"Impossibile aprire il PDF {path.name}: {exc}") from exc
    try:
        title = (pdf.get_metadata_dict().get("Title") or "").strip() or None
        pages: list[list[str]] = []
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
            pages.append(
                [line for line in normalize(raw).split("\n") if not _PAGE_NUMBER.fullmatch(line)]
            )
        blocks: list[Block] = []
        for number, lines in enumerate(drop_running_headers(pages), start=1):
            blocks.extend(lines_to_blocks(lines, page=number))
        return ParsedDocument(tuple(blocks), page_count=len(pdf), title=title, parser="fast")
    finally:
        pdf.close()


def drop_running_headers(pages: Sequence[Sequence[str]]) -> list[list[str]]:
    """Remove running headers and footers: lines among the first or last three of a page
    that recur on at least half of the pages. Identical lines always go; lines that differ
    only in their digits ("5 - 40", "| 3") go when they have few letters and are not a
    heading ("ART. 25.")."""
    if len(pages) < 3:
        return [list(lines) for lines in pages]
    exact: Counter[str] = Counter()
    numbered: Counter[str] = Counter()
    for lines in pages:
        edges = [lines[i] for i in _edge_indices(lines)]
        exact.update(set(edges))
        numbered.update({_DIGITS.sub("#", line) for line in edges})
    threshold = max(3, len(pages) // 2)

    def is_running(line: str) -> bool:
        if exact[line] >= threshold:
            return True
        return (
            numbered[_DIGITS.sub("#", line)] >= threshold
            and sum(c.isalpha() for c in line) <= _MAX_COUNTER_LETTERS
            and not heading_level(line)
        )

    cleaned = []
    for lines in pages:
        positions = set(_edge_indices(lines))
        cleaned.append(
            [line for i, line in enumerate(lines) if i not in positions or not is_running(line)]
        )
    return cleaned


def _edge_indices(lines: Sequence[str]) -> list[int]:
    filled = [i for i, line in enumerate(lines) if line]
    return filled[:_EDGE_LINES] + filled[-_EDGE_LINES:]


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
