from collections.abc import Iterable


def rrf_fuse(rankings: list[Iterable[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(id) = sum over rankings of 1/(k + rank).

    Rank is 1-based. Items appearing in more rankings gain score — the standard
    dense+sparse fusion used in production RAG.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
