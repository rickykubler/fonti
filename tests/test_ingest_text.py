from fonti.ingest.text import join_lines, normalize, split_sentences


def sentences(text: str) -> list[str]:
    return [text[start:end] for start, end in split_sentences(text)]


def test_normalize_fixes_ligatures_spaces_and_soft_hyphens() -> None:
    raw = (
        "La \N{LATIN SMALL LIGATURE FI}ne\N{NO-BREAK SPACE}del  contratto\r\n"
        "è pre\N{SOFT HYPHEN}vista.  \r\n"
    )

    assert normalize(raw) == "La fine del contratto\nè prevista.\n"


def test_normalize_removes_pdfium_line_break_hyphen_marker() -> None:
    assert normalize("interna" + chr(0xFFFE) + "zionale") == "internazionale"


def test_join_lines_undoes_hyphenation() -> None:
    assert join_lines(["il contrat-", "to di locazione"]) == "il contratto di locazione"
    assert join_lines(["Torino -", "Milano"]) == "Torino - Milano"


def test_split_sentences_on_periods() -> None:
    text = "Il canone è di euro 800. Il conduttore paga entro il giorno 5!"

    assert sentences(text) == ["Il canone è di euro 800.", "Il conduttore paga entro il giorno 5!"]


def test_abbreviations_do_not_end_sentences() -> None:
    text = "Ai sensi dell'art. 13 e del D.Lgs. 196/2003 vale la L. 241/1990. Fine del testo."

    assert sentences(text) == [
        "Ai sensi dell'art. 13 e del D.Lgs. 196/2003 vale la L. 241/1990.",
        "Fine del testo.",
    ]


def test_numbers_with_dots_can_end_a_sentence() -> None:
    assert sentences("Il canone è di euro 9.600,00. È pagato in rate.") == [
        "Il canone è di euro 9.600,00.",
        "È pagato in rate.",
    ]


def test_leading_enumeration_is_not_a_sentence() -> None:
    text = "1. La libertà personale è inviolabile. 2. Non è ammessa la detenzione."

    assert sentences(text) == [
        "1. La libertà personale è inviolabile.",
        "2. Non è ammessa la detenzione.",
    ]


def test_line_breaks_end_sentences_and_spans_skip_whitespace() -> None:
    text = "Art. 13\n\n  La libertà personale è inviolabile.  "

    assert sentences(text) == ["Art. 13", "La libertà personale è inviolabile."]


def test_lowercase_after_period_does_not_split() -> None:
    assert sentences("Somma pari a euro 9.600,00 annui. in rate.") == [
        "Somma pari a euro 9.600,00 annui. in rate."
    ]
