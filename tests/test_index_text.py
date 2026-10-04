import pytest

from fonti.index.text import expand_abbreviations, index_terms, keyword_terms, match_query


@pytest.mark.parametrize(
    ("abbreviated", "expanded"),
    [
        ("art. 13 del d.lgs. 196/2003", "articolo 13 del decreto legislativo 196/2003"),
        ("artt. 1341 e 1342 c.c.", "articolo 1341 e 1342 codice civile"),
        ("L. 241/1990 e l. n. 300", "legge 241/1990 e legge n. 300"),
        ("art. 360 c.p.c.", "articolo 360 codice procedura civile"),
        ("D.P.R. 445/2000", "decreto presidente repubblica 445/2000"),
        ("lett. b) e co. 2", "lettera b) e comma 2"),
    ],
)
def test_legal_abbreviations_are_expanded(abbreviated: str, expanded: str) -> None:
    assert " ".join(expand_abbreviations(abbreviated).split()) == expanded


def test_abbreviations_and_full_forms_give_the_same_stemmed_terms() -> None:
    short = keyword_terms("art. 13 del d.lgs. 196/2003", "stemmed")
    full = keyword_terms("Articolo 13 del Decreto Legislativo 196/2003", "stemmed")

    assert short == full


def test_ordinary_words_ending_with_l_or_art_are_untouched() -> None:
    assert expand_abbreviations("Il canone e l'arte.") == "Il canone e l'arte."


def test_index_terms_are_lowercase_words() -> None:
    assert index_terms("L'Art. 13 della Costituzione!") == "l art 13 della costituzione"


def test_match_query_quotes_terms_and_drops_operators() -> None:
    query = match_query('canone AND "durata" OR NEAR(x) -- 5*')

    assert query == '"canone" OR "and" OR "durata" OR "or" OR "near" OR "5"'


def test_match_query_deduplicates_terms() -> None:
    assert match_query("canone Canone") == '"canone"'


def test_match_query_without_terms_is_none() -> None:
    assert match_query("?! -- ...") is None
