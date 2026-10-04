from fonti.config import ChunkingSettings
from fonti.domain import Block, BlockKind, Chunk, ParsedDocument
from fonti.ingest.chunking import chunk_document

SENTENCE = "Il conduttore paga il canone mensile entro il giorno cinque di ogni mese. "


def heading(text: str, page: int, level: int) -> Block:
    return Block(BlockKind.HEADING, text, page, level)


def text(content: str, page: int) -> Block:
    return Block(BlockKind.TEXT, content, page)


def chunk(blocks: list[Block], max_chars: int = 400, overlap: int = 80) -> list[Chunk]:
    parsed = ParsedDocument(tuple(blocks), page_count=max(b.page for b in blocks))
    result = chunk_document(parsed, ChunkingSettings(max_chars=max_chars, overlap_chars=overlap))
    for c in result.chunks:
        assert c.text == result.text[c.start : c.end]
    return list(result.chunks)


def test_chunks_follow_sections_and_include_their_heading() -> None:
    chunks = chunk(
        [
            heading("TITOLO I\nRAPPORTI CIVILI", 1, 2),
            heading("Art. 13.", 1, 5),
            text("La libertà personale è inviolabile.", 1),
            heading("Art. 14.", 2, 5),
            text("Il domicilio è inviolabile.", 2),
        ]
    )

    assert [(c.section, c.page_start, c.page_end) for c in chunks] == [
        ("TITOLO I - RAPPORTI CIVILI › Art. 13.", 1, 1),
        ("TITOLO I - RAPPORTI CIVILI › Art. 14.", 2, 2),
    ]
    assert chunks[0].text.startswith("TITOLO I\nRAPPORTI CIVILI\n\nArt. 13.")
    assert chunks[1].text == "Art. 14.\n\nIl domicilio è inviolabile."
    assert chunks[0].context == chunks[0].section


def test_small_blocks_of_a_section_are_packed_together() -> None:
    chunks = chunk([heading("Art. 1", 1, 5), text("Primo comma.", 1), text("Secondo comma.", 2)])

    assert len(chunks) == 1
    assert (chunks[0].page_start, chunks[0].page_end) == (1, 2)


def test_long_paragraph_is_split_by_sentences_with_overlap() -> None:
    chunks = chunk([heading("Art. 5", 1, 5), text(SENTENCE * 12, 1)], max_chars=300, overlap=80)

    assert len(chunks) > 2
    assert all(len(c.text) <= 300 for c in chunks)
    assert chunks[0].text.startswith("Art. 5\n\nIl conduttore")
    assert all(c.text.endswith("mese.") for c in chunks)
    assert chunks[1].start < chunks[0].end  # windows overlap
    assert all(c.section == "Art. 5" for c in chunks)


def test_tables_are_separate_chunks() -> None:
    table = Block(BlockKind.TABLE, "| Rata | Importo |\n| 1 | 800 |", 1)

    chunks = chunk([heading("Art. 3", 1, 5), text("Il canone è pagato in rate.", 1), table])

    assert [c.kind for c in chunks] == [BlockKind.TEXT, BlockKind.TABLE]


def test_document_without_headings_has_empty_section() -> None:
    chunks = chunk([text("Solo testo.", 1)])

    assert chunks[0].section == ""
