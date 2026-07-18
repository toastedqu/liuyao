"""Anthropic provider adapter.

Anthropic's Messages API has no JSON-mode equivalent to OpenAI's
``response_format``; structured output is obtained by forcing a single tool
call whose ``input_schema`` is the target Pydantic schema
(``tool_choice={"type": "tool", "name": ...}``). The SDK already parses the
tool call arguments into a ``dict`` (``ToolUseBlock.input``), so this
provider validates that dict directly instead of going through
:func:`app.llm.base.parse_structured_json`.
"""

from __future__ import annotations

from typing import Any

from app.llm.base import Message, ResponseT, validate_structured_payload
from app.llm.config import AnthropicProviderConfig
from app.llm.errors import (
    LLMDependencyError,
    LLMRateLimitError,
    LLMRequestError,
    LLMResponseError,
    LLMTimeoutError,
)

_TOOL_NAME = "emit_structured_divination_result"


def _import_sdk() -> tuple[Any, type]:
    """Import and return ``(anthropic_module, AsyncAnthropic)``.

    Factored out so tests can monkeypatch this single function to simulate
    the ``anthropic`` package being unavailable, without needing to actually
    uninstall it.
    """
    import anthropic
    from anthropic import AsyncAnthropic

    return anthropic, AsyncAnthropic


def _split_system_message(messages: list[Message]) -> tuple[str, list[dict[str, str]]]:
    system_parts = [message.content for message in messages if message.role == "system"]
    other = [
        {"role": message.role, "content": message.content}
        for message in messages
        if message.role != "system"
    ]
    return "\n\n".join(system_parts), other


def _build_tool(response_schema: type[ResponseT]) -> dict[str, Any]:
    return {
        "name": _TOOL_NAME,
        "description": f"返回符合 {response_schema.__name__} JSON Schema 的结构化断卦结果。",
        "input_schema": response_schema.model_json_schema(),
    }


def _extract_tool_input(response: Any) -> dict[str, Any] | None:
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == _TOOL_NAME:
            return block.input
    return None


class AnthropicProvider:
    """LLMProvider backed by the official Anthropic Python SDK."""

    def __init__(self, config: AnthropicProviderConfig) -> None:
        try:
            anthropic_module, async_anthropic_cls = _import_sdk()
        except ImportError as exc:
            raise LLMDependencyError(
                "未安装 anthropic 官方 SDK，请先执行 `pip install anthropic` 后再使用 Anthropic Provider。"
            ) from exc

        self._config = config
        self._exceptions = anthropic_module
        self._client = async_anthropic_cls(
            api_key=config.api_key,
            timeout=config.timeout,
            max_retries=0,
        )

    async def generate_structured(
        self,
        messages: list[Message],
        response_schema: type[ResponseT],
    ) -> ResponseT:
        system_text, other_messages = _split_system_message(messages)
        tool = _build_tool(response_schema)
        try:
            response = await self._client.messages.create(
                model=self._config.model,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                system=system_text,
                messages=other_messages,
                tools=[tool],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
            )
        except self._exceptions.APITimeoutError as exc:
            raise LLMTimeoutError(f"请求超时：{exc}") from exc
        except self._exceptions.RateLimitError as exc:
            raise LLMRateLimitError(f"请求被限流：{exc}") from exc
        except self._exceptions.APIError as exc:
            raise LLMRequestError(f"请求失败：{exc}") from exc

        tool_input = _extract_tool_input(response)
        if tool_input is None:
            raise LLMResponseError("Anthropic 未返回任何结构化工具调用结果。")
        return validate_structured_payload(tool_input, response_schema)
