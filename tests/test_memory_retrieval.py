import asyncio
import unittest
import uuid
from typing import Any, cast

from app.domain.memory.retrieval import MemoryFactCandidate
from app.infrastructure.llm.reranker.agent import LLMReranker


class FakeClient:
    def request_content(self, messages, model, temperature):
        return (
            '{"items": ['
            '{"fact_id": "22222222-2222-2222-2222-222222222222", "rerank_score": 0.10},'
            '{"fact_id": "11111111-1111-1111-1111-111111111111", "rerank_score": 0.90}'
            "]}"
        )


class FakeInvalidJsonClient:
    def __init__(self):
        self.calls = 0

    def request_content(self, messages, model, temperature):
        self.calls += 1
        return '{"items": ['


class MemoryRetrievalTests(unittest.TestCase):
    def test_reranker_returns_sorted_facts_from_valid_json(self) -> None:
        async def scenario() -> None:
            candidates = [
                MemoryFactCandidate(
                    fact_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                    content="Пользователь предпочитает короткие ответы.",
                    vector_score=0.40,
                    session_id="s-1",
                    created_at=None,
                    source="qdrant",
                ),
                MemoryFactCandidate(
                    fact_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                    content="Пользователь работает по выходным.",
                    vector_score=0.95,
                    session_id="s-1",
                    created_at=None,
                    source="qdrant",
                ),
            ]
            reranker = LLMReranker(
                client=cast(Any, FakeClient()),
                model="fake-model",
                temperature=0.0,
            )

            result = await reranker.rerank(query="Что мне важно помнить о пользователе?", candidates=candidates, top_n=2)

            self.assertEqual(len(result), 2)
            self.assertEqual(
                [item.candidate.fact_id for item in result],
                [
                    uuid.UUID("11111111-1111-1111-1111-111111111111"),
                    uuid.UUID("22222222-2222-2222-2222-222222222222"),
                ],
            )
            self.assertGreaterEqual(result[0].final_score, result[1].final_score)

        asyncio.run(scenario())

    def test_reranker_falls_back_to_vector_scores_on_invalid_json(self) -> None:
        async def scenario() -> None:
            candidates = [
                MemoryFactCandidate(
                    fact_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                    content="Факт с низким векторным score.",
                    vector_score=0.40,
                    session_id="s-1",
                    created_at=None,
                    source="qdrant",
                ),
                MemoryFactCandidate(
                    fact_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                    content="Факт с высоким векторным score.",
                    vector_score=0.95,
                    session_id="s-1",
                    created_at=None,
                    source="qdrant",
                ),
            ]
            fake_client = FakeInvalidJsonClient()
            reranker = LLMReranker(
                client=cast(Any, fake_client),
                model="fake-model",
                temperature=0.0,
            )

            result = await reranker.rerank(
                query="Что важно помнить?",
                candidates=candidates,
                top_n=2,
            )

            self.assertEqual(len(result), 2)
            self.assertEqual(
                [item.candidate.fact_id for item in result],
                [
                    uuid.UUID("22222222-2222-2222-2222-222222222222"),
                    uuid.UUID("11111111-1111-1111-1111-111111111111"),
                ],
            )
            self.assertEqual([item.rerank_score for item in result], [0.0, 0.0])
            self.assertEqual(fake_client.calls, 3)
            diagnostics = reranker.get_last_diagnostics()
            self.assertEqual(diagnostics["rerank_input_count"], 2)
            self.assertEqual(diagnostics["rerank_output_count"], 2)
            self.assertEqual(diagnostics["model_name"], "fake-model")
            self.assertEqual(diagnostics["fallback_reason"], "invalid_json_after_3_attempts")
            rerank_ms = cast(float, diagnostics["rerank_ms"])
            self.assertGreaterEqual(rerank_ms, 0.0)

        asyncio.run(scenario())
