from datetime import datetime
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointIdsList, PointStruct, ScoredPoint, VectorParams

from app.domain.memory.entities import FactPayload
from app.domain.memory.retrieval import MemoryFactCandidate
from app.errors import ConfigurationError, VectorStoreError
from app.infrastructure.embeddings.embeddings_client import EmbeddingsClient
from settings import settings


class QdrantMemoryRepository:
    def __init__(self, host: str, port: int):
        if not host:
            raise ConfigurationError("Не указан хост Qdrant.")
        if not isinstance(port, int) or port <= 0:
            raise ConfigurationError("Порт Qdrant должен быть положительным целым числом.")

        self.client = QdrantClient(host=host, port=port, trust_env=False)
        self.collection_name = "agent_memories"
        self.embeddings_client = EmbeddingsClient()
        self._ensure_collection()

    def _log(self, message: str) -> None:
        if settings.MEMORY_PIPELINE_LOGS_ENABLED:
            print(f"[memory-qdrant] {message}")

    def _ensure_collection(self) -> None:
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                )
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, VectorStoreError)):
                raise
            raise VectorStoreError(f"Не удалось инициализировать коллекцию Qdrant: {e}") from e

    async def add_summary_fact(
        self,
        text: str,
        start_index: int,
        end_index: int,
        session_id: str,
        metadata: dict | None = None,
        source: str = "summary",
    ) -> None:
        fact_payload = FactPayload(
            content=text,
            source=source,
            session_id=session_id,
            start_index=start_index,
            end_index=end_index,
            created_at=datetime.now(),
        )
        payload = fact_payload.model_dump()
        if metadata:
            payload.update(metadata)

        try:
            vector = await self.embeddings_client.embed(text)
            self.client.upsert(
                collection_name=self.collection_name,
                points=[PointStruct(id=uuid.uuid4(), vector=vector, payload=payload)],
            )
            self._log(
                f'Факт сохранён: session_id={session_id}, source={source}, range={start_index}-{end_index}, fact="{text}"'
            )
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, VectorStoreError)):
                raise
            self._log(
                f"Ошибка сохранения факта: session_id={session_id}, range={start_index}-{end_index}, причина={e}"
            )
            raise VectorStoreError(f"Не удалось добавить факт в Qdrant: {e}") from e

    async def _search_points(self, query: str, limit: int = 3) -> list[ScoredPoint]:
        try:
            query_vector = await self.embeddings_client.embed(query)
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                score_threshold=settings.MEMORY_MIN_VECTOR_SCORE,
            )
            self._log(f'Поиск points: query="{query}", limit={limit}, найдено={len(response.points)}')
            return response.points
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, VectorStoreError)):
                raise
            raise VectorStoreError(f"Не удалось выполнить поиск points в Qdrant: {e}") from e

    def _get_content_from_points(self, points: list[ScoredPoint]) -> list[str]:
        contents: list[str] = []
        for hit in points:
            if hit.payload and "content" in hit.payload:
                contents.append(hit.payload["content"])
        return contents


    async def search_facts(self, query: str, limit: int = 3) -> list[str]:
        try:
            results = await self._search_points(query, limit)
            contents = self._get_content_from_points(results)
            self._log(f'Поиск фактов: query="{query}", limit={limit}, фактов={len(contents)}')
            return contents
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, VectorStoreError)):
                raise
            self._log(f'Ошибка поиска фактов: query="{query}", причина={e}')
            raise VectorStoreError(f"Не удалось выполнить поиск фактов в Qdrant: {e}") from e

    async def search_facts_with_score(self, query: str, limit: int) -> list[MemoryFactCandidate]:
        try:
            points_result = await self._search_points(query, limit)
            if not points_result:
                return []
            fact_candidates: list[MemoryFactCandidate] = []

            for point in points_result:
                if not point.payload or "content" not in point.payload:
                    self._log(f'У найденной точки нет payload.content для факта: "{point.id}"')
                    continue
                fact_candidates.append(
                    MemoryFactCandidate(
                        fact_id=uuid.UUID(str(point.id)),
                        content=point.payload["content"],
                        vector_score=point.score,
                        session_id=point.payload["session_id"],
                        created_at=point.payload["created_at"],
                        source=point.payload["source"],
                    )
                )
            return fact_candidates
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, VectorStoreError)):
                raise
            self._log(f'Ошибка поиска фактов с score: query="{query}", причина={e}')
            raise VectorStoreError(f"Не удалось выполнить поиск фактов с score в Qdrant: {e}") from e

    async def find_most_similar_fact(self, new_fact: str) -> tuple[str, float, uuid.UUID] | None:
        fact_point = await self._search_points(new_fact, limit=1)
        if fact_point:
            fact_content = self._get_content_from_points(fact_point)
            if not fact_content:
                self._log(f'У найденной точки нет payload.content для факта: "{new_fact}"')
                return None
            raw_id = fact_point[0].id
            if isinstance(raw_id, uuid.UUID):
                fact_id = raw_id
            elif isinstance(raw_id, str):
                try:
                    fact_id = uuid.UUID(raw_id)
                except ValueError as e:
                    raise VectorStoreError(f"Некорректный UUID id точки Qdrant: {raw_id}") from e
            else:
                raise VectorStoreError(
                    f"Ожидался UUID id точки Qdrant, получен тип {type(raw_id).__name__}: {raw_id}"
                )
            self._log(
                f'Найден похожий факт: score={fact_point[0].score:.4f}, id={fact_id}, '
                f'old_fact="{fact_content[0]}", new_fact="{new_fact}"'
            )
            return fact_content[0], fact_point[0].score, fact_id
        self._log(f'Похожий факт не найден: "{new_fact}"')
        return None

    async def delete_fact(self, fact_id: uuid.UUID) -> None:
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=[str(fact_id)]),
            )
            self._log(f"Факт удалён: fact_id={fact_id}")
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, VectorStoreError)):
                raise
            self._log(f"Ошибка удаления факта: fact_id={fact_id}, причина={e}")
            raise VectorStoreError(f"Не удалось удалить факт из Qdrant: {e}") from e
