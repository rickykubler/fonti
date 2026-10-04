"""Italian language resources: stopwords, accent folding, Snowball stemming."""

import unicodedata
from functools import lru_cache

import snowballstemmer

# Italian function words (accent-free): they carry no meaning for matching.
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


def fold_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def is_stopword(word: str) -> bool:
    return fold_accents(word.lower()) in STOPWORDS


@lru_cache(maxsize=65536)
def stem(word: str) -> str:
    """Accent-free Snowball stem: "mensili" and "mensile" both give "mensil"."""
    return fold_accents(_stemmer().stemWord(word.lower()))


@lru_cache(maxsize=1)
def _stemmer() -> snowballstemmer.stemmer:
    return snowballstemmer.stemmer("italian")
