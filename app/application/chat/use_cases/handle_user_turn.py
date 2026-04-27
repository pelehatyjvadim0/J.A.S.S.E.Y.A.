from app.application.memory.use_cases.retrieve_context import retrieve_context_messages
from app.application.memory.use_cases.run_memory_pipeline import MemoryPipeline
from app.infrastructure.llm.gateway import OpenAIGateway
from app.infrastructure.vectorstore.qdrant_repository import QdrantMemoryRepository
from app.application.memory.services.memory_selector import MemorySelector


class HandleUserTurnUseCase:
    def __init__(
        self,
        gateway: OpenAIGateway,
        memory_repo: QdrantMemoryRepository,
        memory_selector: MemorySelector,
        pipeline: MemoryPipeline,
    ):
        self.gateway = gateway
        self.memory_repo = memory_repo
        self.memory_selector = memory_selector
        self.pipeline = pipeline

    async def execute(self, prompt: str) -> str:
        messages = await retrieve_context_messages(
            memory_repo=self.memory_repo,
            memory_selector=self.memory_selector,
            user_prompt=prompt,
            dialog_buffer=self.pipeline.dialog_buffer,
        )
        response = await self.gateway.generate_from_messages(messages)
        self.pipeline.add_turn(prompt, response)
        await self.pipeline.run_if_needed()
        return response
