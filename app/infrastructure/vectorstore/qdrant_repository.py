from datetime import datetime
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointIdsList, PointStruct, ScoredPoint, VectorParams

from app.core.logging import TraceContext, elapsed_ms, log_step_error, log_step_success, start_timer
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

    def _trace_context(self, session_id: str | None = None) -> TraceContext:
        return TraceContext(session_id=session_id, trace_id="infra-qdrant")

    def _log_success(
        self,
        step: str,
        message: str,
        *,
        session_id: str | None = None,
        duration_ms: float | None = None,
        meta: dict | None = None,
    ) -> None:
        log_step_success(
            self._trace_context(session_id=session_id),
            "vectorstore",
            step,
            message=message,
            duration_ms=duration_ms,
            meta=meta,
        )

    def _log_error(
        self,
        step: str,
        error: Exception,
        *,
        session_id: str | None = None,
        duration_ms: float | None = None,
        message: str = "",
        meta: dict | None = None,
    ) -> None:
        log_step_error(
            self._trace_context(session_id=session_id),
            "vectorstore",
            step,
            error=error,
            duration_ms=duration_ms,
            message=message or "Ошибка работы с Qdrant",
            meta=meta,
        )

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

        started_at = start_timer()
        try:
            vector = await self.embeddings_client.embed(text)
            self.client.upsert(
                collection_name=self.collection_name,
                points=[PointStruct(id=uuid.uuid4(), vector=vector, payload=payload)],
            )
            self._log_success(
                "add_summary_fact",
                "Факт сохранён в vectorstore",
                session_id=session_id,
                duration_ms=elapsed_ms(started_at),
                meta={
                    "source": source,
                    "start_index": start_index,
                    "end_index": end_index,
                    "fact_length": len(text.strip()),
                },
            )
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, VectorStoreError)):
                raise
            self._log_error(
                "add_summary_fact",
                e,
                session_id=session_id,
                duration_ms=elapsed_ms(started_at),
                message="Ошибка сохранения факта в vectorstore",
                meta={"start_index": start_index, "end_index": end_index},
            )
            raise VectorStoreError(f"Не удалось добавить факт в Qdrant: {e}") from e

    async def _search_points(self, query: str, limit: int = 3) -> list[ScoredPoint]:
        started_at = start_timer()
        try:
            query_vector = await self.embeddings_client.embed(query)
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                score_threshold=settings.MEMORY_MIN_VECTOR_SCORE,
            )
            self._log_success(
                "search_points",
                "Поиск points выполнен",
                duration_ms=elapsed_ms(started_at),
                meta={"query_length": len(query.strip()), "limit": limit, "found_points": len(response.points)},
            )
            return response.points
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, VectorStoreError)):
                raise
            self._log_error(
                "search_points",
                e,
                duration_ms=elapsed_ms(started_at),
                message="Ошибка поиска points в Qdrant",
                meta={"query_length": len(query.strip()), "limit": limit},
            )
            raise VectorStoreError(f"Не удалось выполнить поиск points в Qdrant: {e}") from e

    def _get_content_from_points(self, points: list[ScoredPoint]) -> list[str]:
        contents: list[str] = []
        for hit in points:
            if hit.payload and "content" in hit.payload:
                contents.append(hit.payload["content"])
        return contents


    async def search_facts(self, query: str, limit: int = 3) -> list[str]:
        started_at = start_timer()
        try:
            results = await self._search_points(query, limit)
            contents = self._get_content_from_points(results)
            self._log_success(
                "search_facts",
                "Поиск фактов завершён",
                duration_ms=elapsed_ms(started_at),
                meta={"query_length": len(query.strip()), "limit": limit, "facts_count": len(contents)},
            )
            return contents
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, VectorStoreError)):
                raise
            self._log_error(
                "search_facts",
                e,
                duration_ms=elapsed_ms(started_at),
                message="Ошибка поиска фактов",
                meta={"query_length": len(query.strip()), "limit": limit},
            )
            raise VectorStoreError(f"Не удалось выполнить поиск фактов в Qdrant: {e}") from e

    async def search_facts_with_score(self, query: str, limit: int) -> list[MemoryFactCandidate]:
        started_at = start_timer()
        try:
            points_result = await self._search_points(query, limit)
            if not points_result:
                return []
            fact_candidates: list[MemoryFactCandidate] = []

            for point in points_result:
                if not point.payload or "content" not in point.payload:
                    self._log_success(
                        "search_facts_with_score",
                        "Точка пропущена: нет payload.content",
                        meta={"point_id": str(point.id)},
                    )
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
            self._log_error(
                "search_facts_with_score",
                e,
                duration_ms=elapsed_ms(started_at),
                message="Ошибка поиска фактов с score",
                meta={"query_length": len(query.strip()), "limit": limit},
            )
            raise VectorStoreError(f"Не удалось выполнить поиск фактов с score в Qdrant: {e}") from e

    async def find_most_similar_fact(self, new_fact: str) -> tuple[str, float, uuid.UUID] | None:
        fact_point = await self._search_points(new_fact, limit=1)
        if fact_point:
            fact_content = self._get_content_from_points(fact_point)
            if not fact_content:
                self._log_success(
                    "find_most_similar_fact",
                    "Похожая точка без payload.content",
                    meta={"query_length": len(new_fact.strip())},
                )
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
            self._log_success(
                "find_most_similar_fact",
                "Найден похожий факт",
                meta={
                    "score": round(float(fact_point[0].score), 4),
                    "fact_id": str(fact_id),
                    "old_fact_length": len(fact_content[0].strip()),
                    "new_fact_length": len(new_fact.strip()),
                },
            )
            return fact_content[0], fact_point[0].score, fact_id
        self._log_success(
            "find_most_similar_fact",
            "Похожий факт не найден",
            meta={"query_length": len(new_fact.strip())},
        )
        return None

    async def delete_fact(self, fact_id: uuid.UUID) -> None:
        started_at = start_timer()
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=[str(fact_id)]),
            )
            self._log_success(
                "delete_fact",
                "Факт удалён из vectorstore",
                duration_ms=elapsed_ms(started_at),
                meta={"fact_id": str(fact_id)},
            )
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, VectorStoreError)):
                raise
            self._log_error(
                "delete_fact",
                e,
                duration_ms=elapsed_ms(started_at),
                message="Ошибка удаления факта из vectorstore",
                meta={"fact_id": str(fact_id)},
            )
            raise VectorStoreError(f"Не удалось удалить факт из Qdrant: {e}") from e
