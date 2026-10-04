import numpy as np

from fonti.index.vectors import VectorIndex


def test_search_returns_best_matches_first() -> None:
    matrix = np.array([[1, 0], [0.6, 0.8], [0, 1]], dtype=np.float32)
    index = VectorIndex(np.array([10, 20, 30], dtype=np.int64), matrix)

    results = index.search(np.array([0, 1], dtype=np.float32), k=2)

    assert [chunk_id for chunk_id, _ in results] == [30, 20]
    assert results[0][1] == 1.0


def test_search_on_empty_index_returns_nothing() -> None:
    index = VectorIndex(np.empty(0, dtype=np.int64), np.empty((0, 0), dtype=np.float32))

    assert index.search(np.array([1.0], dtype=np.float32), k=5) == []
