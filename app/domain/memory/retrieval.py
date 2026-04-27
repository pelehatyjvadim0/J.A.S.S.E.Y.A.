from datetime import datetime
from re import L
from pydantic import BaseModel
import uuid

# вход в модуль, кандидаты на реранк
class MemoryFactCandidate(BaseModel):
    fact_id: uuid.UUID # id факта в Qdrant
    content: str # текст факта
    vector_score: float # score вектора факта
    session_id: str | None # id сессии
    created_at: datetime | None # дата создания факта
    source: str | None # источник факта

# выход после реранка внутри модуля
# отделить скор реранка от score вектора, чтобы не было смешивания и не было путаницы
class RerankerFact(BaseModel):
    candidate: MemoryFactCandidate # кандидат на реранк
    rerank_score: float # score реранка факта
    final_score: float # final score факта (score вектора + score реранка)

# выход из модуля, список фактов и метрики диагностики почему выбраны именно эти факты
class SelectedMemoryFacts(BaseModel):
    facts: list[str] # список выбранных фактов
    diagnostics: dict[str, float | int | str] # диагностика выбора факта

class MemorySelectionConfig(BaseModel):
    top_k: int
    rerank_top_n: int
    context_fact_limit: int
    min_vector_score: float
    rerank_enabled: bool
    