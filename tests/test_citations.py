from collections.abc import Sequence

import pytest

from fonti.domain import BlockKind, Hit, PageSpan
from fonti.generation.citations import (
    ABSTAIN_MESSAGE,
    align,
    build_answer,
    is_refusal,
    parse_claims,
)

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


@pytest.mark.parametrize(
    "output",
    [
        "Le fonti fornite non specificano il numero di disoccupati [1].",
        "Il documento non fornisce il nome dell'amministratore. [1][2]",
        "Nei passaggi non è indicato il costo della caldaia [2].",
        "La Costituzione non specifica una durata precisa per il mandato. [1][4]",
    ],
)
def test_soft_refusals_become_abstentions(output: str) -> None:
    assert build_answer("q", output, hits(), pages, 0.3).abstained


def test_answers_with_negations_are_not_refusals() -> None:
    assert not is_refusal("La disposizione non trova applicazione ai documenti informatici [1].")
    assert not is_refusal("Il conduttore non può sublocare l'immobile [1].")


def test_semantic_similarity_breaks_lexical_ties() -> None:
    source = (
        "Il giorno 14 marzo si riunisce l'assemblea. Sono presenti 14 condomini su 20. "
        "L'assemblea nomina presidente Laura Ferri."
    )

    def prefer_last(claim: str, sentences: Sequence[str]) -> list[float]:
        return [0.1, 0.1, 0.9]

    claim = "Laura Ferri presiede l'assemblea del 14 marzo"
    lexical = align(claim, source)
    semantic = align(claim, source, prefer_last)

    assert lexical is not None and semantic is not None
    assert source[lexical.start : lexical.end] == "Il giorno 14 marzo si riunisce l'assemblea."
    assert source[semantic.start : semantic.end] == "L'assemblea nomina presidente Laura Ferri."


def test_thinking_and_invalid_markers_are_removed_from_the_text() -> None:
    output = "<think>calcolo...</think>Le rate mensili sono di 800 euro [1][5]."

    result = build_answer("q", output, hits(), pages, 0.3)

    assert result.text == "Le rate mensili sono di 800 euro [1]."


def test_unsupported_sentences_lose_their_markers() -> None:
    output = (
        "Si pagano dodici rate mensili di 800 euro [1, 2]. "
        "Il conduttore versa un deposito [1]. Il canone è di 9.600 euro all'anno [1]."
    )

    result = build_answer("Quanto si paga?", output, hits(), pages, 0.3)

    assert result.text == (
        "Si pagano dodici rate mensili di 800 euro [1]. "
        "Il conduttore versa un deposito. Il canone è di 9.600 euro all'anno [1]."
    )
    assert {c.number for c in result.citations} == {1}


def test_citations_are_numbered_without_gaps() -> None:
    sources = [hits()[1], hits()[0]]  # deposit first, rent second
    output = "La Luna è lontana [1]. Si pagano dodici rate mensili di 800 euro [2]."

    result = build_answer("Quanto si paga?", output, sources, pages, 0.3)

    assert result.text == "La Luna è lontana. Si pagano dodici rate mensili di 800 euro [1]."
    assert [c.number for c in result.citations] == [1]
    assert result.citations[0].section == "Art. 3 - Canone"
