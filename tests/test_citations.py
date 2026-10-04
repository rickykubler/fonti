from fonti.domain import BlockKind, Hit, PageSpan
from fonti.generation.citations import ABSTAIN_MESSAGE, align, build_answer, parse_claims

RENT = (
    "Art. 3 - Canone\n\nIl canone annuo è convenuto in euro 9.600,00. È pagato in dodici rate "
    "mensili anticipate di euro 800,00 ciascuna. Il pagamento avviene con bonifico bancario."
)
DEPOSIT = "Art. 4 - Deposito\n\nIl conduttore versa un deposito pari a tre mensilità del canone."
OFFSET = 1000  # where RENT starts in the document text


def hits() -> list[Hit]:
    return [
        Hit(1, "doc", "contratto.pdf", "Contratto", RENT, OFFSET, OFFSET + len(RENT), 2, 2,
            "Art. 3 - Canone", BlockKind.TEXT),
        Hit(2, "doc", "contratto.pdf", "Contratto", DEPOSIT, 3000, 3000 + len(DEPOSIT), 3, 3,
            "Art. 4 - Deposito", BlockKind.TEXT),
    ]  # fmt: skip


def pages(_doc_id: str) -> list[PageSpan]:
    return [PageSpan(1, 0, 900), PageSpan(2, 1000, 2900), PageSpan(3, 3000, 4000)]


def test_parse_claims_keeps_valid_markers_only() -> None:
    claims = parse_claims("Il canone è di 800 euro [1]. Il deposito vale tre mesi [2][9].", 2)

    assert [(c.text, c.sources) for c in claims] == [
        ("Il canone è di 800 euro.", (1,)),
        ("Il deposito vale tre mesi.", (2,)),
    ]


def test_parse_claims_accepts_grouped_markers() -> None:
    [claim] = parse_claims("Si paga con bonifico [1, 2].", 2)

    assert claim.sources == (1, 2)


def test_align_finds_the_supporting_sentence() -> None:
    alignment = align("Le rate mensili sono di 800 euro", RENT)

    assert alignment is not None
    assert RENT[alignment.start : alignment.end] == (
        "È pagato in dodici rate mensili anticipate di euro 800,00 ciascuna."
    )
    assert alignment.support == 1.0


def test_answer_cites_verbatim_passages_with_their_page() -> None:
    result = build_answer(
        "Quanto si paga?",
        "Si pagano dodici rate mensili di 800 euro [1]. Serve un deposito di tre mensilità [2].",
        hits(),
        pages,
        0.3,
    )

    assert not result.abstained
    first, second = result.citations
    assert (first.number, first.page, first.section) == (1, 2, "Art. 3 - Canone")
    assert first.passage in RENT
    assert first.start == OFFSET + RENT.index(first.passage)
    assert (second.number, second.page) == (2, 3)


def test_not_found_output_abstains_and_keeps_nearest_sources() -> None:
    result = build_answer("Chi ha vinto?", "NON_TROVATO", hits(), pages, 0.3)

    assert result.abstained
    assert result.text == ABSTAIN_MESSAGE
    assert result.citations == ()
    assert len(result.sources) == 2


def test_answers_without_valid_or_supported_citations_abstain() -> None:
    no_markers = build_answer("q", "Il canone è di 800 euro.", hits(), pages, 0.3)
    wrong_number = build_answer("q", "Il canone è di 800 euro [7].", hits(), pages, 0.3)
    unsupported = build_answer("q", "La Luna dista 384.000 chilometri [1].", hits(), pages, 0.3)

    assert no_markers.abstained
    assert wrong_number.abstained
    assert unsupported.abstained


def test_thinking_and_invalid_markers_are_removed_from_the_text() -> None:
    output = "<think>calcolo...</think>Le rate mensili sono di 800 euro [1][5]."

    result = build_answer("q", output, hits(), pages, 0.3)

    assert result.text == "Le rate mensili sono di 800 euro [1]."
