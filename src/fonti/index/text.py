"""Terms for keyword search (FTS5 BM25) and for passage matching."""

import re

from fonti.config import KeywordMode
from fonti.italian import is_stopword, stem

_WORD_RE = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _WORD_RE.findall(text)]


def keyword_terms(text: str, mode: KeywordMode) -> list[str]:
    """Lowercase words (mode "plain") or Italian stems without stopwords (mode "stemmed")."""
    if mode == "stemmed":
        return [stem(token) for token in tokenize(text) if not is_stopword(token)]
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
