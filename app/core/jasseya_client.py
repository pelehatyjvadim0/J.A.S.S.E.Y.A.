from app.application.chat.use_cases.handle_user_turn import HandleUserTurnUseCase
from app.application.memory.use_cases.run_memory_pipeline import MemoryPipeline
from app.infrastructure.llm.gateway import OpenAIGateway
from app.infrastructure.vectorstore.qdrant_repository import QdrantMemoryRepository
from app.infrastructure.llm.reranker.agent import LLMReranker
from app.application.memory.services.memory_selector import MemorySelector
from app.domain.memory.retrieval import MemorySelectionConfig
from settings import settings

class JassyClient:
    def __init__(self, session_id: str):
        self.gateway = OpenAIGateway()
        self.memory = QdrantMemoryRepository(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        self.reranker = LLMReranker(
            client=self.gateway.reranker.client,
            model=settings.MEMORY_RERANK_MODEL,
            temperature=settings.MEMORY_RERANK_TEMPERATURE,
        )
        self.memory_selector = MemorySelector(
            reranker=self.reranker,
            config=MemorySelectionConfig(
                top_k=settings.MEMORY_RETRIEVAL_TOP_K,
                rerank_top_n=settings.MEMORY_RERANK_TOP_N,
                context_fact_limit=settings.MEMORY_CONTEXT_FACTS_LIMIT,
                min_vector_score=settings.MEMORY_MIN_VECTOR_SCORE,
                rerank_enabled=settings.MEMORY_RERANK_ENABLED,
            ),
        )
        self.memory_pipeline = MemoryPipeline(
            gateway=self.gateway,
            memory_repo=self.memory,
            session_id=session_id,
        )
        self.handle_user_turn = HandleUserTurnUseCase(
            gateway=self.gateway,
            memory_repo=self.memory,
            memory_selector=self.memory_selector,
            pipeline=self.memory_pipeline,
        )
        self.session_id = session_id

    def _log(self, message: str) -> None:
        if settings.MEMORY_PIPELINE_LOGS_ENABLED:
            print(f'[jasseya-client] {message}')

    async def generate_text(self, prompt: str) -> str:
        self._log(f'Входящий prompt: "{prompt}"')
        response = await self.handle_user_turn.execute(prompt)
        return response
