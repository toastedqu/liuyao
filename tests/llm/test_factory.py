"""Tests for app.llm.factory.get_llm_provider: provider dispatch and
fail-fast/no-silent-fallback behaviour.
"""

from __future__ import annotations

import pytest

from app.llm.anthropic_provider import AnthropicProvider
from app.llm.azure_openai_provider import AzureOpenAIProvider
from app.llm.errors import LLMConfigurationError
from app.llm.factory import get_llm_provider
from app.llm.openai_provider import OpenAIProvider

OPENAI_ENV = {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "gpt-test"}
AZURE_ENV = {
    "LLM_PROVIDER": "azure_openai",
    "AZURE_OPENAI_API_KEY": "key",
    "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-deployment",
    "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
}
ANTHROPIC_ENV = {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "key", "ANTHROPIC_MODEL": "claude-test"}


def test_get_llm_provider_dispatches_openai() -> None:
    provider = get_llm_provider(env=OPENAI_ENV)
    assert isinstance(provider, OpenAIProvider)


def test_get_llm_provider_dispatches_azure_openai() -> None:
    provider = get_llm_provider(env=AZURE_ENV)
    assert isinstance(provider, AzureOpenAIProvider)


def test_get_llm_provider_dispatches_anthropic() -> None:
    provider = get_llm_provider(env=ANTHROPIC_ENV)
    assert isinstance(provider, AnthropicProvider)


def test_get_llm_provider_explicit_provider_argument_overrides_env() -> None:
    env = {**ANTHROPIC_ENV, "LLM_PROVIDER": "openai"}
    provider = get_llm_provider("anthropic", env=env)
    assert isinstance(provider, AnthropicProvider)


def test_get_llm_provider_missing_llm_provider_raises() -> None:
    with pytest.raises(LLMConfigurationError, match="LLM_PROVIDER"):
        get_llm_provider(env={})


def test_get_llm_provider_unsupported_provider_raises() -> None:
    with pytest.raises(LLMConfigurationError, match="不支持的 LLM_PROVIDER"):
        get_llm_provider(env={"LLM_PROVIDER": "some-other-vendor"})


def test_get_llm_provider_does_not_silently_fall_back_when_config_missing() -> None:
    """Selecting openai with only anthropic configured must fail, not silently use anthropic."""
    env = {**ANTHROPIC_ENV, "LLM_PROVIDER": "openai"}
    with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY"):
        get_llm_provider(env=env)


def test_get_llm_provider_azure_alias_names() -> None:
    for alias in ("azure", "azure-openai", "AZURE_OPENAI"):
        env = {**AZURE_ENV, "LLM_PROVIDER": alias}
        provider = get_llm_provider(env=env)
        assert isinstance(provider, AzureOpenAIProvider)
