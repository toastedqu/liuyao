"""Shared request/response mapping for OpenAI-compatible chat completions.

Both :mod:`app.llm.openai_provider` and :mod:`app.llm.azure_openai_provider`
talk to the same ``chat.completions.create`` shape (they only differ in how
the underlying client is constructed and which value is passed as
``model``), so the actual request mapping and error translation lives here
once.
"""

from __future__ import annotations

from typing import Any

from app.llm.base import Message, ResponseT, parse_structured_json
from app.llm.errors import LLMRequestError, LLMResponseError, LLMTimeoutError, LLMRateLimitError


def _message_payload(messages: list[Message]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def _response_format(response_schema: type[ResponseT]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": response_schema.__name__,
            "schema": response_schema.model_json_schema(),
        },
    }


def _extract_content(response: Any) -> str | None:
    try:
        return response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise LLMResponseError("模型返回结果结构异常，缺少 choices[0].message.content。") from exc


def _rejects_temperature(error: Exception) -> bool:
    body = getattr(error, "body", None)
    return (
        isinstance(body, dict)
        and body.get("param") == "temperature"
        and body.get("code") in {"unsupported_parameter", "unsupported_value"}
    )


class OpenAICompatibleRequester:
    """Owns the ``chat.completions.create`` call shared by OpenAI-shaped providers.

    ``exceptions_module`` is the imported ``openai`` module (used both by the
    real OpenAI SDK and the Azure OpenAI SDK, since ``AsyncAzureOpenAI`` is
    part of the same ``openai`` package and raises the same exception
    classes), used to translate SDK errors without hardcoding provider names.
    """

    def __init__(self, client: Any, model: str, temperature: float, exceptions_module: Any) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature
        self._exceptions = exceptions_module
        self._send_temperature = True

    async def generate_structured(
        self,
        messages: list[Message],
        response_schema: type[ResponseT],
    ) -> ResponseT:
        while True:
            request = {
                "model": self._model,
                "messages": _message_payload(messages),
                "response_format": _response_format(response_schema),
            }
            if self._send_temperature:
                request["temperature"] = self._temperature
            try:
                response = await self._client.chat.completions.create(**request)
                break
            except self._exceptions.APITimeoutError as exc:
                raise LLMTimeoutError(f"请求超时：{exc}") from exc
            except self._exceptions.RateLimitError as exc:
                raise LLMRateLimitError(f"请求被限流：{exc}") from exc
            except self._exceptions.APIError as exc:
                if self._send_temperature and _rejects_temperature(exc):
                    self._send_temperature = False
                    continue
                raise LLMRequestError(f"请求失败：{exc}") from exc

        content = _extract_content(response)
        return parse_structured_json(content, response_schema)
