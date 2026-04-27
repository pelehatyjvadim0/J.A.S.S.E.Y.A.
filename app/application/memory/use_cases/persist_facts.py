from app.domain.memory.entities import JudgeFactResult, SummaryResult
from app.infrastructure.vectorstore.qdrant_repository import QdrantMemoryRepository


async def persist_facts(
    memory_repo: QdrantMemoryRepository,
    facts: list[str],
    summary_result: SummaryResult,
) -> int:
    """Сохраняет новые факты в память и возвращает количество успешных сохранений."""
    for fact in facts:
        await memory_repo.add_summary_fact(
            text=fact,
            start_index=summary_result.start_index,
            end_index=summary_result.end_index,
            session_id=summary_result.session_id,
            source="summary",
        )
    return len(facts)


async def apply_judge_results(
    memory_repo: QdrantMemoryRepository,
    judge_results: list[JudgeFactResult],
    summary_result: SummaryResult,
) -> tuple[int, int]:
    """Применяет решения judge: (replaced_count, added_count)."""
    replaced_count = 0
    added_count = 0

    for result in judge_results:
        if result.result == "REPLACE":
            await memory_repo.delete_fact(result.old_fact_id)
            await memory_repo.add_summary_fact(
                text=result.new_fact,
                start_index=summary_result.start_index,
                end_index=summary_result.end_index,
                session_id=summary_result.session_id,
                source="summary",
            )
            replaced_count += 1
            continue

        if result.result == "ADD":
            await memory_repo.add_summary_fact(
                text=result.new_fact,
                start_index=summary_result.start_index,
                end_index=summary_result.end_index,
                session_id=summary_result.session_id,
                source="summary",
            )
            added_count += 1

    return replaced_count, added_count
