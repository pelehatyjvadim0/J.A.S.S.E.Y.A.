from pydantic import BaseModel
from typing import Literal

class DependencyHealth(BaseModel):
    name: str # имя зависимости (llm, qdrant, local_env)
    status: Literal["ok", "failed"] # статус зависимости
    reason: str | None = None # причина ошибки

class MorningBrief(BaseModel):
    summary: str # короткий утрений бриф
    today_focus: list[str] # что мы будем делать сегодня
    restored_checkpoint: str # где остановились вчера

class EveningSummary(BaseModel):
    summary: str # короткий вечерний бриф
    done_items: list[str] # что мы сделали
    blocked_items: list[str]
    first_step_tomorrow: str # первый шаг на завтра

class StepExecutionReport(BaseModel):
    step_name: str # имя шага
    status: Literal['success', 'failed', 'skipped'] # статус выполнения шага
    duration_ms: int # продолжительность выполнения шага в миллисекундах
    error_message: str | None = None # сообщение об ошибке

class DayStatePayload(BaseModel):
    day_id: str # id дня
    last_context: str | None = None # последний контекст
    first_step_tomorrow: str # первый шаг на завтра


