from app.application.memory.use_cases.persist_facts import apply_judge_results, persist_facts
from app.application.memory.use_cases.reconcile_facts import reconcile_facts
from app.application.memory.use_cases.summarize_dialog import summarize_dialog_batch
from app.core.logging import (
    TraceContext,
    elapsed_ms,
    log_step_error,
    log_step_start,
    log_step_success,
    start_timer,
)
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

    async def run_if_needed(self, trace_id: str | None = None) -> MemoryPipelineReport:
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

        trace = TraceContext(session_id=self.session_id, trace_id=trace_id or "pipeline-local")
        pipeline_started_at = start_timer()
        log_step_start(
            trace,
            "pipeline",
            "run_memory_pipeline",
            message="Запуск memory-пайплайна",
            meta={"batch_size": len(batch_messages)},
        )
        try:
            build_batch_started_at = start_timer()
            log_step_start(trace, "pipeline", "build_batch", message="Формирование батча сообщений")
            log_step_success(
                trace,
                "pipeline",
                "build_batch",
                message=f"Сформирован батч {batch.start_index}-{batch.end_index}",
                duration_ms=elapsed_ms(build_batch_started_at),
            )

            summarize_started_at = start_timer()
            log_step_start(trace, "pipeline", "summarize", message="Старт суммаризации диалога")
            summary_result = await summarize_dialog_batch(self.gateway, batch)
            report.extracted_facts = len(summary_result.facts)
            log_step_success(
                trace,
                "pipeline",
                "summarize",
                message="Суммаризация завершена",
                duration_ms=elapsed_ms(summarize_started_at),
                meta={"extracted_facts": report.extracted_facts},
            )

            reconcile_started_at = start_timer()
            log_step_start(trace, "pipeline", "reconcile", message="Согласование фактов памяти")
            reconcile_result = await reconcile_facts(self.memory_repo, summary_result.facts)
            report.ignored_facts = len(reconcile_result.skipped_facts)
            log_step_success(
                trace,
                "pipeline",
                "reconcile",
                message="Согласование фактов завершено",
                duration_ms=elapsed_ms(reconcile_started_at),
                meta={
                    "facts_to_save": len(reconcile_result.facts_to_save),
                    "facts_to_judge": len(reconcile_result.facts_to_judge),
                    "ignored_facts": report.ignored_facts,
                },
            )

            persist_started_at = start_timer()
            log_step_start(trace, "pipeline", "persist_direct", message="Сохранение фактов без judge")
            saved_directly = await persist_facts(
                self.memory_repo,
                reconcile_result.facts_to_save,
                summary_result,
            )
            report.saved_facts += saved_directly
            log_step_success(
                trace,
                "pipeline",
                "persist_direct",
                message="Прямое сохранение завершено",
                duration_ms=elapsed_ms(persist_started_at),
                meta={"saved_directly": saved_directly},
            )

            judge_results = []
            if reconcile_result.facts_to_judge:
                judge_started_at = start_timer()
                log_step_start(trace, "pipeline", "judge", message="Запуск judge для конфликтующих фактов")
                judge_results = await self.gateway.judge_fact_relation(reconcile_result.facts_to_judge)
                report.judged_facts = len(judge_results)
                log_step_success(
                    trace,
                    "pipeline",
                    "judge",
                    message="Judge обработка завершена",
                    duration_ms=elapsed_ms(judge_started_at),
                    meta={"judged_facts": report.judged_facts},
                )

            apply_judge_started_at = start_timer()
            log_step_start(trace, "pipeline", "apply_judge", message="Применение результатов judge")
            replaced_count, added_count = await apply_judge_results(
                self.memory_repo,
                judge_results,
                summary_result,
            )
            report.replaced_facts = replaced_count
            report.saved_facts += added_count
            log_step_success(
                trace,
                "pipeline",
                "apply_judge",
                message="Результаты judge применены",
                duration_ms=elapsed_ms(apply_judge_started_at),
                meta={"replaced_count": replaced_count, "added_count": added_count},
            )

            trim_started_at = start_timer()
            log_step_start(trace, "pipeline", "trim_buffer", message="Обрезка буфера диалога")
            self.dialog_buffer = self.dialog_buffer[settings.SUMMARY_EVERY_N_MESSAGES:]
            log_step_success(
                trace,
                "pipeline",
                "trim_buffer",
                message="Буфер обрезан",
                duration_ms=elapsed_ms(trim_started_at),
                meta={"new_buffer_size": len(self.dialog_buffer)},
            )

            log_step_success(
                trace,
                "pipeline",
                "run_memory_pipeline",
                message="Memory-пайплайн завершён успешно",
                duration_ms=elapsed_ms(pipeline_started_at),
            )
            return report
        except Exception as error:
            log_step_error(
                trace,
                "pipeline",
                "run_memory_pipeline",
                error=error,
                duration_ms=elapsed_ms(pipeline_started_at),
                message="Ошибка выполнения memory-пайплайна",
            )
            raise