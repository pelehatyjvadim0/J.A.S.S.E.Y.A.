from enum import Enum


class SimilarityDecision(str, Enum):
    SAVE = "SAVE"
    JUDGE = "JUDGE"
    SKIP = "SKIP"


def classify_similarity(score: float, low: float, high: float) -> SimilarityDecision:
    """Классифицирует факт по похожести на существующие записи памяти."""
    if score < low:
        return SimilarityDecision.SAVE
    if score > high:
        return SimilarityDecision.SKIP
    return SimilarityDecision.JUDGE
