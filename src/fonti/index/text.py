"""Text normalization for the keyword (BM25) index and its queries."""

import re

_WORD_RE = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _WORD_RE.findall(text)]


def index_terms(text: str) -> str:
    """Terms stored in the FTS5 index; queries must be normalized the same way."""
    return " ".join(tokenize(text))


def match_query(question: str) -> str | None:
    """Build an FTS5 MATCH expression that ORs the question terms, or None if there are none.

    Every term is quoted, so FTS5 operators and punctuation typed by the user are inert.
    """
    terms = [term for term in tokenize(question) if len(term) > 1 or term.isdigit()]
    if not terms:
        return None
    return " OR ".join(f'"{term}"' for term in dict.fromkeys(terms))
