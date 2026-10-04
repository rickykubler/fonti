"""Domain types shared by ingestion, storage, retrieval and generation."""

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class BlockKind(StrEnum):
    HEADING = "heading"
    TEXT = "text"
    TABLE = "table"


@dataclass(frozen=True, slots=True)
class Block:
    """A unit of a parsed document, in reading order."""

    kind: BlockKind
    text: str
    page: int  # 1-based
    level: int = 0  # heading depth, 1 = top level; 0 for non-headings


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    blocks: tuple[Block, ...]
    page_count: int
    title: str | None = None
    parser: str = "fast"
    ocr_pages: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class PageSpan:
    """Character range of a page inside the document text."""

    page: int
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Chunk:
    """A slice of the document text: `text == document_text[start:end]`."""

    ordinal: int
    start: int
    end: int
    text: str
    page_start: int
    page_end: int
    section: str  # heading path, e.g. "Parte I › Titolo I › Art. 13"
    kind: BlockKind
    context: str = ""  # indexed together with the text, never cited


@dataclass(frozen=True, slots=True)
class DocumentInfo:
    id: str
    filename: str
    title: str | None
    page_count: int
    chunk_count: int
    parser: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Hit:
    """A retrieved chunk with its document metadata and a retrieval score."""

    chunk_id: int
    doc_id: str
    filename: str
    title: str | None
    text: str
    start: int
    end: int
    page_start: int
    page_end: int
    section: str
    kind: BlockKind
    score: float = 0.0


@dataclass(frozen=True, slots=True)
class Citation:
    number: int  # source number as cited in the answer, e.g. 1 for "[1]"
    doc_id: str
    filename: str
    title: str | None
    page: int
    section: str
    passage: str  # verbatim from the document, never generated
    start: int  # document-level offsets of the passage
    end: int
    support: float  # alignment score between the claim and the passage, in [0, 1]
    claim: str = ""  # the answer sentence this passage supports


@dataclass(frozen=True, slots=True)
class Retrieval:
    question: str
    candidates: tuple[Hit, ...]  # fused keyword + dense ranking, before reranking
    ranked: tuple[Hit, ...]  # the same candidates in final order (after reranking, if any)
    sources: tuple[Hit, ...]  # what the model will read: the top of `ranked`
    relevant: bool  # False when the best source is not relevant enough to answer


@dataclass(frozen=True, slots=True)
class Answer:
    question: str
    text: str
    citations: tuple[Citation, ...]
    abstained: bool
    sources: tuple[Hit, ...]  # passages given to the model, or the nearest ones when abstaining


def page_for_offset(pages: Sequence[PageSpan], offset: int) -> int:
    """Return the page containing `offset`; offsets between pages belong to the previous page."""
    if not pages:
        raise ValueError("document has no pages with text")
    starts = [page.start for page in pages]
    index = max(bisect_right(starts, offset) - 1, 0)
    return pages[index].page
