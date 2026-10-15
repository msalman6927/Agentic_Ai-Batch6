from dataclasses import dataclass

from medivault.config import get_settings
from medivault.retrieval.hybrid import RetrievalHit


@dataclass
class ConfidenceResult:
    score: float
    level: str  # high | medium | low
    from_vault: bool
    rationale: str


def _normalize_dense(hit: RetrievalHit) -> float:
    if hit.dense_score is not None:
        return max(0.0, min(1.0, hit.dense_score))
    # RRF scores are small (~1/(k+rank)); map relative strength into 0..1 band
    return max(0.0, min(1.0, hit.score * 8.0))


def compute_confidence(
    hits: list[RetrievalHit], *, answer_text: str = ""
) -> ConfidenceResult:
    """Blend retrieval signals: best cosine score + coverage across hits.

    A second-pass LLM support grade is a planned enhancement (P8) — for v1 the
    dense cosine similarity is the dominant, calibrated signal.
    """
    settings = get_settings()
    if not hits:
        return ConfidenceResult(
            score=0.15,
            level="low",
            from_vault=False,
            rationale="no vault sources retrieved",
        )

    dense_scores = [_normalize_dense(hit) for hit in hits]
    best = max(dense_scores)
    strong = sum(1 for score in dense_scores if score >= 0.5)
    coverage = strong / len(hits) if hits else 0.0
    fused_boost = min(0.1, sum(hit.score for hit in hits) / 10)

    score = round(min(0.99, 0.65 * best + 0.25 * coverage + fused_boost), 3)
    if score >= 0.7:
        level = "high"
    elif score >= settings.min_confidence:
        level = "medium"
    else:
        level = "low"
    rationale = (
        f"best_similarity={best:.2f}, strong_hits={strong}/{len(hits)}, level={level}"
    )
    return ConfidenceResult(
        score=score,
        level=level,
        from_vault=True,
        rationale=rationale,
    )
