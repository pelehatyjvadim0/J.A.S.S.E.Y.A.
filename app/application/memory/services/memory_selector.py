from app.application.memory.interfaces.fact_reranker import FactReranker
from app.domain.memory.retrieval import MemoryFactCandidate, SelectedMemoryFacts, MemorySelectionConfig, RerankerFact
from typing import cast


class MemorySelector:
    def __init__(self, reranker: FactReranker, config: MemorySelectionConfig):
        self.reranker = reranker
        self.config = config

    async def select(self, query: str, candidates: list[MemoryFactCandidate]) -> SelectedMemoryFacts:
        reranked_facts: list[RerankerFact] = await self.reranker.rerank(query=query, candidates=candidates, top_n=self.config.rerank_top_n)
        diagnostics: dict[str, float | int | str] = {}
        get_last_diagnostics = getattr(self.reranker, "get_last_diagnostics", None)
        if callable(get_last_diagnostics):
            diagnostics = cast(dict[str, float | int | str], get_last_diagnostics())
        return SelectedMemoryFacts(
            facts=[item.candidate.content for item in reranked_facts],
            diagnostics=diagnostics,
        )