import httpx

from app.core.logging import TraceContext, elapsed_ms, log_step_error, log_step_start, log_step_success, start_timer
from app.errors import ConfigurationError, EmbeddingError


class EmbeddingsClient:
    def __init__(self, model: str = "nomic-embed-text"):
        if not model:
            raise ConfigurationError("Не указано имя модели для эмбеддингов.")
        self.model = model
        self.url = "http://localhost:11434/api/embed"

    async def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise EmbeddingError("Текст для эмбеддинга не должен быть пустым.")
        trace = TraceContext(session_id=None, trace_id="infra-embeddings")
        started_at = start_timer()
        log_step_start(
            trace,
            "embeddings",
            "embed",
            message="Запрос эмбеддинга",
            meta={"model": self.model, "text_length": len(text.strip())},
        )
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                response = await client.post(self.url, json={"model": self.model, "input": text})
                response.raise_for_status()
                data = response.json()
                embeddings = data.get("embeddings")

                if not isinstance(embeddings, list) or len(embeddings) == 0:
                    raise EmbeddingError("Ответ сервиса содержит пустой список эмбеддингов.")

                first_vector = embeddings[0]
                if not isinstance(first_vector, list) or len(first_vector) == 0:
                    raise EmbeddingError("Ответ сервиса содержит некорректный первый вектор эмбеддинга.")
                log_step_success(
                    trace,
                    "embeddings",
                    "embed",
                    message="Эмбеддинг получен",
                    duration_ms=elapsed_ms(started_at),
                    meta={"model": self.model, "vector_size": len(first_vector)},
                )
                return first_vector
        except httpx.HTTPStatusError as e:
            log_step_error(
                trace,
                "embeddings",
                "embed",
                error=e,
                duration_ms=elapsed_ms(started_at),
                message="HTTP ошибка сервиса эмбеддингов",
                meta={"status_code": e.response.status_code},
            )
            raise EmbeddingError(
                f"Сервис эмбеддингов вернул HTTP ошибку {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.HTTPError as e:
            log_step_error(
                trace,
                "embeddings",
                "embed",
                error=e,
                duration_ms=elapsed_ms(started_at),
                message="Сетевая ошибка сервиса эмбеддингов",
            )
            raise EmbeddingError(f"Ошибка запроса к сервису эмбеддингов: {e}") from e
        except ValueError as e:
            log_step_error(
                trace,
                "embeddings",
                "embed",
                error=e,
                duration_ms=elapsed_ms(started_at),
                message="Ошибка разбора JSON ответа эмбеддингов",
            )
            raise EmbeddingError(f"Сервис эмбеддингов вернул некорректный JSON: {e}") from e
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, EmbeddingError)):
                raise
            log_step_error(
                trace,
                "embeddings",
                "embed",
                error=e,
                duration_ms=elapsed_ms(started_at),
                message="Непредвиденная ошибка эмбеддингов",
            )
            raise EmbeddingError(f"Непредвиденная ошибка эмбеддингов: {e}") from e
