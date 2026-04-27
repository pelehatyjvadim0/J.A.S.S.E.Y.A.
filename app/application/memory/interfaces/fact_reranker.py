from typing import Protocol

from app.domain.memory.retrieval import MemoryFactCandidate, RerankerFact

class FactReranker(Protocol):
    async def rerank(self, query: str, candidates: list[MemoryFactCandidate], top_n: int) -> list[RerankerFact]:
        ...