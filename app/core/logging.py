import json
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from settings import settings


LOGGER_NAME = "jasseya.memory"
STATUS_START = "start"
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"

_logger = logging.getLogger(LOGGER_NAME)
if not _logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
_logger.setLevel(logging.INFO)
_logger.propagate = False


@dataclass(slots=True)
class TraceContext:
    session_id: str | None
    trace_id: str


def _safe_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    if not meta:
        return {}
    sanitized: dict[str, Any] = {}
    for key, value in meta.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = value
            continue
        if isinstance(value, list):
            sanitized[key] = [item for item in value if isinstance(item, (str, int, float, bool))]
            continue
        sanitized[key] = str(value)
    return sanitized


def log_step_event(
    context: TraceContext,
    component: str,
    step: str,
    status: str,
    *,
    message: str = "",
    duration_ms: float | None = None,
    attempt: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Пишет структурное событие шага с единым контрактом полей."""
    if not settings.MEMORY_PIPELINE_LOGS_ENABLED:
        return

    payload: dict[str, Any] = {
        "trace_id": context.trace_id,
        "session_id": context.session_id or "unknown",
        "component": component,
        "step": step,
        "status": status,
    }
    if message:
        payload["message"] = message
    if duration_ms is not None:
        payload["duration_ms"] = round(duration_ms, 3)
    if attempt is not None:
        payload["attempt"] = attempt
    if error_type:
        payload["error_type"] = error_type
    if error_message:
        payload["error_message"] = error_message
    safe_meta = _safe_meta(meta)
    if safe_meta:
        payload["meta"] = safe_meta

    _logger.info(json.dumps(payload, ensure_ascii=False))


def log_step_start(
    context: TraceContext,
    component: str,
    step: str,
    *,
    message: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    """Пишет событие старта шага."""
    log_step_event(context, component, step, STATUS_START, message=message, meta=meta)


def log_step_success(
    context: TraceContext,
    component: str,
    step: str,
    *,
    message: str = "",
    duration_ms: float | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Пишет событие успешного завершения шага."""
    log_step_event(
        context,
        component,
        step,
        STATUS_SUCCESS,
        message=message,
        duration_ms=duration_ms,
        meta=meta,
    )


def log_step_error(
    context: TraceContext,
    component: str,
    step: str,
    *,
    error: Exception,
    duration_ms: float | None = None,
    message: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    """Пишет событие ошибки шага."""
    log_step_event(
        context,
        component,
        step,
        STATUS_ERROR,
        message=message or "Ошибка на шаге пайплайна",
        duration_ms=duration_ms,
        error_type=type(error).__name__,
        error_message=str(error),
        meta=meta,
    )


def log_memory_selection_observability(
    context: TraceContext,
    candidates_total: int,
    dropped_by_vector_threshold: int,
    reranked_top_n: int,
    selected_count: int,
    top_reasons: list[str],
    query_length: int,
) -> None:
    """Пишет наблюдаемость по выбору фактов памяти в безопасном формате."""
    log_step_success(
        context,
        "retrieval",
        "memory_selection",
        message="Выбор фактов памяти завершён",
        meta={
            "query_length": query_length,
            "candidates_total": candidates_total,
            "dropped_by_vector_threshold": dropped_by_vector_threshold,
            "reranked_top_n": reranked_top_n,
            "selected_count": selected_count,
            "top_reasons": top_reasons[:3],
        },
    )


def start_timer() -> float:
    """Возвращает отметку времени для расчёта длительности шага."""
    return perf_counter()


def elapsed_ms(started_at: float) -> float:
    """Возвращает длительность шага в миллисекундах."""
    return (perf_counter() - started_at) * 1000
