"""Hybrid retrieval: BM25 (FTS5) and dense search, fused with Reciprocal Rank Fusion."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace

from fonti.config import RetrievalSettings
from fonti.domain import Hit
from fonti.index.store import Store
from fonti.index.text import match_query
from fonti.index.vectors import VectorIndex
from fonti.ml.embedder import Embedder


def reciprocal_rank_fusion(rankings: Sequence[Sequence[int]], k: int) -> list[tuple[int, float]]:
    """Fuse rankings by summing 1 / (k + rank); ties are broken by id for determinism."""
    scores: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


class HybridRetriever:
    def __init__(self, store: Store, embedder: Embedder, settings: RetrievalSettings) -> None:
        self._store = store
        self._embedder = embedder
        self._settings = settings
        self._vectors: VectorIndex | None = None
        self._vectors_revision = -1

    def search(self, question: str, limit: int | None = None) -> list[Hit]:
        """Candidate chunks for `question`, best first, scored by fused rank."""
        keyword = self._keyword_ranking(question)
        dense = self._dense_ranking(question)
        fused = reciprocal_rank_fusion([keyword, dense], self._settings.rrf_k)
        fused = fused[: limit or self._settings.fused_k]
        hits = self._store.get_hits([chunk_id for chunk_id, _ in fused])
        return [
            replace(hits[chunk_id], score=score) for chunk_id, score in fused if chunk_id in hits
        ]

    def _keyword_ranking(self, question: str) -> list[int]:
        query = match_query(question, self._settings.keyword_terms)
        if query is None:
            return []
        return [chunk_id for chunk_id, _ in self._store.search_terms(query, self._settings.bm25_k)]

    def _dense_ranking(self, question: str) -> list[int]:
        index = self._vector_index()
        if len(index) == 0:
            return []
        query = self._embedder.embed_queries([question])[0]
        return [chunk_id for chunk_id, _ in index.search(query, self._settings.dense_k)]

    def _vector_index(self) -> VectorIndex:
        revision = self._store.revision
        if self._vectors is None or revision != self._vectors_revision:
            self._vectors = VectorIndex(*self._store.load_vectors())
            self._vectors_revision = revision
        return self._vectors
