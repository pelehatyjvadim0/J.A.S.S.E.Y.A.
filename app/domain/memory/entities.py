from datetime import datetime
import uuid
from pydantic import BaseModel

from app.domain.chat.entities import DialogHistoryMessage


class SummaryBatch(BaseModel):
    start_index: int  # индекс первого сообщения в пакете
    end_index: int  # индекс последнего сообщения в пакете
    messages: list[DialogHistoryMessage]  # список сообщений в диалоге
    session_id: str  # id сессии


class SummaryResult(BaseModel):
    facts: list[str]  # список фактов
    start_index: int  # индекс первого сообщения в пакете
    end_index: int  # индекс последнего сообщения в пакете
    session_id: str  # id сессии


class FactPayload(BaseModel):
    content: str  # текст факта
    source: str  # источник факта
    session_id: str  # id сессии
    start_index: int  # индекс первого сообщения в пакете
    end_index: int  # индекс последнего сообщения в пакете
    created_at: datetime  # дата создания факта


class JudgeFactCandidate(BaseModel):
    old_fact: str  # существующий факт в памяти
    new_fact: str  # новый факт из суммаризации
    old_fact_id: uuid.UUID  # id существующего факта в Qdrant


class JudgeFactResult(BaseModel):
    old_fact: str  # существующий факт в памяти
    new_fact: str  # новый факт из суммаризации
    old_fact_id: uuid.UUID  # id существующего факта в Qdrant
    result: str  # результат оценки отношений фактов


class MemoryPipelineReport(BaseModel):
    session_id: str
    start_index: int | None = None
    end_index: int | None = None
    extracted_facts: int = 0
    saved_facts: int = 0
    judged_facts: int = 0
    replaced_facts: int = 0
    ignored_facts: int = 0
