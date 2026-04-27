from app.domain.chat.entities import ChatMessage
from app.errors import GatewayError
from app.infrastructure.llm.base_client import BaseLLMClient
from settings import settings


class JasseyaAgent:
    def __init__(
        self,
        client: BaseLLMClient,
        model: str,
        temperature: float | None = None,
        top_k: int | None = None,
        top_p: float | None = None,
    ):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p

    def _log(self, message: str) -> None:
        if settings.MEMORY_PIPELINE_LOGS_ENABLED:
            print(f"[memory-gateway] {message}")

    async def generate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        if not prompt or not prompt.strip():
            raise GatewayError("Промпт не должен быть пустым.")
        return self.client.request_content(
            [
                {"role": "system", "content": system_prompt or settings.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model=self.model,
            temperature=self.temperature,
            top_k=self.top_k,
            top_p=self.top_p,
        )

    async def generate_from_messages(self, messages: list[ChatMessage]) -> str:
        if not messages:
            raise GatewayError("Список сообщений для генерации не должен быть пустым.")
        payload = [m.model_dump() for m in messages]
        return self.client.request_content(
            payload,
            model=self.model,
            temperature=self.temperature,
            top_k=self.top_k,
            top_p=self.top_p,
        )
