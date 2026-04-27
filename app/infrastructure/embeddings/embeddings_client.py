import httpx

from app.errors import ConfigurationError, EmbeddingError
from settings import settings


class EmbeddingsClient:
    def __init__(self, model: str = "nomic-embed-text"):
        if not model:
            raise ConfigurationError("Не указано имя модели для эмбеддингов.")
        self.model = model
        self.url = "http://localhost:11434/api/embed"

    def _log(self, message: str) -> None:
        if settings.MEMORY_PIPELINE_LOGS_ENABLED:
            print(f"[memory-embeddings] {message}")

    async def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise EmbeddingError("Текст для эмбеддинга не должен быть пустым.")

        try:
            self._log(f"Запрос эмбеддинга: model={self.model}, text_len={len(text.strip())}")
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
                self._log(f"Эмбеддинг получен: vector_size={len(first_vector)}")
                return first_vector
        except httpx.HTTPStatusError as e:
            self._log(f"HTTP ошибка эмбеддингов: status={e.response.status_code}, body={e.response.text}")
            raise EmbeddingError(
                f"Сервис эмбеддингов вернул HTTP ошибку {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.HTTPError as e:
            self._log(f"Сетевая ошибка эмбеддингов: {e}")
            raise EmbeddingError(f"Ошибка запроса к сервису эмбеддингов: {e}") from e
        except ValueError as e:
            self._log(f"Ошибка JSON эмбеддингов: {e}")
            raise EmbeddingError(f"Сервис эмбеддингов вернул некорректный JSON: {e}") from e
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, EmbeddingError)):
                raise
            self._log(f"Непредвиденная ошибка эмбеддингов: {e}")
            raise EmbeddingError(f"Непредвиденная ошибка эмбеддингов: {e}") from e
