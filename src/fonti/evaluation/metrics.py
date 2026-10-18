"""Evaluation metrics. Pure functions over retrieved passages, answers and gold evidence."""

import re
from collections.abc import Callable, Sequence

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from fonti.domain import Answer, Hit
from fonti.evaluation.dataset import Evidence
from fonti.evaluation.text import normalize

# A passage contains a quote when the quote matches one of its substrings at this level
# (100 = verbatim). The tolerance absorbs OCR errors and small parser differences.
QUOTE_MATCH = 90.0
_NUMBER_RE = re.compile(r"\d(?:[\d.,]*\d)?")


def quote_score(quote: str, text: str) -> float:
    """How well `quote` matches the best substring of `text`, from 0 to 100."""
    needle, haystack = normalize(quote), normalize(text)
    if not needle:
        return 0.0
    if needle in haystack:
        return 100.0
    # Fuzzy matching cannot tell "5,8" from "5,2": every number of the quote must be there.
    if not _numbers(needle) <= _numbers(haystack):
        return 0.0
    return float(fuzz.partial_ratio(needle, haystack))


def _numbers(text: str) -> set[str]:
    """Numbers without separators, so that "800,00" and "800.00" are the same number."""
    return {re.sub(r"[.,]", "", number) for number in _NUMBER_RE.findall(text)}


def evidence_ranks(
    evidence: Sequence[Evidence], hits: Sequence[Hit], doc_of: Callable[[str], str | None]
) -> list[int | None]:
    """For every evidence item, the 1-based rank of the first hit that contains any of its
    locations: same document, a page range that includes the location's page and the quote.
    The page keeps a restatement elsewhere (an EU recital repeating an article) from counting."""
    ranks: list[int | None] = []
    for item in evidence:
        rank = next(
            (
                position
                for position, hit in enumerate(hits, start=1)
                if any(
                    doc_of(hit.doc_id) == location.doc
                    and hit.page_start <= location.page <= hit.page_end
                    and quote_score(location.quote, hit.text) >= QUOTE_MATCH
                    for location in item.locations
                )
            ),
            None,
        )
        ranks.append(rank)
    return ranks


def recall_at(ranks: Sequence[int | None], k: int | None = None) -> float:
    """Share of evidence found within the first `k` results (anywhere when `k` is None)."""
    if not ranks:
        return 0.0
    found = sum(1 for rank in ranks if rank is not None and (k is None or rank <= k))
    return found / len(ranks)


def reciprocal_rank(ranks: Sequence[int | None], cutoff: int = 10) -> float:
    found = [rank for rank in ranks if rank is not None and rank <= cutoff]
    return 1.0 / min(found) if found else 0.0


def citation_page_precision(
    answer: Answer, evidence: Sequence[Evidence], doc_of: Callable[[str], str | None]
) -> float | None:
    """Share of citations that point to a page holding gold evidence (None if no citations)."""
    if not answer.citations:
        return None
    gold = {(location.doc, location.page) for item in evidence for location in item.locations}
    hits = sum(1 for c in answer.citations if (doc_of(c.doc_id), c.page) in gold)
    return hits / len(answer.citations)


def cites_evidence(
    answer: Answer, evidence: Sequence[Evidence], doc_of: Callable[[str], str | None]
) -> bool:
    """At least one cited passage overlaps a gold quote."""
    return any(
        doc_of(citation.doc_id) == location.doc
        and (
            quote_score(citation.passage, location.quote) >= QUOTE_MATCH
            or quote_score(location.quote, citation.passage) >= QUOTE_MATCH
        )
        for citation in answer.citations
        for item in evidence
        for location in item.locations
    )


def character_error_rate(predicted: str, reference: str) -> float:
    """Edit distance between normalized texts divided by the reference length."""
    reference, predicted = normalize(reference), normalize(predicted)
    if not reference:
        return 0.0 if not predicted else 1.0
    return float(Levenshtein.distance(predicted, reference)) / len(reference)
