from app.domain.chat.entities import ChatMessage
from app.domain.memory.entities import JudgeFactCandidate, JudgeFactResult, SummaryBatch, SummaryResult
from app.infrastructure.llm.archivist.agent import ArchivistAgent
from app.infrastructure.llm.base_client import BaseLLMClient
from app.infrastructure.llm.jasseya.agent import JasseyaAgent
from app.infrastructure.llm.judge.agent import JudgeAgent
from app.infrastructure.llm.reranker.agent import LLMReranker
from app.domain.memory.retrieval import MemoryFactCandidate, RerankerFact
from settings import settings

class OpenAIGateway:
    def __init__(self):
        client = BaseLLMClient(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)
        self.jasseya = JasseyaAgent(
            client=client,
            model=settings.BASE_MODEL,
            temperature=settings.BASE_MODEL_TEMPERATURE,
            top_k=settings.BASE_MODEL_TOP_K,
            top_p=settings.BASE_MODEL_TOP_P,
        )
        self.archivist = ArchivistAgent(client=client, model=settings.BASE_MODEL)
        self.judge = JudgeAgent(client=client, model=settings.FACT_JUDGE_MODEL)
        self.reranker = LLMReranker(
            client=client,
            model=settings.MEMORY_RERANK_MODEL,
            temperature=settings.MEMORY_RERANK_TEMPERATURE,
        )

    async def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        return await self.jasseya.generate_text(prompt=prompt, system_prompt=system_prompt)

    async def generate_from_messages(self, messages: list[ChatMessage]) -> str:
        return await self.jasseya.generate_from_messages(messages)

    async def summarize_dialog_batch(self, batch: SummaryBatch) -> SummaryResult:
        return await self.archivist.summarize_dialog_batch(batch)

    async def judge_fact_relation(self, candidates: list[JudgeFactCandidate]) -> list[JudgeFactResult]:
        return await self.judge.judge_fact_relation(candidates)

    async def rerank(self, query: str, candidates: list[MemoryFactCandidate], top_n: int) -> list[RerankerFact]:
        return await self.reranker.rerank(query=query, candidates=candidates, top_n=top_n)
