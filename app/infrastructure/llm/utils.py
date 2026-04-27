import json

from app.errors import GatewayError


def parse_json(raw_result: str) -> dict:
    cleaned = raw_result.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise GatewayError(f"LLM вернула невалидный JSON: {e}") from e
    except Exception as e:
        raise GatewayError(f"Непредвиденная ошибка при парсинге JSON: {e}") from e


def parse_json_with_facts(raw_result: str) -> dict:
    """Парсит JSON и гарантирует наличие списка фактов."""
    parsed = parse_json(raw_result)
    if "facts" not in parsed:
        raise GatewayError('LLM вернула JSON без поля "facts".')
    if not isinstance(parsed["facts"], list):
        raise GatewayError('Поле "facts" должно быть списком.')
    return parsed
