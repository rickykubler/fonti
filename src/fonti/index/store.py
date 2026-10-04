"""SQLite persistence: documents, pages, chunks, the FTS5 keyword index and the embeddings.

This is the only module that issues SQL.
"""

import sqlite3
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from fonti.domain import BlockKind, Chunk, DocumentInfo, Hit, PageSpan
from fonti.errors import FontiError

SCHEMA_VERSION = "1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    title TEXT,
    suffix TEXT NOT NULL,
    page_count INTEGER NOT NULL,
    parser TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pages (
    doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    PRIMARY KEY (doc_id, page)
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    section TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    context TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_by_doc ON chunks(doc_id);
CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    vector BLOB NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    terms, tokenize = 'unicode61 remove_diacritics 2'
);
"""

_UPSERT_META = (
    "INSERT INTO meta (key, value) VALUES (?, ?) "
    "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
)

_HIT_COLUMNS = """
    c.id, c.doc_id, d.filename, d.title, c.text, c.char_start, c.char_end,
    c.page_start, c.page_end, c.section, c.kind
"""


class IndexMismatchError(FontiError):
    """The index was built with different settings, e.g. another embedding model."""


@dataclass(frozen=True, slots=True)
class NewDocument:
    id: str  # SHA-256 of the file
    filename: str
    title: str | None
    suffix: str
    page_count: int
    parser: str
    text: str
    pages: tuple[PageSpan, ...]


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # Autocommit mode: transactions are explicit, see _transaction().
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(_SCHEMA)
        self._check_schema_version()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def _check_schema_version(self) -> None:
        with self._transaction() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO meta (key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,)
                )
            elif row[0] != SCHEMA_VERSION:
                raise IndexMismatchError(
                    f"L'indice usa lo schema {row[0]}, questa versione richiede {SCHEMA_VERSION}: "
                    "ricrea l'indice."
                )

    # --- index settings -------------------------------------------------------------------

    def ensure_settings(self, expected: Mapping[str, str]) -> None:
        """Record the settings that define the index; raise if they changed since documents
        were indexed. An empty index adopts the new settings."""
        with self._transaction() as conn:
            empty = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
            for key, value in expected.items():
                row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
                if row is not None and row[0] != value and not empty:
                    raise IndexMismatchError(
                        f"L'indice è stato creato con {key} = {row[0]!r}, ma la configurazione "
                        f"attuale usa {value!r}. Esegui `fonti reindex` oppure ripristina la "
                        "configurazione."
                    )
                conn.execute(_UPSERT_META, (key, value))

    def force_settings(self, expected: Mapping[str, str]) -> None:
        """Overwrite the recorded index settings, once every document was re-indexed."""
        with self._transaction() as conn:
            conn.executemany(_UPSERT_META, list(expected.items()))

    def check_settings(self, expected: Mapping[str, str]) -> None:
        """Raise if the stored index settings differ from `expected` (missing keys are ok)."""
        with self._lock:
            for key, value in expected.items():
                row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
                if row is not None and row[0] != value and self.document_count() > 0:
                    raise IndexMismatchError(
                        f"L'indice è stato creato con {key} = {row[0]!r}, ma la configurazione "
                        f"attuale usa {value!r}. Esegui `fonti reindex` oppure ripristina la "
                        "configurazione."
                    )

    @property
    def revision(self) -> int:
        """Increases on every change to the indexed content; used to refresh caches."""
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key = 'revision'").fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _bump_revision(conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('revision', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1"
        )

    # --- documents ------------------------------------------------------------------------

    def has_document(self, doc_id: str) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return row is not None

    def document_count(self) -> int:
        with self._lock:
            count: int = self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        return count

    def add_document(
        self,
        document: NewDocument,
        chunks: Sequence[Chunk],
        terms: Sequence[str],
        vectors: NDArray[np.float32],
    ) -> None:
        with self._transaction() as conn:
            self._insert(conn, document, chunks, terms, vectors)
            self._bump_revision(conn)

    def replace_document(
        self,
        document: NewDocument,
        chunks: Sequence[Chunk],
        terms: Sequence[str],
        vectors: NDArray[np.float32],
    ) -> None:
        """Atomically re-index an existing document (used when settings change)."""
        with self._transaction() as conn:
            self._delete(conn, document.id)
            self._insert(conn, document, chunks, terms, vectors)
            self._bump_revision(conn)

    def remove_document(self, doc_id: str) -> bool:
        with self._transaction() as conn:
            deleted = self._delete(conn, doc_id)
            self._bump_revision(conn)
        return deleted

    @staticmethod
    def _delete(conn: sqlite3.Connection, doc_id: str) -> bool:
        conn.execute(
            "DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM chunks WHERE doc_id = ?)",
            (doc_id,),
        )
        # Pages, chunks and embeddings follow through ON DELETE CASCADE.
        return conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,)).rowcount > 0

    @staticmethod
    def _insert(
        conn: sqlite3.Connection,
        document: NewDocument,
        chunks: Sequence[Chunk],
        terms: Sequence[str],
        vectors: NDArray[np.float32],
    ) -> None:
        if not len(chunks) == len(terms) == len(vectors):
            raise ValueError("chunks, terms and vectors must have the same length")
        conn.execute(
            "INSERT INTO documents (id, filename, title, suffix, page_count, parser, text, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                document.id,
                document.filename,
                document.title,
                document.suffix,
                document.page_count,
                document.parser,
                document.text,
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        conn.executemany(
            "INSERT INTO pages (doc_id, page, char_start, char_end) VALUES (?, ?, ?, ?)",
            [(document.id, page.page, page.start, page.end) for page in document.pages],
        )
        for chunk, chunk_terms, vector in zip(chunks, terms, vectors, strict=True):
            cursor = conn.execute(
                "INSERT INTO chunks (doc_id, ordinal, char_start, char_end, page_start, "
                "page_end, section, kind, text, context) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    document.id,
                    chunk.ordinal,
                    chunk.start,
                    chunk.end,
                    chunk.page_start,
                    chunk.page_end,
                    chunk.section,
                    chunk.kind.value,
                    chunk.text,
                    chunk.context,
                ),
            )
            chunk_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO chunks_fts (rowid, terms) VALUES (?, ?)", (chunk_id, chunk_terms)
            )
            conn.execute(
                "INSERT INTO embeddings (chunk_id, vector) VALUES (?, ?)",
                (chunk_id, np.asarray(vector, dtype="<f4").tobytes()),
            )

    def list_documents(self) -> list[DocumentInfo]:
        return self._query_documents("", ())

    def find_documents(self, id_prefix: str) -> list[DocumentInfo]:
        prefix = id_prefix.lower()
        if not prefix or any(c not in "0123456789abcdef" for c in prefix):
            return []
        return self._query_documents("WHERE d.id LIKE ?", (prefix + "%",))

    def _query_documents(self, where: str, params: tuple[str, ...]) -> list[DocumentInfo]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT d.id, d.filename, d.title, d.page_count, COUNT(c.id), d.parser, "
                f"d.created_at FROM documents d LEFT JOIN chunks c ON c.doc_id = d.id {where} "
                "GROUP BY d.id ORDER BY d.created_at, d.filename",
                params,
            ).fetchall()
        return [DocumentInfo(*row) for row in rows]

    def document_text(self, doc_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT text FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
        return row[0] if row else None

    def document_suffix(self, doc_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT suffix FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
        return row[0] if row else None

    def page_spans(self, doc_id: str) -> list[PageSpan]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT page, char_start, char_end FROM pages WHERE doc_id = ? ORDER BY page",
                (doc_id,),
            ).fetchall()
        return [PageSpan(*row) for row in rows]

    # --- retrieval ------------------------------------------------------------------------

    def search_terms(self, match: str, limit: int) -> list[tuple[int, float]]:
        """BM25 search; returns (chunk id, score) pairs, best first (higher is better)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT rowid, bm25(chunks_fts) AS rank FROM chunks_fts "
                "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
                (match, limit),
            ).fetchall()
        return [(int(chunk_id), -float(rank)) for chunk_id, rank in rows]

    def load_vectors(self) -> tuple[NDArray[np.int64], NDArray[np.float32]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT chunk_id, vector FROM embeddings ORDER BY chunk_id"
            ).fetchall()
        if not rows:
            return np.empty(0, dtype=np.int64), np.empty((0, 0), dtype=np.float32)
        ids = np.fromiter((row[0] for row in rows), dtype=np.int64, count=len(rows))
        matrix = np.vstack([np.frombuffer(row[1], dtype="<f4") for row in rows])
        return ids, matrix.astype(np.float32, copy=False)

    def get_hits(self, chunk_ids: Sequence[int]) -> dict[int, Hit]:
        if not chunk_ids:
            return {}
        placeholders = ",".join("?" * len(chunk_ids))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_HIT_COLUMNS} FROM chunks c JOIN documents d ON d.id = c.doc_id "
                f"WHERE c.id IN ({placeholders})",
                tuple(chunk_ids),
            ).fetchall()
        hits = {}
        for (
            chunk_id,
            doc_id,
            filename,
            title,
            text,
            start,
            end,
            p_start,
            p_end,
            section,
            kind,
        ) in rows:
            hits[chunk_id] = Hit(
                chunk_id=chunk_id,
                doc_id=doc_id,
                filename=filename,
                title=title,
                text=text,
                start=start,
                end=end,
                page_start=p_start,
                page_end=p_end,
                section=section,
                kind=BlockKind(kind),
            )
        return hits
