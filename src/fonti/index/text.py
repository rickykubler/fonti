"""Terms for keyword search (FTS5 BM25) and for passage matching."""

import re

from fonti.config import KeywordMode
from fonti.italian import is_stopword, stem

# Bump when keyword terms change: indexes built with older terms must be rebuilt.
KEYWORDS_VERSION = "2"

_WORD_RE = re.compile(r"\w+")
_END = r"(?=[\s,;:)]|$)"

# Italian legal abbreviations, expanded so that "art. 13 del d.lgs. 196/2003" and "articolo 13
# del decreto legislativo 196/2003" give the same terms. Longer forms come first.
_ABBREVIATIONS = [
    (rf"\bd\.\s?lgs\.?{_END}", "decreto legislativo"),
    (rf"\bd\.\s?p\.\s?c\.\s?m\.?{_END}", "decreto presidente consiglio ministri"),
    (rf"\bd\.\s?p\.\s?r\.?{_END}", "decreto presidente repubblica"),
    (rf"\bd\.\s?l\.{_END}", "decreto legge"),
    (rf"\bd\.\s?m\.{_END}", "decreto ministeriale"),
    (rf"\bc\.\s?p\.\s?c\.?{_END}", "codice procedura civile"),
    (rf"\bc\.\s?p\.\s?p\.?{_END}", "codice procedura penale"),
    (rf"\bc\.\s?c\.{_END}", "codice civile"),
    (rf"\bc\.\s?p\.{_END}", "codice penale"),
    (rf"\bg\.\s?u\.{_END}", "gazzetta ufficiale"),
    (rf"\bcost\.{_END}", "costituzione"),
    (r"\bartt?\.(?=\s*\d)", "articolo"),
    (r"\bl\.(?=\s*(?:n\.\s*)?\d)", "legge"),
    (r"\bco\.(?=\s*\d)", "comma"),
    (r"\bparr?\.(?=\s*\d)", "paragrafo"),
    (r"\blett\.(?=\s*[a-z]\b)", "lettera"),
]
_ABBREVIATION_RES = [
    (re.compile(pattern, re.IGNORECASE), words) for pattern, words in _ABBREVIATIONS
]


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _WORD_RE.findall(text)]


def expand_abbreviations(text: str) -> str:
    for pattern, words in _ABBREVIATION_RES:
        text = pattern.sub(f" {words} ", text)
    return text


def keyword_terms(text: str, mode: KeywordMode) -> list[str]:
    """Lowercase words (mode "plain") or, in mode "stemmed", Italian stems without stopwords
    after expanding legal abbreviations."""
    if mode == "stemmed":
        tokens = tokenize(expand_abbreviations(text))
        return [stem(token) for token in tokens if not is_stopword(token)]
    return tokenize(text)


def index_terms(text: str, mode: KeywordMode = "plain") -> str:
    """Terms stored in the FTS5 index; queries must use the same mode."""
    return " ".join(keyword_terms(text, mode))


def match_query(question: str, mode: KeywordMode = "plain") -> str | None:
    """Build an FTS5 MATCH expression that ORs the question terms, or None if there are none.

    Every term is quoted, so FTS5 operators and punctuation typed by the user are inert.
    """
    terms = [term for term in keyword_terms(question, mode) if len(term) > 1 or term.isdigit()]
    if not terms:
        return None
    return " OR ".join(f'"{term}"' for term in dict.fromkeys(terms))


def content_terms(text: str) -> set[str]:
    """Stemmed content words, used to align answer sentences with source sentences."""
    return {
        stem(token)
        for token in tokenize(text)
        if (len(token) > 2 or token.isdigit()) and not is_stopword(token)
    }
