from app.domain.memory.entities import SummaryBatch, SummaryResult
from app.infrastructure.llm.gateway import OpenAIGateway


async def summarize_dialog_batch(gateway: OpenAIGateway, batch: SummaryBatch) -> SummaryResult:
    """Запускает суммаризацию текущего батча диалога."""
    return await gateway.summarize_dialog_batch(batch)
