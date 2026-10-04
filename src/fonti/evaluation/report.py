"""Markdown and JSON reports of evaluation runs."""

import re
from collections import defaultdict
from pathlib import Path

from fonti.evaluation.metrics import recall_at, reciprocal_rank
from fonti.evaluation.runner import QuestionResult, RunResult

_LABELS = {
    "recall@1": "Recall@1",
    "recall@3": "Recall@3",
    "recall@5": "Recall@5",
    "recall@10": "Recall@10",
    "recall@candidates": "Recall nei candidati",
    "mrr@10": "MRR@10",
    "correct_refusals": "Rifiuti corretti (non rispondibili)",
    "false_refusals": "Falsi rifiuti (rispondibili)",
    "page_precision": "Pagine citate corrette",
    "cites_evidence": "Risposte che citano l'evidenza",
    "groundedness": "Groundedness (giudice)",
    "correctness": "Correttezza (giudice)",
    "retrieval_p50_s": "Retrieval p50 (s)",
    "retrieval_p95_s": "Retrieval p95 (s)",
    "generation_p50_s": "Generazione p50 (s)",
    "generation_p95_s": "Generazione p95 (s)",
}


def write_report(result: RunResult, reports_dir: Path) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{result.created_at[:10]}_{_slug(result.label)}_{result.dataset}"
    markdown = reports_dir / f"{stem}.md"
    data = reports_dir / f"{stem}.json"
    markdown.write_text(render_markdown(result), encoding="utf-8", newline="\n")
    data.write_text(result.to_json() + "\n", encoding="utf-8", newline="\n")
    return markdown, data


def render_markdown(result: RunResult) -> str:
    settings = result.settings
    llm = settings["llm"]
    lines = [
        f"# Valutazione: {result.label} ({result.dataset})",
        "",
        f"- Data: {result.created_at}",
        f"- Domande: {len(result.questions)} "
        f"({sum(q.answerable for q in result.questions)} rispondibili)",
        f"- Parser: {settings['parser']['mode']}; chunk max {settings['chunking']['max_chars']} "
        f"caratteri; keyword: {settings['retrieval']['keyword_terms']}",
        f"- Embedding: {settings['embedding']['model']}",
        f"- Reranker: {_reranker(settings)}",
        f"- LLM: {llm['model']} ({llm['provider']})",
        f"- Giudice: {result.judge_model or 'nessuno'}",
        f"- Indice: {result.ingest['documents']} documenti, {result.ingest['pages']} pagine, "
        f"{result.ingest['chunks']} chunk",
        "",
        "## Metriche",
        "",
        "| Metrica | Valore |",
        "|---|---|",
    ]
    for key, value in result.summary().items():
        lines.append(f"| {_LABELS.get(key, key)} | {_format(value)} |")
    lines += [
        "",
        "## Per tipo di domanda",
        "",
        "| Tag | Domande | Recall@5 | MRR@10 |",
        "|---|---|---|---|",
    ]
    by_tag: dict[str, list[QuestionResult]] = defaultdict(list)
    for question in result.questions:
        for tag in question.tags:
            by_tag[tag].append(question)
    for tag, questions in sorted(by_tag.items()):
        answerable = [q for q in questions if q.answerable]
        recall = _average([recall_at(q.ranks, 5) for q in answerable])
        mrr = _average([reciprocal_rank(q.ranks) for q in answerable])
        lines.append(f"| {tag} | {len(questions)} | {_format(recall)} | {_format(mrr)} |")
    lines += [
        "",
        "## Domande",
        "",
        "| Id | Rank evidenze | Esito | Pagine ok | Grounded | Corretta |",
        "|---|---|---|---|---|---|",
    ]
    for question in result.questions:
        ranks = ", ".join("—" if r is None else str(r) for r in question.ranks) or "n/a"
        lines.append(
            f"| {question.id} | {ranks} | {_outcome(question)} | "
            f"{_format(question.page_precision)} | {_format(question.grounded)} | "
            f"{_format(question.correct)} |"
        )
    return "\n".join(lines) + "\n"


def _outcome(question: QuestionResult) -> str:
    if question.abstained is None:
        return "solo retrieval"
    if question.answerable:
        return "rifiuto errato" if question.abstained else "risposta"
    return "rifiuto corretto" if question.abstained else "risposta non dovuta"


def _reranker(settings: dict[str, object]) -> str:
    rerank = settings.get("rerank")
    if isinstance(rerank, dict) and rerank.get("enabled"):
        return str(rerank.get("model"))
    return "nessuno"


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _format(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}".rstrip("0").rstrip(".") if value else "0"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "run"
