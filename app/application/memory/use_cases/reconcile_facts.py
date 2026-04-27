from dataclasses import dataclass, field

from app.domain.memory.entities import JudgeFactCandidate
from app.domain.memory.policies import SimilarityDecision, classify_similarity
from app.infrastructure.vectorstore.qdrant_repository import QdrantMemoryRepository
from settings import settings


@dataclass(slots=True)
class ReconcileResult:
    facts_to_save: list[str] = field(default_factory=list)
    facts_to_judge: list[JudgeFactCandidate] = field(default_factory=list)
    skipped_facts: list[str] = field(default_factory=list)


async def reconcile_facts(
    memory_repo: QdrantMemoryRepository,
    facts: list[str],
    low_threshold: float = settings.FACT_SIMILARITY_LOW,
    high_threshold: float = settings.FACT_SIMILARITY_HIGH,
) -> ReconcileResult:
    """Определяет судьбу каждого нового факта: сохранить, отправить в judge или пропустить."""
    result = ReconcileResult()

    for fact in facts:
        most_similar_fact = await memory_repo.find_most_similar_fact(fact)
        if most_similar_fact is None:
            result.facts_to_save.append(fact)
            continue

        old_fact, fact_score, fact_id = most_similar_fact
        decision = classify_similarity(
            score=fact_score,
            low=low_threshold,
            high=high_threshold,
        )
        if decision is SimilarityDecision.SAVE:
            result.facts_to_save.append(fact)
        elif decision is SimilarityDecision.JUDGE:
            result.facts_to_judge.append(
                JudgeFactCandidate(old_fact=old_fact, new_fact=fact, old_fact_id=fact_id)
            )
        else:
            result.skipped_facts.append(fact)

    return result
