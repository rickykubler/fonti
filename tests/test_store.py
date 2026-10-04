from pathlib import Path

import numpy as np
import pytest

from fonti.domain import BlockKind, Chunk, PageSpan
from fonti.index.store import IndexMismatchError, NewDocument, Store
from fonti.index.text import index_terms, match_query

TEXT = "Art. 1\n\nIl canone è di euro 800 al mese.\n\nArt. 2\n\nPerché la durata è di quattro anni."
DOC_ID = "ab" * 32


def make_document(doc_id: str = DOC_ID) -> tuple[NewDocument, list[Chunk]]:
    split = TEXT.index("Art. 2")
    document = NewDocument(
        id=doc_id,
        filename="contratto.pdf",
        title="Contratto",
        suffix=".pdf",
        page_count=2,
        parser="fast",
        text=TEXT,
        pages=(PageSpan(1, 0, split - 2), PageSpan(2, split, len(TEXT))),
    )
    chunks = [
        Chunk(0, 0, split - 2, TEXT[: split - 2], 1, 1, "Art. 1", BlockKind.TEXT),
        Chunk(1, split, len(TEXT), TEXT[split:], 2, 2, "Art. 2", BlockKind.TEXT),
    ]
    return document, chunks


def add(store: Store, doc_id: str = DOC_ID) -> None:
    document, chunks = make_document(doc_id)
    vectors = np.eye(len(chunks), 4, dtype=np.float32)
    store.add_document(document, chunks, [index_terms(c.text) for c in chunks], vectors)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "index.sqlite3")


def test_added_document_is_listed(store: Store) -> None:
    add(store)

    [info] = store.list_documents()

    assert info.id == DOC_ID
    assert info.chunk_count == 2
    assert store.has_document(DOC_ID)
    assert store.document_text(DOC_ID) == TEXT
    assert store.page_spans(DOC_ID)[1].page == 2


def test_keyword_search_finds_chunk_ignoring_accents(store: Store) -> None:
    add(store)
    query = match_query("perche quattro")
    assert query is not None

    results = store.search_terms(query, limit=5)

    hits = store.get_hits([chunk_id for chunk_id, _ in results])
    assert hits[results[0][0]].section == "Art. 2"


def test_vectors_round_trip(store: Store) -> None:
    add(store)

    ids, matrix = store.load_vectors()

    assert len(ids) == 2
    np.testing.assert_array_equal(matrix, np.eye(2, 4, dtype=np.float32))


def test_hits_carry_document_metadata(store: Store) -> None:
    add(store)
    ids, _ = store.load_vectors()

    hit = store.get_hits([int(ids[0])])[int(ids[0])]

    assert hit.filename == "contratto.pdf"
    assert hit.text == TEXT[hit.start : hit.end]
    assert hit.kind is BlockKind.TEXT


def test_remove_document_deletes_everything(store: Store) -> None:
    add(store)
    revision = store.revision

    assert store.remove_document(DOC_ID)

    assert store.list_documents() == []
    assert len(store.load_vectors()[0]) == 0
    assert store.search_terms('"canone"', limit=5) == []
    assert store.revision > revision
    assert not store.remove_document(DOC_ID)


def test_find_documents_by_id_prefix(store: Store) -> None:
    add(store)
    add(store, "cd" * 32)

    assert [d.id for d in store.find_documents("AB")] == [DOC_ID]
    assert store.find_documents("zz") == []


def test_index_settings_cannot_change_once_documents_exist(store: Store) -> None:
    store.ensure_settings({"embedder": "model-a"})
    add(store)

    with pytest.raises(IndexMismatchError):
        store.ensure_settings({"embedder": "model-b"})
    with pytest.raises(IndexMismatchError):
        store.check_settings({"embedder": "model-b"})
    store.check_settings({"embedder": "model-a"})


def test_empty_index_adopts_new_settings(store: Store) -> None:
    store.ensure_settings({"embedder": "model-a"})

    store.ensure_settings({"embedder": "model-b"})

    store.check_settings({"embedder": "model-b"})
