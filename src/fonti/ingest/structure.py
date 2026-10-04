"""Heading detection and paragraph grouping for text extracted line by line."""

import re
from collections.abc import Sequence

from fonti.domain import Block, BlockKind
from fonti.ingest.text import join_lines
from fonti.italian import is_stopword

_ROMAN = r"[IVXLCDM]+"
_ORDINAL = (
    r"(?i:prim[ao]|second[ao]|terz[ao]|quart[ao]|quint[ao]|sest[ao]|settim[ao]|ottav[ao]"
    r"|non[ao]|decim[ao]|preliminare|unic[ao])"
)
_NUMBER = rf"(?:{_ROMAN}|\d+|{_ORDINAL})"
_LATIN = r"(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)"

# Structural headings of Italian legal and contractual documents, with their depth.
_STRUCTURAL = [
    (re.compile(rf"(?:PARTE|Parte|LIBRO|Libro)\s+{_NUMBER}\b"), 1),
    (re.compile(rf"(?:ALLEGATO|Allegato)\s+(?:[A-Z]|{_NUMBER})\b"), 1),
    (re.compile(rf"(?:TITOLO|Titolo)\s+{_NUMBER}\b"), 2),
    (re.compile(rf"(?:CAPO|Capo)\s+{_NUMBER}\b"), 3),
    (re.compile(rf"(?:SEZIONE|Sezione)\s+{_NUMBER}\b"), 4),
    (re.compile(rf"(?:ARTICOLO|Articolo|ART\.?|Art\.?)\s*\d+(?:\s*[-–]?\s*{_LATIN}\b)?"), 5),
]
_NUMBERED_TITLE = re.compile(r"(\d+(?:\.\d+)*)\.?\s+(\S.*)")
# "ART. 56.9": the 9 is a footnote mark glued to the heading.
_ARTICLE_FOOTNOTE = re.compile(
    rf"^((?:ARTICOLO|Articolo|ART\.?|Art\.?)\s*\d+(?:\s*{_LATIN})?\.)\d{{1,3}}$"
)
_INLINE_ARTICLE = re.compile(
    rf"((?:ARTICOLO|Articolo|ART\.?|Art\.?)\s*\d+(?:\s*[-–]?\s*{_LATIN}\b)?\.)\d{{0,3}}\s+"
    r"(?=[A-ZÀ-Ý«\"(])"
)
_LETTER_SPACED = re.compile(r"(?:\S ){3,}\S")
_SPACED_KEYWORD = re.compile(r"(PARTE|LIBRO|TITOLO|CAPO|SEZIONE|ALLEGATO)([IVXLCDM]+|\d+)")
_LIST_ITEM = re.compile(r"(?:[-–•·▪]|\(?[a-z]\)|\(?\d+\)|\d+\.)\s")
_TITLE_SEPARATORS = "-–—:(."
_MAX_HEADING_CHARS = 120
_MAX_TITLE_CHARS = 100


def heading_level(line: str) -> int:
    """Depth of `line` as a heading (1 = top level), or 0 if it is not a heading."""
    if not line or len(line) > _MAX_HEADING_CHARS:
        return 0
    for pattern, level in _STRUCTURAL:
        match = pattern.match(line)
        if match and _is_title_rest(line[match.end() :]):
            return level
    numbered = _NUMBERED_TITLE.fullmatch(line)
    if numbered and _is_short_title(numbered.group(2)):
        return 6 + numbered.group(1).count(".")
    if _is_caps_title(line):
        return 1
    return 0


def collapse_letter_spacing(line: str) -> str:
    """Undo letter-spaced typography: "P A R T E I" -> "PARTE I", "I N D I C E" -> "INDICE"."""
    if not _LETTER_SPACED.fullmatch(line):
        return line
    joined = line.replace(" ", "")
    keyword = _SPACED_KEYWORD.fullmatch(joined)
    return f"{keyword.group(1)} {keyword.group(2)}" if keyword else joined


def is_bare_heading(line: str) -> bool:
    """A structural heading without a title, e.g. "TITOLO I" or "Articolo 17"."""
    return any(
        (match := pattern.match(line)) and line[match.end() :].strip(" .:") == ""
        for pattern, _ in _STRUCTURAL
    )


def lines_to_blocks(lines: Sequence[str], page: int) -> list[Block]:
    """Group the lines of one page into heading and paragraph blocks.

    Blank lines, headings, list items and lines that end a sentence well before the right
    margin start a new paragraph.
    """
    typical_length = _typical_length(lines)
    blocks: list[Block] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(Block(BlockKind.TEXT, join_lines(paragraph), page))
            paragraph.clear()

    for index, raw in enumerate(lines):
        if not raw:
            flush()
            continue
        line = _ARTICLE_FOOTNOTE.sub(r"\1", collapse_letter_spacing(raw))
        inline = _INLINE_ARTICLE.match(line)
        if inline and not heading_level(line):
            # "ART. 56.9 La Camera..." -> heading "ART. 56." (9 is a footnote mark) + text.
            flush()
            blocks.append(Block(BlockKind.HEADING, inline.group(1), page, 5))
            line = line[inline.end() :]
        previous = blocks[-1] if blocks and not paragraph else None
        following = next((text for text in lines[index + 1 :] if text), "")
        is_title = _is_caps_title(line) or (
            _is_short_title(line)
            and len(line) < 0.85 * typical_length
            and not following[:1].islower()  # a wrapped sentence continues in lowercase
            and not is_stopword(line.split()[-1].strip("’'"))  # "... con la" is wrapped
        )
        if (
            previous is not None
            and previous.kind is BlockKind.HEADING
            and is_bare_heading(previous.text)
            and is_title
        ):
            blocks[-1] = Block(BlockKind.HEADING, f"{previous.text}\n{line}", page, previous.level)
            continue
        level = heading_level(line)
        if level:
            flush()
            blocks.append(Block(BlockKind.HEADING, line, page, level))
            continue
        if paragraph and _starts_new_paragraph(paragraph[-1], line, typical_length):
            flush()
        paragraph.append(line)
    flush()
    return blocks


def _is_title_rest(rest: str) -> bool:
    rest = rest.strip()
    if rest in ("", ".", ":"):
        return True
    if rest[0] not in _TITLE_SEPARATORS:
        return False
    title = rest.lstrip(_TITLE_SEPARATORS + " ")
    return not title or _is_short_title(title)


def _is_short_title(text: str) -> bool:
    text = text.strip()
    return (
        0 < len(text) <= _MAX_TITLE_CHARS
        and len(text.split()) <= 12
        and text[0].isupper()
        and text[-1] not in ".;,"
    )


def _is_caps_title(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 4 or len(line) > _MAX_TITLE_CHARS or line.endswith((".", ";", ",")):
        return False
    uppercase = sum(c.isupper() for c in letters)
    return uppercase / len(letters) >= 0.9 and any(len(word) >= 3 for word in line.split())


def _starts_new_paragraph(previous: str, line: str, typical_length: int) -> bool:
    if _LIST_ITEM.match(line):
        return True
    ends_sentence = previous.endswith((".", "!", "?", ":", ";", "»", '"', ")"))
    return ends_sentence and len(previous) < 0.85 * typical_length


def _typical_length(lines: Sequence[str]) -> int:
    lengths = sorted(len(line) for line in lines if line)
    if not lengths:
        return 0
    return lengths[min(len(lengths) - 1, int(len(lengths) * 0.9))]
