"""OpenAI provider adapter.

The ``openai`` SDK is imported lazily inside :func:`_import_sdk` (called only
from ``OpenAIProvider.__init__``), so importing this module never fails just
because the ``openai`` package is missing -- only *constructing* an
``OpenAIProvider`` does, and it fails with a clear
:class:`app.llm.errors.LLMDependencyError`.
"""

from __future__ import annotations

from typing import Any

from app.llm._chat_completions import OpenAICompatibleRequester
from app.llm.base import Message, ResponseT
from app.llm.config import OpenAIProviderConfig
from app.llm.errors import LLMDependencyError


def _import_sdk() -> tuple[Any, type]:
    """Import and return ``(openai_module, AsyncOpenAI)``.

    Factored out so tests can monkeypatch this single function to simulate
    the ``openai`` package being unavailable, without needing to actually
    uninstall it.
    """
    import openai
    from openai import AsyncOpenAI

    return openai, AsyncOpenAI


class OpenAIProvider:
    """LLMProvider backed by the official OpenAI Python SDK."""

    def __init__(self, config: OpenAIProviderConfig) -> None:
        try:
            openai_module, async_openai_cls = _import_sdk()
        except ImportError as exc:
            raise LLMDependencyError(
                "未安装 openai 官方 SDK，请先执行 `pip install openai` 后再使用 OpenAI Provider。"
            ) from exc

        self._config = config
        client = async_openai_cls(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=0,
        )
        self._requester = OpenAICompatibleRequester(
            client=client,
            model=config.model,
            temperature=config.temperature,
            exceptions_module=openai_module,
        )

    async def generate_structured(
        self,
        messages: list[Message],
        response_schema: type[ResponseT],
    ) -> ResponseT:
        return await self._requester.generate_structured(messages, response_schema)
