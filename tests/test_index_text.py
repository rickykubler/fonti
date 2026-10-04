from fonti.index.text import index_terms, match_query


def test_index_terms_are_lowercase_words() -> None:
    assert index_terms("L'Art. 13 della Costituzione!") == "l art 13 della costituzione"


def test_match_query_quotes_terms_and_drops_operators() -> None:
    query = match_query('canone AND "durata" OR NEAR(x) -- 5*')

    assert query == '"canone" OR "and" OR "durata" OR "or" OR "near" OR "5"'


def test_match_query_deduplicates_terms() -> None:
    assert match_query("canone Canone") == '"canone"'


def test_match_query_without_terms_is_none() -> None:
    assert match_query("?! -- ...") is None
