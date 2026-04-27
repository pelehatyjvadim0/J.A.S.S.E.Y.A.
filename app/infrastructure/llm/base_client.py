from typing import Any

import httpx
import openai

from app.errors import ConfigurationError, GatewayError


class BaseLLMClient:
    def __init__(self, base_url: str, api_key: str):
        if not base_url or not api_key:
            raise ConfigurationError("Конфигурация шлюза LLM заполнена не полностью.")
        self.client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=httpx.Client(trust_env=False),
        )

    def request_content(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float | None = None,
        top_k: int | None = None,
        top_p: float | None = None,
    ) -> str:
        try:
            extra_body: dict[str, dict[str, float | int]] | None = None
            options: dict[str, float | int] = {}
            if top_k is not None:
                options["top_k"] = top_k
            if top_p is not None:
                options["top_p"] = top_p
            if options:
                extra_body = {"options": options}

            response = self.client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                extra_body=extra_body,
            )
            return self._extract_content(response)
        except openai.APIError as e:
            raise GatewayError(f"Ошибка запроса к шлюзу LLM: {e}") from e
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, GatewayError)):
                raise
            raise GatewayError(f"Непредвиденная ошибка шлюза LLM: {e}") from e

    def _extract_content(self, response: Any) -> str:
        choices = response.choices
        if not choices:
            raise GatewayError("Шлюз LLM вернул пустой список вариантов ответа.")
        message = choices[0].message
        content = message.content if message else None
        if content is None:
            raise GatewayError("Ответ шлюза LLM не содержит текста сообщения.")
        return content
