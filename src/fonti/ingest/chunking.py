"""Structure-aware chunking. Every chunk is an exact slice of the document text, so citations
can always point back to verbatim passages and pages."""

from collections.abc import Sequence
from dataclasses import dataclass

from fonti.config import ChunkingSettings
from fonti.domain import Block, BlockKind, Chunk, PageSpan, ParsedDocument, page_for_offset
from fonti.ingest.text import split_sentences

CHUNKER_VERSION = "1"
BLOCK_SEPARATOR = "\n\n"
SECTION_SEPARATOR = " › "
_MAX_LABEL_CHARS = 80


@dataclass(frozen=True, slots=True)
class ChunkedDocument:
    text: str
    pages: tuple[PageSpan, ...]
    chunks: tuple[Chunk, ...]


def chunk_document(parsed: ParsedDocument, settings: ChunkingSettings) -> ChunkedDocument:
    blocks = parsed.blocks
    text, spans = _assemble(blocks)
    pages = _page_spans(blocks, spans)
    chunks: list[Chunk] = []
    for section, indices in _section_groups(blocks):
        for start, end, kind in _pack(blocks, spans, indices, text, settings):
            header = _table_header(blocks, spans, indices, start) if kind is BlockKind.TABLE else ""
            chunks.append(
                Chunk(
                    ordinal=len(chunks),
                    start=start,
                    end=end,
                    text=text[start:end],
                    page_start=page_for_offset(pages, start),
                    page_end=page_for_offset(pages, end - 1),
                    section=section,
                    kind=kind,
                    context=f"{section}\n{header}".strip() if header else section,
                )
            )
    return ChunkedDocument(text, pages, tuple(chunks))


def _table_header(
    blocks: Sequence[Block], spans: Sequence[tuple[int, int]], indices: Sequence[int], start: int
) -> str:
    """The header rows of the table a chunk continues, so that a slice of rows stays readable
    ("Disoccupati 761 ..." needs its column names)."""
    for index in indices:
        block_start, block_end = spans[index]
        if blocks[index].kind is BlockKind.TABLE and block_start < start < block_end:
            lines = blocks[index].text.split("\n")
            separator = len(lines) > 1 and set(lines[1].replace("|", "").strip()) <= set("-: ")
            return "\n".join(lines[: 2 if separator else 1])
    return ""


def heading_label(text: str) -> str:
    label = " - ".join(part.strip() for part in text.split("\n") if part.strip())
    return label if len(label) <= _MAX_LABEL_CHARS else label[: _MAX_LABEL_CHARS - 1] + "…"


def _assemble(blocks: Sequence[Block]) -> tuple[str, list[tuple[int, int]]]:
    parts: list[str] = []
    spans: list[tuple[int, int]] = []
    offset = 0
    for block in blocks:
        if parts:
            parts.append(BLOCK_SEPARATOR)
            offset += len(BLOCK_SEPARATOR)
        parts.append(block.text)
        spans.append((offset, offset + len(block.text)))
        offset += len(block.text)
    return "".join(parts), spans


def _page_spans(blocks: Sequence[Block], spans: Sequence[tuple[int, int]]) -> tuple[PageSpan, ...]:
    ranges: dict[int, tuple[int, int]] = {}
    for block, (start, end) in zip(blocks, spans, strict=True):
        first, _ = ranges.get(block.page, (start, end))
        ranges[block.page] = (first, end)
    return tuple(PageSpan(page, start, end) for page, (start, end) in sorted(ranges.items()))


def _section_groups(blocks: Sequence[Block]) -> list[tuple[str, list[int]]]:
    """Split blocks into runs that share the same heading path; headings join the run they
    introduce, so every group is a contiguous range of blocks."""
    stack: list[tuple[int, str]] = []
    groups: list[tuple[str, list[int]]] = []
    pending: list[int] = []
    for index, block in enumerate(blocks):
        if block.kind is BlockKind.HEADING:
            while stack and stack[-1][0] >= block.level:
                stack.pop()
            stack.append((block.level, heading_label(block.text)))
            pending.append(index)
            continue
        section = SECTION_SEPARATOR.join(label for _, label in stack)
        if pending or not groups or groups[-1][0] != section:
            groups.append((section, [*pending, index]))
            pending = []
        else:
            groups[-1][1].append(index)
    if pending:
        if groups:
            groups[-1][1].extend(pending)
        else:
            groups.append((SECTION_SEPARATOR.join(label for _, label in stack), pending))
    return groups


def _pack(
    blocks: Sequence[Block],
    spans: Sequence[tuple[int, int]],
    indices: Sequence[int],
    text: str,
    settings: ChunkingSettings,
) -> list[tuple[int, int, BlockKind]]:
    """Pack consecutive blocks into windows of at most `max_chars`; split longer blocks by
    sentences. Tables are never mixed with prose; lone headings join the next window."""
    windows: list[tuple[int, int, BlockKind]] = []
    start: int | None = None  # current window
    end = 0
    has_content = False

    def flush() -> None:
        nonlocal start, has_content
        if start is not None and has_content:
            windows.append((start, end, BlockKind.TEXT))
            start = None
        has_content = False

    for index in indices:
        block = blocks[index]
        block_start, block_end = spans[index]
        if block.kind is BlockKind.TABLE or block_end - block_start > settings.max_chars:
            # Headings waiting for content are split together with this block.
            first = start if start is not None and not has_content else block_start
            flush()
            kind = block.kind if block.kind is BlockKind.TABLE else BlockKind.TEXT
            windows.extend((s, e, kind) for s, e in _split_long(text, first, block_end, settings))
            start = None
            continue
        if start is not None and has_content and block_end - start > settings.max_chars:
            flush()
        if start is None:
            start = block_start
        end = block_end
        has_content = has_content or block.kind is not BlockKind.HEADING
    if start is not None:
        has_content = True  # trailing headings: keep them rather than lose text
        flush()
    return windows


def _split_long(
    text: str, start: int, end: int, settings: ChunkingSettings
) -> list[tuple[int, int]]:
    if end - start <= settings.max_chars:
        return [(start, end)]
    sentences = [(start + s, start + e) for s, e in split_sentences(text[start:end])]
    sentences = [piece for s, e in sentences for piece in _hard_split(text, s, e, settings)]
    windows: list[tuple[int, int]] = []
    first = 0
    while first < len(sentences):
        last = first
        while (
            last + 1 < len(sentences)
            and sentences[last + 1][1] - sentences[first][0] <= settings.max_chars
        ):
            last += 1
        windows.append((sentences[first][0], sentences[last][1]))
        if last + 1 >= len(sentences):
            break
        # Start the next window a few sentences back, as long as the overlap fits.
        following = last + 1
        while (
            following - 1 > first
            and sentences[last][1] - sentences[following - 1][0] <= settings.overlap_chars
        ):
            following -= 1
        first = following
    return windows


def _hard_split(
    text: str, start: int, end: int, settings: ChunkingSettings
) -> list[tuple[int, int]]:
    """Split a sentence longer than `max_chars` at whitespace."""
    pieces: list[tuple[int, int]] = []
    while end - start > settings.max_chars:
        cut = text.rfind(" ", start, start + settings.max_chars)
        if cut <= start:
            cut = start + settings.max_chars
        pieces.append((start, cut))
        start = cut + 1 if text[cut : cut + 1] == " " else cut
    pieces.append((start, end))
    return pieces
