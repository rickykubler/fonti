"""Golden datasets: questions with expected answers and evidence quotes.

A dataset (`eval/datasets/<name>.toml`) names the corpus documents to index and the questions
file. Evidence is identified by document, page and a verbatim quote, never by chunk id, so the
same questions keep working when parsing or chunking change. `aliases` reuse questions on other
versions of a document, e.g. its synthetic scan.
"""

import json
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fonti.config import ChunkingSettings
from fonti.evaluation.corpus import Corpus, EvaluationError
from fonti.evaluation.text import normalize
from fonti.ingest.chunking import chunk_document
from fonti.ingest.parsers import parse_file


@dataclass(frozen=True, slots=True)
class Location:
    doc: str  # corpus document id
    page: int
    quote: str


@dataclass(frozen=True, slots=True)
class Evidence:
    """A fact the answer needs. The same fact may appear in several places (a figure in the
    text and in a table): finding any of its locations is enough."""

    doc: str
    page: int
    quote: str
    alternatives: tuple[Location, ...] = ()

    @property
    def locations(self) -> tuple[Location, ...]:
        return (Location(self.doc, self.page, self.quote), *self.alternatives)


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    question: str
    answerable: bool
    answer: str = ""
    evidence: tuple[Evidence, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Dataset:
    name: str
    description: str
    documents: tuple[str, ...]
    questions: tuple[Question, ...]
    aliases: Mapping[str, str] = field(default_factory=dict)


def load_dataset(datasets_dir: Path, name: str) -> Dataset:
    path = datasets_dir / f"{name}.toml"
    if not path.is_file():
        raise EvaluationError(f"Dataset non trovato: {path}")
    with path.open("rb") as f:
        config: dict[str, Any] = tomllib.load(f)
    aliases: dict[str, str] = config.get("aliases", {})
    documents = tuple(config["documents"])
    questions = []
    for question in load_questions(datasets_dir / config["questions"]):
        evidence = tuple(_alias(item, aliases, documents) for item in question.evidence)
        if all(e.doc in documents for e in evidence):
            questions.append(
                Question(
                    question.id,
                    question.question,
                    question.answerable,
                    question.answer,
                    evidence,
                    question.tags,
                )
            )
    return Dataset(name, config.get("description", ""), documents, tuple(questions), aliases)


def check_dataset(dataset: Dataset, corpus: Corpus) -> list[str]:
    """Problems with the gold evidence: quotes that are not in the document text extracted by
    the fast parser, or that are on another page. Scanned documents cannot be checked."""
    problems = []
    pages_by_doc: dict[str, dict[int, str]] = {}
    for question in dataset.questions:
        for location in (loc for item in question.evidence for loc in item.locations):
            if location.doc not in corpus.documents:
                problems.append(f"{question.id}: documento sconosciuto {location.doc}")
                continue
            if corpus.documents[location.doc].scan_of is not None:
                continue
            if location.doc not in pages_by_doc:
                pages_by_doc[location.doc] = _page_texts(corpus.path(location.doc))
            quote = normalize(location.quote)
            found = [page for page, text in pages_by_doc[location.doc].items() if quote in text]
            if not found:
                problems.append(
                    f"{question.id}: citazione non trovata in {location.doc}: «{location.quote}»"
                )
            elif location.page not in found:
                problems.append(
                    f"{question.id}: citazione a pagina {found}, non a pagina {location.page}"
                )
    return problems


def _alias(item: Evidence, aliases: Mapping[str, str], documents: tuple[str, ...]) -> Evidence:
    """Map evidence onto the documents of a dataset (e.g. the scan of a document)."""
    alternatives = tuple(
        Location(aliases.get(alt.doc, alt.doc), alt.page, alt.quote)
        for alt in item.alternatives
        if aliases.get(alt.doc, alt.doc) in documents
    )
    return Evidence(aliases.get(item.doc, item.doc), item.page, item.quote, alternatives)


def _page_texts(path: Path) -> dict[int, str]:
    chunked = chunk_document(parse_file(path), ChunkingSettings())
    return {page.page: normalize(chunked.text[page.start : page.end]) for page in chunked.pages}


def load_questions(path: Path) -> list[Question]:
    questions = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            question = Question(
                id=record["id"],
                question=record["question"],
                answerable=record["answerable"],
                answer=record.get("answer", ""),
                evidence=tuple(_evidence(e) for e in record.get("evidence", [])),
                tags=tuple(record.get("tags", [])),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise EvaluationError(f"{path.name}, riga {number}: record non valido ({exc})") from exc
        if question.id in seen:
            raise EvaluationError(f"{path.name}, riga {number}: id duplicato {question.id}")
        if question.answerable != bool(question.evidence):
            raise EvaluationError(
                f"{question.id}: le domande rispondibili (e solo quelle) devono avere evidenze"
            )
        seen.add(question.id)
        questions.append(question)
    return questions


def _evidence(record: dict[str, Any]) -> Evidence:
    alternatives = tuple(Location(**alt) for alt in record.get("alternatives", []))
    return Evidence(record["doc"], record["page"], record["quote"], alternatives)
