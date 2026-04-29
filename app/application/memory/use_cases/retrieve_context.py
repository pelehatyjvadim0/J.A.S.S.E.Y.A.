from app.domain.chat.entities import ChatMessage, DialogHistoryMessage
from app.domain.memory.retrieval import MemoryFactCandidate, SelectedMemoryFacts
from app.core.logging import (
    TraceContext,
    elapsed_ms,
    log_memory_selection_observability,
    log_step_error,
    log_step_start,
    log_step_success,
    start_timer,
)
from app.infrastructure.vectorstore.qdrant_repository import QdrantMemoryRepository
from app.application.memory.services.memory_selector import MemorySelector
from settings import settings


async def retrieve_context_messages(
    memory_repo: QdrantMemoryRepository,
    memory_selector: MemorySelector,
    user_prompt: str,
    dialog_buffer: list[DialogHistoryMessage],
    trace_id: str,
    session_id: str | None = None,
) -> list[ChatMessage]:
    """Собирает сообщения для ответа ассистента: системный промпт, память, история, запрос пользователя."""
    trace = TraceContext(session_id=session_id, trace_id=trace_id)
    retrieval_started_at = start_timer()
    log_step_start(
        trace,
        "retrieval",
        "retrieve_context_messages",
        message="Старт формирования контекста",
        meta={"dialog_buffer_size": len(dialog_buffer), "query_length": len(user_prompt.strip())},
    )
    messages: list[ChatMessage] = [ChatMessage(role="system", content=settings.SYSTEM_PROMPT)]
    try:
        search_started_at = start_timer()
        log_step_start(trace, "retrieval", "vector_search", message="Поиск кандидатов памяти")
        memory_facts: list[MemoryFactCandidate] = await memory_repo.search_facts_with_score(
            user_prompt,
            limit=settings.MEMORY_RETRIEVAL_TOP_K,
        )
        log_step_success(
            trace,
            "retrieval",
            "vector_search",
            message="Поиск кандидатов завершён",
            duration_ms=elapsed_ms(search_started_at),
            meta={"candidates_total": len(memory_facts), "retrieval_top_k": settings.MEMORY_RETRIEVAL_TOP_K},
        )

        select_started_at = start_timer()
        log_step_start(trace, "retrieval", "memory_select", message="Отбор фактов для контекста")
        selected_facts: SelectedMemoryFacts = await memory_selector.select(user_prompt, memory_facts)
        diagnostics = selected_facts.diagnostics or {}
        rerank_input_count = int(diagnostics.get("rerank_input_count", len(memory_facts)))
        reranked_top_n = int(diagnostics.get("rerank_output_count", 0))
        dropped_by_vector_threshold = max(len(memory_facts) - rerank_input_count, 0)
        selected_for_context = selected_facts.facts[:settings.MEMORY_CONTEXT_FACTS_LIMIT]
        log_step_success(
            trace,
            "retrieval",
            "memory_select",
            message="Отбор фактов завершён",
            duration_ms=elapsed_ms(select_started_at),
            meta={"selected_count": len(selected_for_context), "context_limit": settings.MEMORY_CONTEXT_FACTS_LIMIT},
        )

        top_reasons: list[str] = []
        if diagnostics.get("fallback_reason"):
            top_reasons.append(f'сработал fallback: {diagnostics["fallback_reason"]}')
        if reranked_top_n > 0:
            top_reasons.append("высокий rerank_score относительно остальных кандидатов")
        if dropped_by_vector_threshold > 0:
            top_reasons.append("часть кандидатов отфильтрована по порогу vector_score")
        if selected_for_context:
            top_reasons.append("факты попали в итоговый top-N контекста")

        log_memory_selection_observability(
            context=trace,
            candidates_total=len(memory_facts),
            dropped_by_vector_threshold=dropped_by_vector_threshold,
            reranked_top_n=reranked_top_n,
            selected_count=len(selected_for_context),
            top_reasons=top_reasons,
            query_length=len(user_prompt.strip()),
        )

        if selected_for_context:
            memory_block = "### ТВОЯ ПАМЯТЬ\n" + "\n".join(selected_for_context)
            messages.append(ChatMessage(role="system", content=memory_block))

        for message in dialog_buffer:
            messages.append(ChatMessage(role=message.role, content=message.content))
        messages.append(ChatMessage(role="user", content=user_prompt))
        log_step_success(
            trace,
            "retrieval",
            "retrieve_context_messages",
            message="Контекст успешно сформирован",
            duration_ms=elapsed_ms(retrieval_started_at),
            meta={"messages_total": len(messages)},
        )
        return messages
    except Exception as error:
        log_step_error(
            trace,
            "retrieval",
            "retrieve_context_messages",
            error=error,
            duration_ms=elapsed_ms(retrieval_started_at),
            message="Ошибка при формировании контекста",
        )
        raise
