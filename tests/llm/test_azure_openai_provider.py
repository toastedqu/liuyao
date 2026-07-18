"""Tests for app.llm.azure_openai_provider: request mapping and error translation.

Mirrors test_openai_provider.py, but also checks Azure-specific client
construction (``azure_endpoint``/``api_version``) and that the deployment
name (not a model family name) is sent as ``model``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.llm.azure_openai_provider as azure_provider_module
from app.llm.azure_openai_provider import AzureOpenAIProvider
from app.llm.base import Message
from app.llm.config import AzureOpenAIProviderConfig
from app.llm.errors import LLMDependencyError, LLMRateLimitError, LLMRequestError, LLMResponseError, LLMTimeoutError
from app.llm.schemas import DivinationConclusion


class FakeAPITimeoutError(Exception):
    pass


class FakeRateLimitError(Exception):
    pass


class FakeAPIError(Exception):
    pass


def _fake_openai_module() -> SimpleNamespace:
    return SimpleNamespace(
        APITimeoutError=FakeAPITimeoutError,
        RateLimitError=FakeRateLimitError,
        APIError=FakeAPIError,
    )


class FakeAsyncAzureOpenAI:
    last_instance: "FakeAsyncAzureOpenAI | None" = None

    def __init__(self, **kwargs: object) -> None:
        self.init_kwargs = kwargs
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        FakeAsyncAzureOpenAI.last_instance = self


def _response_with_content(content: str) -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@pytest.fixture
def config() -> AzureOpenAIProviderConfig:
    return AzureOpenAIProviderConfig(
        api_key="key",
        endpoint="https://example.openai.azure.com",
        deployment="gpt-deployment",
        api_version="2024-02-15-preview",
        temperature=0.0,
    )


@pytest.fixture(autouse=True)
def patched_sdk(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        azure_provider_module, "_import_sdk", lambda: (_fake_openai_module(), FakeAsyncAzureOpenAI)
    )


SAMPLE_MESSAGES = [
    Message(role="system", content="系统提示"),
    Message(role="user", content="用户问题"),
]


async def test_generate_structured_uses_deployment_as_model(config, sample_conclusion) -> None:
    provider = AzureOpenAIProvider(config)
    client = FakeAsyncAzureOpenAI.last_instance
    assert client is not None
    client.chat.completions.create.return_value = _response_with_content(sample_conclusion.model_dump_json())

    result = await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)

    assert result == sample_conclusion
    call_kwargs = client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-deployment"
    assert call_kwargs["temperature"] == 0.0


def test_client_constructed_with_azure_specific_kwargs(config) -> None:
    AzureOpenAIProvider(config)
    client = FakeAsyncAzureOpenAI.last_instance
    assert client is not None
    assert client.init_kwargs["azure_endpoint"] == "https://example.openai.azure.com"
    assert client.init_kwargs["api_version"] == "2024-02-15-preview"
    assert client.init_kwargs["api_key"] == "key"
    assert client.init_kwargs["timeout"] == config.timeout
    assert client.init_kwargs["max_retries"] == 0


async def test_timeout_is_translated(config) -> None:
    provider = AzureOpenAIProvider(config)
    client = FakeAsyncAzureOpenAI.last_instance
    client.chat.completions.create.side_effect = FakeAPITimeoutError("timed out")

    with pytest.raises(LLMTimeoutError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_rate_limit_is_translated(config) -> None:
    provider = AzureOpenAIProvider(config)
    client = FakeAsyncAzureOpenAI.last_instance
    client.chat.completions.create.side_effect = FakeRateLimitError("too many requests")

    with pytest.raises(LLMRateLimitError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_generic_api_error_is_translated(config) -> None:
    provider = AzureOpenAIProvider(config)
    client = FakeAsyncAzureOpenAI.last_instance
    client.chat.completions.create.side_effect = FakeAPIError("server exploded")

    with pytest.raises(LLMRequestError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_invalid_json_content_raises_response_error(config) -> None:
    provider = AzureOpenAIProvider(config)
    client = FakeAsyncAzureOpenAI.last_instance
    client.chat.completions.create.return_value = _response_with_content("{not valid json")

    with pytest.raises(LLMResponseError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


def test_missing_sdk_dependency_raises_llm_dependency_error(config, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_import_error() -> None:
        raise ImportError("No module named 'openai'")

    monkeypatch.setattr(azure_provider_module, "_import_sdk", _raise_import_error)

    with pytest.raises(LLMDependencyError):
        AzureOpenAIProvider(config)
