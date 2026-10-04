from fonti.retrieval.hybrid import reciprocal_rank_fusion


def test_rrf_rewards_items_ranked_high_in_both_lists() -> None:
    fused = reciprocal_rank_fusion([[1, 2, 3], [3, 1, 4]], k=60)

    assert [item for item, _ in fused] == [1, 3, 2, 4]


def test_rrf_handles_empty_rankings() -> None:
    assert reciprocal_rank_fusion([[], [7]], k=60) == [(7, 1 / 61)]
