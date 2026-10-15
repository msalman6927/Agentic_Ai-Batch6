from medivault.retrieval.fusion import rrf_fuse


def test_rrf_single_ranking_preserves_order() -> None:
    fused = rrf_fuse([["a", "b", "c"]], k=60)
    assert [item for item, _ in fused] == ["a", "b", "c"]


def test_rrf_boosts_items_in_both_rankings() -> None:
    fused = rrf_fuse([["a", "b"], ["b", "c"]], k=60)
    assert fused[0][0] == "b"
    scores = dict(fused)
    assert scores["b"] > scores["a"]
    assert scores["b"] > scores["c"]


def test_rrf_empty() -> None:
    assert rrf_fuse([], k=60) == []
    assert rrf_fuse([[], []], k=60) == []


def test_rrf_custom_k_changes_gap() -> None:
    fused_small_k = dict(rrf_fuse([["a", "b"], ["b"]], k=1))
    fused_big_k = dict(rrf_fuse([["a", "b"], ["b"]], k=100))
    gap_small = fused_small_k["b"] - fused_small_k["a"]
    gap_big = fused_big_k["b"] - fused_big_k["a"]
    assert gap_small > gap_big
