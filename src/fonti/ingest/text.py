"""Text utilities for Italian documents: normalization, line joining, sentence splitting."""

import re
import unicodedata
from collections.abc import Iterator, Sequence

_SPACES_RE = re.compile(
    r"[ \t\N{NO-BREAK SPACE}\N{EN QUAD}-\N{HAIR SPACE}\N{NARROW NO-BREAK SPACE}"
    r"\N{MEDIUM MATHEMATICAL SPACE}\N{IDEOGRAPHIC SPACE}]+"
)
# PDFium marks a word hyphenated across a line break with U+FFFE: "interna<U+FFFE>zionale".
_ZERO_WIDTH_RE = re.compile(
    r"[\N{SOFT HYPHEN}\N{ZERO WIDTH SPACE}-\N{ZERO WIDTH JOINER}\N{WORD JOINER}"
    r"\N{ZERO WIDTH NO-BREAK SPACE}\U0000FFFE]"
)
_SENTENCE_END_RE = re.compile(r"[.!?…]+[»”\"')\]]*(?=\s)")
_ROMAN_RE = re.compile(r"[ivxlcdm]+")
_DOTTED_ABBREVIATION_RE = re.compile(r"(?:[^\W\d_]+\.)+[^\W\d_]+")  # d.lgs, s.p.a, c.c
_SENTENCE_STARTS = "«\"“'‘(-–•"

# Common Italian abbreviations (lowercase, without the final period) that do not end a sentence.
_ABBREVIATIONS = frozenset(
    {
        "all", "art", "artt", "avv", "ca", "cap", "capp", "cfr", "cit", "co", "cod", "cost",
        "dott", "dr", "ecc", "ed", "egr", "es", "etc", "fig", "figg", "fraz", "geom", "gent",
        "ing", "int", "lett", "loc", "mod", "n", "nn", "num", "on", "p", "pag", "pagg", "par",
        "parr", "pp", "prof", "prot", "prov", "racc", "rag", "reg", "rif", "sc", "seg", "segg",
        "sez", "sig", "sigg", "ss", "spett", "tab", "tel", "tit", "v", "vol", "vs",
    }
)  # fmt: skip


def normalize(text: str) -> str:
    """NFKC (ligatures, compatibility forms), unified line breaks and spaces, trimmed lines."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _SPACES_RE.sub(" ", text)
    return "\n".join(line.strip() for line in text.split("\n"))


def join_lines(lines: Sequence[str]) -> str:
    """Join the lines of a paragraph, undoing hyphenation at line breaks ("contrat-" + "to")."""
    text = ""
    for line in lines:
        if not text:
            text = line
        elif len(text) > 1 and text[-1] == "-" and text[-2].isalpha() and line[:1].islower():
            text = text[:-1] + line
        else:
            text = f"{text} {line}"
    return text


def split_sentences(text: str) -> list[tuple[int, int]]:
    """Return (start, end) spans of the sentences in `text`, without surrounding whitespace.

    Line breaks always end a sentence; periods after abbreviations ("art.", "D.Lgs.") and
    after leading enumerations ("1. La libertà...") do not.
    """
    spans: list[tuple[int, int]] = []
    for offset, line in _lines(text):
        start = 0
        for match in _SENTENCE_END_RE.finditer(line):
            if _is_sentence_end(line, start, match):
                _append_span(spans, offset, line, start, match.end())
                start = match.end()
        _append_span(spans, offset, line, start, len(line))
    return spans


def _lines(text: str) -> Iterator[tuple[int, str]]:
    offset = 0
    for line in text.split("\n"):
        yield offset, line
        offset += len(line) + 1


def _append_span(
    spans: list[tuple[int, int]], offset: int, line: str, start: int, end: int
) -> None:
    segment = line[start:end]
    stripped = segment.strip()
    if stripped:
        begin = start + (len(segment) - len(segment.lstrip()))
        spans.append((offset + begin, offset + begin + len(stripped)))


def _is_sentence_end(line: str, start: int, match: re.Match[str]) -> bool:
    following = line[match.end() :].lstrip()
    if not following:
        return True
    if not (following[0].isupper() or following[0].isdigit() or following[0] in _SENTENCE_STARTS):
        return False
    punctuation = match.group().rstrip("»”\"')]")
    if punctuation != ".":
        return True
    tokens = line[start : match.start()].split()
    if not tokens:
        return False
    # The last word, without elided articles: "dell'art." -> "art".
    word = re.split(r"['’]", tokens[-1].lstrip('(«"“‘['))[-1].lower()
    if (
        word in _ABBREVIATIONS
        or _DOTTED_ABBREVIATION_RE.fullmatch(word)
        or (len(word) == 1 and word.isalpha())
    ):
        return False
    is_enumeration = len(tokens) == 1 and (word.isdigit() or _ROMAN_RE.fullmatch(word))
    return not is_enumeration
