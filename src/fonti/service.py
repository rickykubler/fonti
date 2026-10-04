"""Application service: the single entry point used by the CLI, the web UI and evaluation."""

import hashlib
import logging
import shutil
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import TracebackType

import numpy as np
from numpy.typing import NDArray

from fonti.config import Settings
from fonti.domain import Answer, Chunk, DocumentInfo, Hit
from fonti.errors import FontiError
from fonti.generation.citations import abstain, build_answer
from fonti.generation.llm import ChatClient, create_chat_client
from fonti.generation.prompts import build_messages
from fonti.index.store import NewDocument, Store
from fonti.index.text import index_terms
from fonti.ingest.chunking import CHUNKER_VERSION, chunk_document
from fonti.ingest.parsers import SUPPORTED_SUFFIXES, ParseError, parse_file
from fonti.ml.embedder import Embedder, create_embedder
from fonti.ml.hub import pull
from fonti.retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)

_NO_TEXT_MESSAGE = "nessun testo estratto: potrebbe essere una scansione da leggere con l'OCR"


class IngestStatus(StrEnum):
    ADDED = "added"
    UPDATED = "updated"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class IngestResult:
    path: Path
    status: IngestStatus
    doc_id: str | None = None
    chunks: int = 0
    message: str = ""


class DocumentLookupError(FontiError, LookupError):
    """No document, or more than one, matches the given id prefix."""


@dataclass(frozen=True, slots=True)
class _Prepared:
    document: NewDocument
    chunks: tuple[Chunk, ...]
    terms: list[str]
    vectors: NDArray[np.float32]


class Fonti:
    def __init__(
        self,
        settings: Settings,
        *,
        embedder: Embedder | None = None,
        chat: ChatClient | None = None,
    ) -> None:
        self.settings = settings
        self.store = Store(settings.data_dir / "index.sqlite3")
        self._embedder = embedder
        self._chat = chat
        self._retriever: HybridRetriever | None = None

    def close(self) -> None:
        self.store.close()

    def __enter__(self) -> "Fonti":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = create_embedder(self.settings.embedding, offline=self.settings.offline)
        return self._embedder

    @property
    def chat(self) -> ChatClient:
        if self._chat is None:
            self._chat = create_chat_client(self.settings.llm)
        return self._chat

    @property
    def files_dir(self) -> Path:
        """Copies of the indexed files, named by content hash: citations always point to the
        exact version that was indexed."""
        return self.settings.data_dir / "files"

    def model_names(self) -> list[tuple[str, str | None]]:
        """Hugging Face models (name, revision) used by the current settings."""
        embedding = self.settings.embedding
        if embedding.model.startswith("hashing"):
            return []
        return [(embedding.model, embedding.revision)]

    def pull_models(self) -> list[Path]:
        """Download the models in use, so later runs never need the network."""
        return pull(self.model_names())

    def stored_file(self, doc_id: str) -> Path | None:
        suffix = self.store.document_suffix(doc_id)
        return None if suffix is None else self.files_dir / f"{doc_id}{suffix}"

    # --- documents ------------------------------------------------------------------------

    def ingest(self, paths: Iterable[Path]) -> Iterator[IngestResult]:
        """Index files and folders (recursively); already indexed files are skipped."""
        self.store.ensure_settings(self._index_settings())
        for path in _expand(paths):
            yield self._ingest_file(path)

    def reindex(self) -> Iterator[IngestResult]:
        """Rebuild every document with the current settings, e.g. after changing the
        embedding model. Safe to interrupt and run again."""
        for info in self.store.list_documents():
            stored = self.stored_file(info.id)
            if stored is None or not stored.is_file():
                yield IngestResult(
                    Path(info.filename), IngestStatus.FAILED, info.id, 0, "file mancante"
                )
                continue
            try:
                prepared = self._prepare(stored, info.id, info.filename)
            except ParseError as exc:
                yield IngestResult(Path(info.filename), IngestStatus.FAILED, info.id, 0, str(exc))
                continue
            self.store.replace_document(
                prepared.document, prepared.chunks, prepared.terms, prepared.vectors
            )
            yield IngestResult(
                Path(info.filename), IngestStatus.UPDATED, info.id, len(prepared.chunks)
            )
        self.store.force_settings(self._index_settings())

    def documents(self) -> list[DocumentInfo]:
        return self.store.list_documents()

    def find_document(self, id_prefix: str) -> DocumentInfo:
        matches = self.store.find_documents(id_prefix)
        if not matches:
            raise DocumentLookupError(f"Nessun documento con id che inizia per {id_prefix!r}")
        if len(matches) > 1:
            raise DocumentLookupError(f"Più documenti hanno id che inizia per {id_prefix!r}")
        return matches[0]

    def remove(self, id_prefix: str) -> DocumentInfo:
        info = self.find_document(id_prefix)
        stored = self.stored_file(info.id)
        self.store.remove_document(info.id)
        if stored is not None:
            stored.unlink(missing_ok=True)
        return info

    # --- retrieval ------------------------------------------------------------------------

    def search(self, question: str, limit: int | None = None) -> list[Hit]:
        self.store.check_settings({"embedder": self.embedder.model_id})
        if self._retriever is None:
            self._retriever = HybridRetriever(self.store, self.embedder, self.settings.retrieval)
        return self._retriever.search(question, limit)

    def ask(self, question: str) -> Answer:
        """Answer from the indexed documents with verified citations, or abstain."""
        sources = self.search(question)[: self.settings.retrieval.final_k]
        if not sources:
            return abstain(question, sources)
        output = self.chat.complete(build_messages(question, sources))
        return build_answer(
            question,
            output,
            sources,
            self.store.page_spans,
            self.settings.citations.min_support,
        )

    # --- internals ------------------------------------------------------------------------

    def _index_settings(self) -> dict[str, str]:
        chunking = self.settings.chunking
        return {
            "embedder": self.embedder.model_id,
            "chunker": f"{CHUNKER_VERSION}:{chunking.max_chars}:{chunking.overlap_chars}",
        }

    def _ingest_file(self, path: Path) -> IngestResult:
        try:
            doc_id = _sha256(path)
            if self.store.has_document(doc_id):
                return IngestResult(path, IngestStatus.SKIPPED, doc_id, message="già indicizzato")
            prepared = self._prepare(path, doc_id, path.name)
            if not prepared.chunks:
                return IngestResult(path, IngestStatus.FAILED, doc_id, message=_NO_TEXT_MESSAGE)
            stored = self.files_dir / f"{doc_id}{prepared.document.suffix}"
            stored.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, stored)
            try:
                self.store.add_document(
                    prepared.document, prepared.chunks, prepared.terms, prepared.vectors
                )
            except BaseException:
                stored.unlink(missing_ok=True)
                raise
        except (ParseError, OSError) as exc:
            return IngestResult(path, IngestStatus.FAILED, message=str(exc))
        logger.info("Indexed %s: %d chunks", path.name, len(prepared.chunks))
        return IngestResult(path, IngestStatus.ADDED, doc_id, len(prepared.chunks))

    def _prepare(self, path: Path, doc_id: str, filename: str) -> _Prepared:
        parsed = parse_file(path)
        chunked = chunk_document(parsed, self.settings.chunking)
        indexed_texts = [_indexed_text(chunk) for chunk in chunked.chunks]
        vectors = self.embedder.embed_documents(indexed_texts)
        title = parsed.title or next(
            (c.section.split(" › ")[0] for c in chunked.chunks if c.section), None
        )
        document = NewDocument(
            id=doc_id,
            filename=filename,
            title=title,
            suffix=path.suffix.lower(),
            page_count=parsed.page_count,
            parser=parsed.parser,
            text=chunked.text,
            pages=chunked.pages,
        )
        return _Prepared(document, chunked.chunks, [index_terms(t) for t in indexed_texts], vectors)


def _indexed_text(chunk: Chunk) -> str:
    """Text used for embeddings and keyword search: the section path adds context."""
    return f"{chunk.context}\n\n{chunk.text}" if chunk.context else chunk.text


def _expand(paths: Iterable[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(
                p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
            )
        else:
            yield path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
