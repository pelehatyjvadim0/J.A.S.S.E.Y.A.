from app.application.memory.interfaces.fact_reranker import FactReranker
from app.domain.memory.retrieval import MemoryFactCandidate, RerankerFact
from app.errors import GatewayError
from app.infrastructure.llm.base_client import BaseLLMClient
from app.infrastructure.llm.utils import parse_json
import uuid
import time
from settings import settings


MAX_RERANK_PARSE_ATTEMPTS = 3


class LLMReranker(FactReranker):
    def __init__(self, client: BaseLLMClient, model: str, temperature: float):
        self.client = client
        self.model = model
        self.temperature = temperature
        self._last_diagnostics: dict[str, float | int | str] = {}

    async def rerank(self, query: str, candidates: list[MemoryFactCandidate], top_n: int) -> list[RerankerFact]:
        started_at = time.perf_counter()
        if not candidates:
            self._last_diagnostics = self.build_rerank_diagnostics(
                rerank_input_count=0,
                rerank_output_count=0,
                rerank_ms=(time.perf_counter() - started_at) * 1000,
                model_name=self.model,
            )
            return []

        # Системный промпт для задания инструкции модели
        system_prompt = (
            "Оцени релевантность каждого кандидата к запросу пользователя.\n"
            "Для каждого кандидата верни оценку rerank_score в диапазоне от 0 до 1 (чем выше, тем релевантнее).\n"
            "Ответ должен быть ТОЛЬКО в виде JSON:\n"
            "{\"items\": [{\"fact_id\": \"<uuid>\", \"rerank_score\": <float>}, ...]}\n"
            "Никакого текста вне JSON."
        )
        # В user промпте только текст запроса и кандидаты
        user_prompt = (
            f"Запрос пользователя:\n{query}\n"
            "Кандидаты:\n" +
            "\n".join(
                [
                    f"{i + 1}. fact_id: {c.fact_id}, content: {c.content}"
                    for i, c in enumerate(candidates)
                ]
            )
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        parsed = self._request_and_parse_with_retries(messages=messages)
        print(f'Кандидаты: {candidates}')
        print(f'Ответ реранкера: {parsed}')
        if parsed is None:
            fallback_result = self._fallback_by_vector_score(candidates=candidates, top_n=top_n)
            self._last_diagnostics = self.build_rerank_diagnostics(
                rerank_input_count=len(candidates),
                rerank_output_count=len(fallback_result),
                rerank_ms=(time.perf_counter() - started_at) * 1000,
                model_name=self.model,
                fallback_reason="invalid_json_after_3_attempts",
            )
            return fallback_result
        if not parsed or "items" not in parsed or not isinstance(parsed["items"], list):
            self._last_diagnostics = self.build_rerank_diagnostics(
                rerank_input_count=len(candidates),
                rerank_output_count=0,
                rerank_ms=(time.perf_counter() - started_at) * 1000,
                model_name=self.model,
            )
            return []

        reranker_facts: list[RerankerFact] = []
        # Создаем индекс для быстрого поиска MemoryFactCandidate по fact_id
        candidate_map = {str(c.fact_id): c for c in candidates}

        for item in parsed["items"]:
            if not item or "fact_id" not in item or "rerank_score" not in item:
                continue
            fact_id_str = item["fact_id"]
            if fact_id_str not in candidate_map:
                continue  # Пропускаем item, если такого fact_id нет среди кандидатов

            candidate = candidate_map[fact_id_str]
            rerank_score = item["rerank_score"]
            final_score = self.get_final_score(rerank_score, candidate.vector_score)

            reranker_facts.append(
                RerankerFact(
                    candidate=MemoryFactCandidate(
                        fact_id=candidate.fact_id,
                        content=candidate.content,
                        vector_score=candidate.vector_score,
                        session_id=candidate.session_id,
                        created_at=candidate.created_at,
                        source=candidate.source,
                    ),
                    rerank_score=rerank_score,
                    final_score=final_score
                )
            )

            # После добавления всех фактов - сортировка по убыванию итогового score
            reranker_facts.sort(key=lambda x: x.final_score, reverse=True)
     
        result = reranker_facts[:top_n]
        self._last_diagnostics = self.build_rerank_diagnostics(
            rerank_input_count=len(candidates),
            rerank_output_count=len(result),
            rerank_ms=(time.perf_counter() - started_at) * 1000,
            model_name=self.model,
        )
        return result

    def get_final_score(self, rerank_score: float, vector_score: float) -> float:
        # Нормализация vector_score. Предполагаем, что vector_score >= 0, и максимальное возможное значение 1,
        # Если встречаются значения выше 1 -- считаем их за 1.0.
        vector_score_norm = min(max(vector_score, 0.0), 1.0)
        rerank_score_norm = min(max(rerank_score, 0.0), 1.0)  # Дополнительная защита

        final_score = (
            settings.MEMORY_VECTOR_WEIGHT * vector_score_norm
            + settings.MEMORY_RERANK_WEIGHT * rerank_score_norm
        )
        # Ограничиваем итоговый скор 0..1
        final_score = min(max(final_score, 0.0), 1.0)

        return final_score

    def _fallback_by_vector_score(
        self, candidates: list[MemoryFactCandidate], top_n: int
    ) -> list[RerankerFact]:
        fallback_facts = [
            RerankerFact(
                candidate=candidate,
                rerank_score=0.0,
                final_score=self.get_final_score(0.0, candidate.vector_score),
            )
            for candidate in candidates
        ]
        fallback_facts.sort(key=lambda x: x.final_score, reverse=True)
        return fallback_facts[:top_n]

    def _request_and_parse_with_retries(self, messages: list[dict[str, str]]) -> dict | None:
        for _ in range(MAX_RERANK_PARSE_ATTEMPTS):
            raw_result = self.client.request_content(
                messages,
                model=self.model,
                temperature=self.temperature,
            )
            try:
                return parse_json(raw_result)
            except GatewayError:
                continue
        return None

    def build_rerank_diagnostics(
        self,
        rerank_input_count: int,
        rerank_output_count: int,
        rerank_ms: float,
        model_name: str,
        fallback_reason: str | None = None,
    ) -> dict[str, float | int | str]:
        diagnostics: dict[str, float | int | str] = {
            "rerank_input_count": rerank_input_count,
            "rerank_output_count": rerank_output_count,
            "rerank_ms": round(rerank_ms, 3),
            "model_name": model_name,
        }
        if fallback_reason:
            diagnostics["fallback_reason"] = fallback_reason
        return diagnostics

    def get_last_diagnostics(self) -> dict[str, float | int | str]:
        return dict(self._last_diagnostics)



        

        
   
   

        
        