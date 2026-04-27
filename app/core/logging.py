from dataclasses import dataclass

from settings import settings


@dataclass(slots=True)
class TraceContext:
    session_id: str
    trace_id: str


def log_step(context: TraceContext, step: str, status: str, message: str) -> None:
    """Пишет единообразный лог шага пайплайна памяти."""
    if not settings.MEMORY_PIPELINE_LOGS_ENABLED:
        return
    print(
        f"[memory-pipeline][session_id={context.session_id}]"
        f"[trace_id={context.trace_id}]"
        f"[step={step}]"
        f"[status={status}] {message}"
    )


def log_memory_selection_observability(
    query: str,
    candidates_total: int,
    dropped_by_vector_threshold: int,
    reranked_top_n: int,
    selected_count: int,
    top_reasons: list[str],
) -> None:
    """Пишет наблюдаемость по выбору фактов памяти."""
    if not settings.MEMORY_PIPELINE_LOGS_ENABLED:
        return

    normalized_reasons = top_reasons[:3]
    reasons_message = " | ".join(normalized_reasons) if normalized_reasons else "нет причин"
    print(
        "[memory-selection]"
        f"[query={query}]"
        f"[candidates_total={candidates_total}]"
        f"[dropped_by_vector_threshold={dropped_by_vector_threshold}]"
        f"[reranked_top_n={reranked_top_n}]"
        f"[selected_count={selected_count}]"
        f" top_reasons={reasons_message}"
    )
