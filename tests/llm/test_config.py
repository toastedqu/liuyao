"""Tests for app.llm.config: per-provider env parsing and fail-fast behaviour.

Every loader must raise LLMConfigurationError -- never silently substitute
defaults or fall back to a different provider -- when a required variable
for the requested provider is missing.
"""

from __future__ import annotations

import pytest

from app.llm.config import (
    AnthropicProviderConfig,
    AzureOpenAIProviderConfig,
    OpenAIProviderConfig,
    load_anthropic_config,
    load_azure_openai_config,
    load_openai_config,
)
from app.llm.errors import LLMConfigurationError


def test_load_openai_config_success() -> None:
    env = {"OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "gpt-test"}
    config = load_openai_config(env)
    assert isinstance(config, OpenAIProviderConfig)
    assert config.api_key == "sk-test"
    assert config.model == "gpt-test"
    assert config.base_url is None
    assert config.temperature == 0.0


def test_load_openai_config_reads_optional_base_url() -> None:
    env = {"OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "gpt-test", "OPENAI_BASE_URL": "https://example.com/v1"}
    config = load_openai_config(env)
    assert config.base_url == "https://example.com/v1"


def test_provider_configs_read_shared_timeout() -> None:
    openai = load_openai_config(
        {
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_MODEL": "gpt-test",
            "LLM_TIMEOUT_SECONDS": "180",
        }
    )
    azure = load_azure_openai_config(
        {
            "AZURE_OPENAI_API_KEY": "key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            "AZURE_OPENAI_DEPLOYMENT": "gpt-deployment",
            "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
            "LLM_TIMEOUT_SECONDS": "180",
        }
    )
    anthropic = load_anthropic_config(
        {
            "ANTHROPIC_API_KEY": "key",
            "ANTHROPIC_MODEL": "claude-test",
            "LLM_TIMEOUT_SECONDS": "180",
        }
    )

    assert openai.timeout == azure.timeout == anthropic.timeout == 180


@pytest.mark.parametrize("value", ["not-a-number", "0", "601"])
def test_provider_config_rejects_invalid_timeout(value: str) -> None:
    with pytest.raises(LLMConfigurationError, match="LLM_TIMEOUT_SECONDS"):
        load_openai_config(
            {
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_MODEL": "gpt-test",
                "LLM_TIMEOUT_SECONDS": value,
            }
        )


@pytest.mark.parametrize("missing_key", ["OPENAI_API_KEY", "OPENAI_MODEL"])
def test_load_openai_config_missing_required_var_raises(missing_key: str) -> None:
    env = {"OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "gpt-test"}
    del env[missing_key]
    with pytest.raises(LLMConfigurationError, match=missing_key):
        load_openai_config(env)


def test_load_openai_config_empty_string_is_treated_as_missing() -> None:
    env = {"OPENAI_API_KEY": "   ", "OPENAI_MODEL": "gpt-test"}
    with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY"):
        load_openai_config(env)


def test_load_openai_config_rejects_nonzero_temperature() -> None:
    env = {"OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "gpt-test", "LLM_TEMPERATURE": "0.7"}
    with pytest.raises(LLMConfigurationError, match="temperature"):
        load_openai_config(env)


def test_load_openai_config_rejects_non_numeric_temperature() -> None:
    env = {"OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "gpt-test", "LLM_TEMPERATURE": "not-a-number"}
    with pytest.raises(LLMConfigurationError):
        load_openai_config(env)


def test_load_azure_openai_config_success() -> None:
    env = {
        "AZURE_OPENAI_API_KEY": "key",
        "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
        "AZURE_OPENAI_DEPLOYMENT": "gpt-deployment",
        "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
    }
    config = load_azure_openai_config(env)
    assert isinstance(config, AzureOpenAIProviderConfig)
    assert config.deployment == "gpt-deployment"


@pytest.mark.parametrize(
    "missing_key",
    ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_VERSION"],
)
def test_load_azure_openai_config_missing_required_var_raises(missing_key: str) -> None:
    env = {
        "AZURE_OPENAI_API_KEY": "key",
        "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
        "AZURE_OPENAI_DEPLOYMENT": "gpt-deployment",
        "AZURE_OPENAI_API_VERSION": "2024-02-15-preview",
    }
    del env[missing_key]
    with pytest.raises(LLMConfigurationError, match=missing_key):
        load_azure_openai_config(env)


def test_load_anthropic_config_success() -> None:
    env = {"ANTHROPIC_API_KEY": "key", "ANTHROPIC_MODEL": "claude-test"}
    config = load_anthropic_config(env)
    assert isinstance(config, AnthropicProviderConfig)
    assert config.model == "claude-test"


@pytest.mark.parametrize("missing_key", ["ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"])
def test_load_anthropic_config_missing_required_var_raises(missing_key: str) -> None:
    env = {"ANTHROPIC_API_KEY": "key", "ANTHROPIC_MODEL": "claude-test"}
    del env[missing_key]
    with pytest.raises(LLMConfigurationError, match=missing_key):
        load_anthropic_config(env)
