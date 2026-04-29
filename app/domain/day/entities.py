from re import S
from pydantic import BaseModel
from typing import Literal

class DependencyHealth(BaseModel):
    name: str # имя зависимости (llm, qdrant, local_env)
    status: Literal["ok", "failed"] # статус зависимости
    reason: str | None = None # причина ошибки


class MorningBrief(BaseModel):
    summary: str # короткий утрений бриф
    today_focus: str # что мы будем делать сегодня
    restored_checkpoint: str # где остановились вчера

class EveningSummary(BaseModel):
    summary: str # короткий вечерний бриф
    done_items: list[str] # что мы сделали
    blocked_items: list[str]
    first_step_tommorow: str # первый шаг на завтра
    warnings: list[str] # предупреждения

