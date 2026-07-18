"""Provider selection: the single place that turns ``LLM_PROVIDER`` + env into
a constructed :class:`app.llm.base.LLMProvider`.

Per implementation_plan.md §11.1, exactly one provider is initialized at
startup, and each provider's SDK module is imported lazily -- selecting
``anthropic`` never requires ``openai``/``azure_openai`` configuration or
packages to be present, and vice versa.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from app.llm.base import LLMProvider
from app.llm.config import load_anthropic_config, load_azure_openai_config, load_openai_config
from app.llm.errors import LLMConfigurationError

_PROVIDER_ALIASES: dict[str, str] = {
    "openai": "openai",
    "azure_openai": "azure_openai",
    "azure-openai": "azure_openai",
    "azure": "azure_openai",
    "anthropic": "anthropic",
}


def get_llm_provider(
    provider: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> LLMProvider:
    """Construct the ``LLMProvider`` named by ``provider`` (or ``LLM_PROVIDER``).

    Raises :class:`LLMConfigurationError` if no provider name can be
    determined, the name is unsupported, or the resolved provider is missing
    required configuration. Never falls back to a different provider.
    """
    env = env if env is not None else os.environ
    raw_name = provider if provider is not None else env.get("LLM_PROVIDER")
    if raw_name is None or not raw_name.strip():
        raise LLMConfigurationError(
            "缺少 LLM_PROVIDER 环境变量，无法确定使用哪个大语言模型 Provider。"
        )

    name = _PROVIDER_ALIASES.get(raw_name.strip().lower())
    if name is None:
        raise LLMConfigurationError(
            f"不支持的 LLM_PROVIDER={raw_name!r}，仅支持 openai、azure_openai、anthropic。"
        )

    if name == "openai":
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(load_openai_config(env))
    if name == "azure_openai":
        from app.llm.azure_openai_provider import AzureOpenAIProvider

        return AzureOpenAIProvider(load_azure_openai_config(env))

    from app.llm.anthropic_provider import AnthropicProvider

    return AnthropicProvider(load_anthropic_config(env))
