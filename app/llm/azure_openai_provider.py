"""Azure OpenAI provider adapter.

Uses the same ``openai`` Python package (``AsyncAzureOpenAI``), which is why
it shares :class:`app.llm._chat_completions.OpenAICompatibleRequester` with
:class:`app.llm.openai_provider.OpenAIProvider`. ``model`` in the underlying
request is the Azure *deployment* name, not a model family name.
"""

from __future__ import annotations

from typing import Any

from app.llm._chat_completions import OpenAICompatibleRequester
from app.llm.base import Message, ResponseT
from app.llm.config import AzureOpenAIProviderConfig
from app.llm.errors import LLMDependencyError


def _import_sdk() -> tuple[Any, type]:
    """Import and return ``(openai_module, AsyncAzureOpenAI)``.

    Factored out so tests can monkeypatch this single function to simulate
    the ``openai`` package being unavailable, without needing to actually
    uninstall it.
    """
    import openai
    from openai import AsyncAzureOpenAI

    return openai, AsyncAzureOpenAI


class AzureOpenAIProvider:
    """LLMProvider backed by the official OpenAI Python SDK's Azure client."""

    def __init__(self, config: AzureOpenAIProviderConfig) -> None:
        try:
            openai_module, async_azure_openai_cls = _import_sdk()
        except ImportError as exc:
            raise LLMDependencyError(
                "未安装 openai 官方 SDK，请先执行 `pip install openai` 后再使用 Azure OpenAI Provider。"
            ) from exc

        self._config = config
        client = async_azure_openai_cls(
            api_key=config.api_key,
            azure_endpoint=config.endpoint,
            api_version=config.api_version,
            timeout=config.timeout,
            max_retries=0,
        )
        self._requester = OpenAICompatibleRequester(
            client=client,
            model=config.deployment,
            temperature=config.temperature,
            exceptions_module=openai_module,
        )

    async def generate_structured(
        self,
        messages: list[Message],
        response_schema: type[ResponseT],
    ) -> ResponseT:
        return await self._requester.generate_structured(messages, response_schema)
