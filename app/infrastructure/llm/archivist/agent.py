from app.domain.memory.entities import SummaryBatch, SummaryResult
from app.errors import GatewayError
from app.infrastructure.llm.base_client import BaseLLMClient
from app.infrastructure.llm.utils import parse_json_with_facts
from settings import settings


class ArchivistAgent:
    def __init__(self, client: BaseLLMClient, model: str):
        self.client = client
        self.model = model

    def _log(self, message: str) -> None:
        if settings.MEMORY_PIPELINE_LOGS_ENABLED:
            print(f"[memory-gateway] {message}")

    async def summarize_dialog_batch(self, batch: SummaryBatch) -> SummaryResult:
        if not batch.messages:
            raise GatewayError("Пакет суммаризации не содержит сообщений.")

        messages_block = self._build_messages_block(batch)
        if not messages_block:
            raise GatewayError("В пакете суммаризации нет содержательных сообщений.")

        system_prompt = settings.SUMMARY_PROMPT.format(max_facts=settings.SUMMARY_MAX_FACTS)
        raw_result = self.client.request_content(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"messages:\n{messages_block}"},
            ],
            model=self.model,
            temperature=settings.ARCHIVIST_TEMPERATURE,
        )
        parsed = parse_json_with_facts(raw_result)
        facts = self._process_facts(parsed)

        self._log(f'Ответ от архивариуса: {raw_result}')
        self._log(
            f"Суммаризация batch: session_id={batch.session_id}, "
            f"range={batch.start_index}-{batch.end_index}, facts={len(facts)}"
        )
        return SummaryResult(
            facts=facts[:settings.SUMMARY_MAX_FACTS],
            start_index=batch.start_index,
            end_index=batch.end_index,
            session_id=batch.session_id,
        )

    def _build_messages_block(self, batch: SummaryBatch) -> str:
        role_map = {"user": "U", "assistant": "A", "system": "S"}
        result = []
        for m in batch.messages:
            if not m.content or not m.content.strip():
                continue
            role = role_map.get(m.role, m.role)
            result.append(f"{role}: {m.content.strip()}")

        msg_block = "\n".join(result)
        self._log(f'Блок сообщений для суммаризации: {msg_block}')
        return msg_block

    def _process_facts(self, parsed: dict) -> list[str]:
        normalized_facts: list[str] = []
        seen: set[str] = set()
        for fact in parsed.get("facts", []):
            if not isinstance(fact, str):
                continue
            cleaned = fact.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            normalized_facts.append(cleaned)
        return normalized_facts
