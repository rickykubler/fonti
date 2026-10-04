"""Turn the model output into an answer with verifiable citations, or into an abstention.

Citation passages are never generated: for every sentence of the answer, the supporting
passage is the sentence (or two) of the cited source that best matches it, by term overlap
and, when available, by embedding similarity.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from fonti.domain import Answer, Citation, Hit, PageSpan, page_for_offset
from fonti.generation.prompts import NOT_FOUND
from fonti.index.text import content_terms
from fonti.ingest.text import split_sentences
from fonti.italian import fold_accents

ABSTAIN_MESSAGE = "Non lo so: nei documenti indicizzati non trovo fonti sufficienti per rispondere."
NEAREST_SOURCES = 3

# similarity(claim, sentences) -> one score in [-1, 1] per sentence
Similarity = Callable[[str, Sequence[str]], Sequence[float]]

_MARKER_RE = re.compile(r"\s*\[(\d+(?:\s*[,;]\s*\d+)*)\]")
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_MIN_EXTENSION_GAIN = 0.2
# Answers that say the sources do not contain the information, instead of NON_TROVATO.
_REFUSAL_SUBJECT = re.compile(
    r"\b(fonti?|document[oi]|test[oi]|passagg[io]+|informazioni|costituzione|contratt[oi]|"
    r"verbal[ei]|manual[ei]|regolament[oi]|legge|norm[ae]|linee guida|comunicat[oi])\b"
)
_REFUSAL_VERB = re.compile(
    r"\bnon (?:(?:e|sono|viene|vengono) (?:specificat|indicat|riportat|menzionat|present|"
    r"disponibil|fornit|chiarit)|specifica|indica|riporta|menziona|fornisc|contien|precisa|"
    r"trovo|ho trovato|(?:e )?possibile (?:determinare|stabilire|rispondere))"
)


@dataclass(frozen=True, slots=True)
class Claim:
    text: str  # answer sentence without citation markers
    sources: tuple[int, ...]  # cited source numbers that exist (1-based)


@dataclass(frozen=True, slots=True)
class Alignment:
    start: int  # offsets inside the source text
    end: int
    support: float  # share of the claim's content terms found in the passage


def abstain(question: str, sources: Sequence[Hit]) -> Answer:
    return Answer(question, ABSTAIN_MESSAGE, (), True, tuple(sources[:NEAREST_SOURCES]))


def build_answer(
    question: str,
    output: str,
    sources: Sequence[Hit],
    page_spans: Callable[[str], Sequence[PageSpan]],
    min_support: float,
    similarity: Similarity | None = None,
) -> Answer:
    text = _THINK_RE.sub("", output).strip()
    if not text or NOT_FOUND in text or is_refusal(text):
        return abstain(question, sources)
    citations: dict[tuple[int, int, int], Citation] = {}
    for claim in parse_claims(text, len(sources)):
        for number in claim.sources:
            hit = sources[number - 1]
            alignment = align(claim.text, hit.text, similarity)
            if alignment is None or alignment.support < min_support:
                continue
            start, end = hit.start + alignment.start, hit.start + alignment.end
            key = (number, start, end)
            if key in citations and citations[key].support >= alignment.support:
                continue
            citations[key] = Citation(
                number=number,
                doc_id=hit.doc_id,
                filename=hit.filename,
                title=hit.title,
                page=page_for_offset(page_spans(hit.doc_id), start),
                section=hit.section,
                passage=hit.text[alignment.start : alignment.end],
                start=start,
                end=end,
                support=alignment.support,
                claim=claim.text,
            )
    if not citations:
        return abstain(question, sources)
    ordered = sorted(citations.values(), key=lambda c: (c.number, c.start))
    return Answer(
        question, _drop_invalid_markers(text, len(sources)), tuple(ordered), False, tuple(sources)
    )


def is_refusal(text: str) -> bool:
    """A short answer saying that the sources lack the information ("Le fonti non
    specificano..."), which small models write instead of NON_TROVATO."""
    sentences = [text[start:end] for start, end in split_sentences(text)]
    if len(sentences) > 2:
        return False
    return any(
        _REFUSAL_SUBJECT.search(folded) and _REFUSAL_VERB.search(folded)
        for folded in (fold_accents(sentence.lower()) for sentence in sentences)
    )


def parse_claims(answer: str, source_count: int) -> list[Claim]:
    claims = []
    for start, end in split_sentences(answer):
        sentence = answer[start:end]
        numbers = [
            int(number)
            for group in _MARKER_RE.findall(sentence)
            for number in re.split(r"\s*[,;]\s*", group)
        ]
        valid = tuple(dict.fromkeys(n for n in numbers if 1 <= n <= source_count))
        claims.append(Claim(_MARKER_RE.sub("", sentence).strip(), valid))
    return claims


def align(claim: str, source: str, similarity: Similarity | None = None) -> Alignment | None:
    """The sentence of `source` that best matches the claim, extended to a neighbouring
    sentence when that adds term coverage. The support is the share of the claim's content
    terms found in the passage; embedding similarity, when given, only helps choose."""
    wanted = content_terms(claim)
    sentences = split_sentences(source)
    if not wanted or not sentences:
        return None
    terms = [content_terms(source[start:end]) for start, end in sentences]

    def coverage(found: set[str]) -> float:
        return len(wanted & found) / len(wanted)

    semantic = (
        list(similarity(claim, [source[s:e] for s, e in sentences]))
        if similarity is not None
        else [0.0] * len(sentences)
    )
    best = max(range(len(sentences)), key=lambda i: (coverage(terms[i]) + semantic[i], -i))
    start, end = sentences[best]
    support = coverage(terms[best])
    for neighbour in (best - 1, best + 1):
        if 0 <= neighbour < len(sentences):
            extended = coverage(terms[best] | terms[neighbour])
            if extended - support >= _MIN_EXTENSION_GAIN:
                start = min(start, sentences[neighbour][0])
                end = max(end, sentences[neighbour][1])
                support = extended
                terms[best] = terms[best] | terms[neighbour]
    return Alignment(start, end, support)


def _drop_invalid_markers(text: str, source_count: int) -> str:
    def keep_valid(match: re.Match[str]) -> str:
        numbers = [int(n) for n in re.split(r"\s*[,;]\s*", match.group(1))]
        return match.group(0) if all(1 <= n <= source_count for n in numbers) else ""

    return _MARKER_RE.sub(keep_valid, text)
