import unittest

from app.domain.memory.policies import SimilarityDecision, classify_similarity


class SimilarityPolicyTests(unittest.TestCase):
    def test_classify_similarity_save_when_below_low(self) -> None:
        decision = classify_similarity(score=0.5, low=0.8, high=0.95)
        self.assertIs(decision, SimilarityDecision.SAVE)

    def test_classify_similarity_judge_on_boundaries(self) -> None:
        self.assertIs(
            classify_similarity(score=0.8, low=0.8, high=0.95),
            SimilarityDecision.JUDGE,
        )
        self.assertIs(
            classify_similarity(score=0.95, low=0.8, high=0.95),
            SimilarityDecision.JUDGE,
        )

    def test_classify_similarity_skip_when_above_high(self) -> None:
        decision = classify_similarity(score=0.99, low=0.8, high=0.95)
        self.assertIs(decision, SimilarityDecision.SKIP)
