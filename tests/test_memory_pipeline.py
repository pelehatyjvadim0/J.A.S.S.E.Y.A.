import asyncio
import unittest
import uuid

import app.application.memory.use_cases.run_memory_pipeline as pipeline_module
from app.application.memory.use_cases.run_memory_pipeline import MemoryPipeline
from app.domain.memory.entities import JudgeFactResult, SummaryResult


class FakeGateway:
    async def summarize_dialog_batch(self, batch):
        return SummaryResult(
            facts=["новый факт", "граничный факт", "дубликат"],
            start_index=batch.start_index,
            end_index=batch.end_index,
            session_id=batch.session_id,
        )

    async def judge_fact_relation(self, candidates):
        return [
            JudgeFactResult(
                old_fact=candidates[0].old_fact,
                new_fact=candidates[0].new_fact,
                old_fact_id=candidates[0].old_fact_id,
                result="REPLACE",
            )
        ]


class FakeMemoryRepo:
    def __init__(self):
        self.saved_facts: list[str] = []
        self.deleted_fact_ids: list[uuid.UUID] = []

    async def find_most_similar_fact(self, new_fact: str):
        if new_fact == "новый факт":
            return None
        if new_fact == "граничный факт":
            return "старый факт", 0.85, uuid.UUID("11111111-1111-1111-1111-111111111111")
        if new_fact == "дубликат":
            return "дубликат", 0.999, uuid.UUID("22222222-2222-2222-2222-222222222222")
        return None

    async def add_summary_fact(self, text, start_index, end_index, session_id, source="summary", metadata=None):
        self.saved_facts.append(text)

    async def delete_fact(self, fact_id: uuid.UUID):
        self.deleted_fact_ids.append(fact_id)


class MemoryPipelineTests(unittest.TestCase):
    def test_memory_pipeline_runs_all_main_branches(self) -> None:
        async def scenario() -> None:
            pipeline_module.SUMMARY_EVERY_N_MESSAGES = 4
            gateway = FakeGateway()
            memory = FakeMemoryRepo()
            pipeline = MemoryPipeline(gateway=gateway, memory_repo=memory, session_id="s-1")

            pipeline.add_turn("u1", "a1")
            pipeline.add_turn("u2", "a2")

            report = await pipeline.run_if_needed()

            self.assertEqual(report.extracted_facts, 3)
            self.assertEqual(report.judged_facts, 1)
            self.assertEqual(report.replaced_facts, 1)
            self.assertEqual(report.saved_facts, 1)
            self.assertEqual(report.ignored_facts, 1)
            self.assertEqual(memory.deleted_fact_ids, [uuid.UUID("11111111-1111-1111-1111-111111111111")])
            self.assertEqual(memory.saved_facts, ["новый факт", "граничный факт"])
            self.assertEqual(len(pipeline.dialog_buffer), 0)

        asyncio.run(scenario())

    def test_memory_pipeline_does_not_run_below_threshold(self) -> None:
        async def scenario() -> None:
            pipeline_module.SUMMARY_EVERY_N_MESSAGES = 4
            gateway = FakeGateway()
            memory = FakeMemoryRepo()
            pipeline = MemoryPipeline(gateway=gateway, memory_repo=memory, session_id="s-2")

            pipeline.add_turn("u1", "a1")
            report = await pipeline.run_if_needed()

            self.assertEqual(report.extracted_facts, 0)
            self.assertEqual(report.saved_facts, 0)
            self.assertEqual(len(pipeline.dialog_buffer), 2)

        asyncio.run(scenario())
