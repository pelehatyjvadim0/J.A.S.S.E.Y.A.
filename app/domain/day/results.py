from pydantic import BaseModel
from typing import Literal

from app.domain.day.entities import MorningBrief
from app.domain.day.entities import StepExecutionReport
from app.domain.day.entities import DependencyHealth
from app.domain.day.entities import EveningSummary

class StartDayResult(BaseModel):
    status: Literal['ok', 'failed'] # статус выполнения функции
    brief: MorningBrief # утренний бриф
    dependency_health: list[DependencyHealth] # здоровье зависимостей
    environment_reports: list[StepExecutionReport] # отчеты о среде выполнения
    checkpoint_loaded: bool # был ли загружен checkpoint

class EndDayResult(BaseModel):
    status: Literal['ok', 'failed'] # статус выполнения функции
    summary: EveningSummary # вечерний бриф
    checkpoint_saved: bool # был ли сохранен checkpoint на завтра
    save_report: StepExecutionReport | None = None # отчет о сохранении checkpoint