"""Evaluation runner: index a dataset's corpus with the given settings, ask every question and
collect retrieval, generation and timing metrics."""

import hashlib
import json
import logging
import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fonti.config import Settings
from fonti.domain import Answer
from fonti.evaluation.corpus import Corpus, EvaluationError
from fonti.evaluation.dataset import Dataset, Question
from fonti.evaluation.judge import Judge
from fonti.evaluation.metrics import (
    citation_page_precision,
    cites_evidence,
    evidence_ranks,
    recall_at,
    reciprocal_rank,
)
from fonti.generation.citations import parse_claims
from fonti.ingest.chunking import CHUNKER_VERSION
from fonti.ingest.parsers import PARSER_VERSION
from fonti.service import Fonti, IngestStatus

logger = logging.getLogger(__name__)

RECALL_CUTOFFS = (1, 3, 5, 10)


@dataclass
class QuestionResult:
    id: str
    question: str
    answerable: bool
    tags: list[str]
    ranks: list[int | None]  # evidence ranks in the final ranking
    candidate_ranks: list[int | None]  # evidence ranks before reranking
    retrieval_s: float
    answer: str | None = None
    abstained: bool | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    page_precision: float | None = None
    cites_evidence: bool | None = None
    grounded: float | None = None
    correct: float | None = None
    generation_s: float | None = None


@dataclass
class RunResult:
    dataset: str
    label: str
    created_at: str
    settings: dict[str, Any]
    judge_model: str | None
    ingest: dict[str, Any]
    questions: list[QuestionResult]

    def summary(self) -> dict[str, float | None]:
        answerable = [q for q in self.questions if q.answerable]
        unanswerable = [q for q in self.questions if not q.answerable]
        summary: dict[str, float | None] = {}
        for k in RECALL_CUTOFFS:
            summary[f"recall@{k}"] = _mean(recall_at(q.ranks, k) for q in answerable)
        summary["recall@candidates"] = _mean(recall_at(q.candidate_ranks) for q in answerable)
        summary["mrr@10"] = _mean(reciprocal_rank(q.ranks) for q in answerable)
        generated = [q for q in self.questions if q.abstained is not None]
        if generated:
            answered = [q for q in answerable if q.abstained is False]
            summary["correct_refusals"] = _mean(bool(q.abstained) for q in unanswerable)
            summary["false_refusals"] = _mean(bool(q.abstained) for q in answerable)
            summary["page_precision"] = _mean(
                q.page_precision for q in answered if q.page_precision is not None
            )
            summary["cites_evidence"] = _mean(bool(q.cites_evidence) for q in answered)
            summary["groundedness"] = _mean(q.grounded for q in generated if q.grounded is not None)
            summary["correctness"] = _mean(q.correct for q in answered if q.correct is not None)
            summary["generation_p50_s"] = _percentile(
                [q.generation_s or 0.0 for q in generated], 50
            )
            summary["generation_p95_s"] = _percentile(
                [q.generation_s or 0.0 for q in generated], 95
            )
        summary["retrieval_p50_s"] = _percentile([q.retrieval_s for q in self.questions], 50)
        summary["retrieval_p95_s"] = _percentile([q.retrieval_s for q in self.questions], 95)
        return summary

    def to_json(self) -> str:
        return json.dumps({"summary": self.summary(), **asdict(self)}, ensure_ascii=False, indent=2)


def run(
    dataset: Dataset,
    corpus: Corpus,
    settings: Settings,
    *,
    work_dir: Path,
    label: str,
    generate: bool = True,
    judge: Judge | None = None,
    progress: Callable[[str], None] = lambda _: None,
    fonti_factory: Callable[[Settings], Fonti] = Fonti,
) -> RunResult:
    """Evaluate `settings` on `dataset`. The index lives in `work_dir`, keyed by the settings
    that define it, so runs that only change retrieval or generation reuse it."""
    for doc_id in dataset.documents:
        if not corpus.path(doc_id).is_file():
            raise EvaluationError(
                f"Documento {doc_id} mancante: esegui `fonti eval corpus` per prepararlo."
            )
    data_dir = work_dir / f"{dataset.name}-{index_fingerprint(settings)}"
    run_settings = settings.model_copy(update={"data_dir": data_dir})
    with fonti_factory(run_settings) as fonti:
        corpus_of, ingest = _ingest(fonti, corpus, dataset.documents, progress)
        results = []
        for number, question in enumerate(dataset.questions, start=1):
            progress(f"[{number}/{len(dataset.questions)}] {question.id}")
            results.append(_evaluate(fonti, question, corpus_of.get, generate, judge))
    return RunResult(
        dataset=dataset.name,
        label=label,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        settings=describe_settings(run_settings),
        judge_model=judge.model_id if judge else None,
        ingest=ingest,
        questions=results,
    )


def index_fingerprint(settings: Settings) -> str:
    """Short hash of the settings that define the index."""
    defining = {
        "versions": [PARSER_VERSION, CHUNKER_VERSION],
        "parser": settings.parser.model_dump(),
        "chunking": settings.chunking.model_dump(),
        "embedding": settings.embedding.model_dump(exclude={"device", "batch_size"}),
        "keywords": settings.retrieval.keyword_terms,
    }
    return hashlib.sha256(json.dumps(defining, sort_keys=True).encode()).hexdigest()[:10]


def describe_settings(settings: Settings) -> dict[str, Any]:
    described = settings.model_dump(mode="json", exclude={"data_dir"})
    described["llm"].pop("api_key", None)
    return described


def _ingest(
    fonti: Fonti, corpus: Corpus, documents: Sequence[str], progress: Callable[[str], None]
) -> tuple[dict[str, str], dict[str, Any]]:
    corpus_of: dict[str, str] = {}
    started = time.perf_counter()
    added_pages = 0
    for doc_id in documents:
        progress(f"indicizzazione {doc_id}")
        [result] = fonti.ingest([corpus.path(doc_id)])
        if result.status is IngestStatus.FAILED or result.doc_id is None:
            raise EvaluationError(f"Indicizzazione di {doc_id} fallita: {result.message}")
        corpus_of[result.doc_id] = doc_id
        if result.status is IngestStatus.ADDED:
            added_pages += fonti.find_document(result.doc_id).page_count
    seconds = time.perf_counter() - started
    documents_info = fonti.documents()
    return corpus_of, {
        "documents": len(documents_info),
        "pages": sum(d.page_count for d in documents_info),
        "chunks": sum(d.chunk_count for d in documents_info),
        "seconds": round(seconds, 2) if added_pages else None,
        "seconds_per_page": round(seconds / added_pages, 3) if added_pages else None,
    }


def _evaluate(
    fonti: Fonti,
    question: Question,
    doc_of: Callable[[str], str | None],
    generate: bool,
    judge: Judge | None,
) -> QuestionResult:
    started = time.perf_counter()
    retrieval = fonti.retrieve(question.question)
    result = QuestionResult(
        id=question.id,
        question=question.question,
        answerable=question.answerable,
        tags=list(question.tags),
        ranks=evidence_ranks(question.evidence, retrieval.ranked, doc_of),
        candidate_ranks=evidence_ranks(question.evidence, retrieval.candidates, doc_of),
        retrieval_s=round(time.perf_counter() - started, 3),
    )
    if not generate:
        return result
    started = time.perf_counter()
    answer = fonti.answer(retrieval)
    result.generation_s = round(time.perf_counter() - started, 3)
    result.answer = answer.text
    result.abstained = answer.abstained
    result.citations = [
        {"doc": doc_of(c.doc_id), "page": c.page, "passage": c.passage, "claim": c.claim}
        for c in answer.citations
    ]
    if question.answerable and not answer.abstained:
        result.page_precision = citation_page_precision(answer, question.evidence, doc_of)
        result.cites_evidence = cites_evidence(answer, question.evidence, doc_of)
    if judge is not None and not answer.abstained:
        result.grounded = _groundedness(judge, answer)
        if question.answerable:
            result.correct = judge.correct(question.question, question.answer, answer.text).score
    return result


def _groundedness(judge: Judge, answer: Answer) -> float:
    """Mean verdict over the answer's sentences; a sentence without citations scores 0."""
    claims = parse_claims(answer.text, len(answer.sources))
    scores = []
    for claim in claims:
        passages = [c.passage for c in answer.citations if c.claim == claim.text]
        scores.append(judge.grounded(claim.text, passages).score if passages else 0.0)
    return _mean(scores) or 0.0


def _mean(values: Any) -> float | None:
    collected = [float(v) for v in values]
    return round(statistics.fmean(collected), 4) if collected else None


def _percentile(values: Sequence[float], percent: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(percent / 100 * (len(ordered) - 1)))
    return round(ordered[index], 3)
