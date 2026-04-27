from app.domain.memory.entities import JudgeFactCandidate, JudgeFactResult
from app.errors import GatewayError
from app.infrastructure.llm.base_client import BaseLLMClient
from settings import settings


class JudgeAgent:
    def __init__(self, client: BaseLLMClient, model: str):
        self.client = client
        self.model = model

    def _log(self, message: str) -> None:
        if settings.MEMORY_PIPELINE_LOGS_ENABLED:
            print(f"[memory-gateway] {message}")

    async def judge_fact_relation(self, candidates: list[JudgeFactCandidate]) -> list[JudgeFactResult]:
        results: list[JudgeFactResult] = []
        for candidate in candidates:
            prompt = (
                f"old_fact: {candidate.old_fact}\n"
                f"new_fact: {candidate.new_fact}"
            )
            result = self.client.request_content(
                [
                    {"role": "system", "content": settings.FACT_JUDGE_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=self.model,
                temperature=settings.FACT_JUDGE_TEMPERATURE,
            )
            normalized = result.upper().strip()
            self._log(
                f'Judge raw answer="{result}", normalized="{normalized}", old_fact_id={candidate.old_fact_id}'
            )
            print(f'Запрос к судье: {prompt}')
            print(f'Ответ от судьи: {result}')
            if normalized not in ["REPLACE", "ADD", "IGNORE"]:
                raise GatewayError(
                    f"Судья вернул некорректный ответ при оценке отношений фактов: {result}"
                )
            results.append(
                JudgeFactResult(
                    old_fact=candidate.old_fact,
                    new_fact=candidate.new_fact,
                    old_fact_id=candidate.old_fact_id,
                    result=normalized,
                )
            )
        return results
