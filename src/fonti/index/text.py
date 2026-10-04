"""Italian text normalization for keyword search and passage matching."""

import re
import unicodedata
from functools import lru_cache

import snowballstemmer

from fonti.config import KeywordMode

_WORD_RE = re.compile(r"\w+")

# Italian function words: they carry no meaning for matching.
STOPWORDS = frozenset(
    """
    a ad agli ai al all alla alle allo anche ancora avere aveva c che chi ci cio come con contro
    cosa cui d da dagli dai dal dall dalla dalle dallo degli dei del dell della delle dello di
    dove e ed era essere fra gli ha hai hanno ho i il in infatti io l la le lei li lo loro lui
    ma mi mia mie miei mio ne negli nei nel nell nella nelle nello noi non nostra nostre nostri
    nostro o oppure per perche piu po poi pero qual quale quali qualcosa quando quanto quel
    quella quelle quelli quello questa queste questi questo qui se senza si sia siamo siete sono
    sopra sotto su sua sue sugli sui sul sull sulla sulle sullo suo suoi ti tra tu tua tue tuo
    tuoi tutti tutto un una uno vi voi
    """.split()  # noqa: SIM905 - a compact list is easier to review
)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _WORD_RE.findall(text)]


def keyword_terms(text: str, mode: KeywordMode) -> list[str]:
    """Lowercase words (mode "plain") or Italian stems without stopwords (mode "stemmed")."""
    if mode == "stemmed":
        return [_stem(token) for token in tokenize(text) if fold_accents(token) not in STOPWORDS]
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
    """Stemmed, accent-free content words: "mensili" and "mensile" both give "mensil"."""
    return {
        _stem(token)
        for token in tokenize(text)
        if (len(token) > 2 or token.isdigit()) and fold_accents(token) not in STOPWORDS
    }


def fold_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@lru_cache(maxsize=65536)
def _stem(token: str) -> str:
    return fold_accents(_italian_stemmer().stemWord(token))


@lru_cache(maxsize=1)
def _italian_stemmer() -> snowballstemmer.stemmer:
    return snowballstemmer.stemmer("italian")
