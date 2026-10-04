"""Exact (brute-force) vector search over normalized embeddings."""

import numpy as np
from numpy.typing import NDArray


class VectorIndex:
    def __init__(self, ids: NDArray[np.int64], matrix: NDArray[np.float32]) -> None:
        if len(ids) != len(matrix):
            raise ValueError("ids and matrix must have the same length")
        self._ids = ids
        self._matrix = matrix

    def __len__(self) -> int:
        return len(self._ids)

    def search(self, query: NDArray[np.float32], k: int) -> list[tuple[int, float]]:
        """Return up to `k` (id, cosine similarity) pairs, best first."""
        if len(self._ids) == 0 or k <= 0:
            return []
        scores = self._matrix @ query
        k = min(k, len(scores))
        top = np.argpartition(-scores, k - 1)[:k]
        order = top[np.argsort(-scores[top], kind="stable")]
        return [(int(self._ids[i]), float(scores[i])) for i in order]
