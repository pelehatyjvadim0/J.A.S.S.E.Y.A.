import uuid

from app.application.memory.use_cases.persist_facts import apply_judge_results, persist_facts
from app.application.memory.use_cases.reconcile_facts import reconcile_facts
from app.application.memory.use_cases.summarize_dialog import summarize_dialog_batch
from app.core.logging import TraceContext, log_step
from app.domain.chat.entities import DialogHistoryMessage
from app.domain.memory.entities import MemoryPipelineReport, SummaryBatch
from app.infrastructure.llm.gateway import OpenAIGateway
from app.infrastructure.vectorstore.qdrant_repository import QdrantMemoryRepository
from settings import settings


class MemoryPipeline:
    def __init__(self, gateway: OpenAIGateway, memory_repo: QdrantMemoryRepository, session_id: str):
        self.gateway = gateway
        self.memory_repo = memory_repo
        self.session_id = session_id
        self.dialog_buffer: list[DialogHistoryMessage] = []
        self.message_index = 0

    def add_turn(self, user_prompt: str, assistant_response: str) -> None:
        self._append_message(role="user", content=user_prompt)
        self._append_message(role="assistant", content=assistant_response)

    def _append_message(self, role: str, content: str) -> None:
        self.dialog_buffer.append(
            DialogHistoryMessage(role=role, content=content, index=self.message_index)
        )
        self.message_index += 1

    async def run_if_needed(self) -> MemoryPipelineReport:
        report = MemoryPipelineReport(session_id=self.session_id)
        if len(self.dialog_buffer) < settings.SUMMARY_EVERY_N_MESSAGES:
            return report

        batch_messages = self.dialog_buffer[:settings.SUMMARY_EVERY_N_MESSAGES]
        batch = SummaryBatch(
            start_index=batch_messages[0].index,
            end_index=batch_messages[-1].index,
            messages=batch_messages,
            session_id=self.session_id,
        )
        report.start_index = batch.start_index
        report.end_index = batch.end_index

        trace = TraceContext(session_id=self.session_id, trace_id=str(uuid.uuid4())[:8])
        log_step(trace, "build_batch", "ok", f"Сформирован батч {batch.start_index}-{batch.end_index}")

        summary_result = await summarize_dialog_batch(self.gateway, batch)
        report.extracted_facts = len(summary_result.facts)

        print(f'Извлечено фактов: {summary_result.facts}')
        log_step(trace, "summarize", "ok", f"Извлечено фактов: {report.extracted_facts}")

        reconcile_result = await reconcile_facts(self.memory_repo, summary_result.facts)
        report.ignored_facts = len(reconcile_result.skipped_facts)
        log_step(
            trace,
            "reconcile",
            "ok",
            "К сохранению: "
            f"{len(reconcile_result.facts_to_save)}, к judge: {len(reconcile_result.facts_to_judge)}, "
            f"пропущено: {report.ignored_facts}",
        )

        saved_directly = await persist_facts(
            self.memory_repo,
            reconcile_result.facts_to_save,
            summary_result,
        )
        report.saved_facts += saved_directly
        log_step(trace, "persist_direct", "ok", f"Сохранено напрямую: {saved_directly}")

        judge_results = []
        if reconcile_result.facts_to_judge:
            judge_results = await self.gateway.judge_fact_relation(reconcile_result.facts_to_judge)
            report.judged_facts = len(judge_results)
            log_step(trace, "judge", "ok", f"Решений judge: {report.judged_facts}")

        replaced_count, added_count = await apply_judge_results(
            self.memory_repo,
            judge_results,
            summary_result,
        )
        report.replaced_facts = replaced_count
        report.saved_facts += added_count
        log_step(
            trace,
            "apply_judge",
            "ok",
            f"REPLACE: {replaced_count}, ADD: {added_count}",
        )

        self.dialog_buffer = self.dialog_buffer[settings.SUMMARY_EVERY_N_MESSAGES:]
        log_step(trace, "trim_buffer", "ok", f"Новый размер буфера: {len(self.dialog_buffer)}")

        return report