"""Tests for app.llm.openai_provider: request mapping and error translation.

The ``openai`` SDK itself is never called; :func:`_import_sdk` is
monkeypatched to return a fake module + fake ``AsyncOpenAI`` class so these
tests exercise only *our* mapping and error-translation code.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.llm.openai_provider as openai_provider_module
from app.llm.base import Message
from app.llm.config import OpenAIProviderConfig
from app.llm.errors import (
    LLMDependencyError,
    LLMRateLimitError,
    LLMRequestError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.llm.openai_provider import OpenAIProvider
from app.llm.schemas import DivinationConclusion


class FakeAPITimeoutError(Exception):
    pass


class FakeRateLimitError(Exception):
    pass


class FakeAPIError(Exception):
    pass


class FakeUnsupportedTemperatureError(FakeAPIError):
    def __init__(self) -> None:
        super().__init__("temperature is unsupported")
        self.body = {
            "param": "temperature",
            "code": "unsupported_value",
        }


def _fake_openai_module() -> SimpleNamespace:
    return SimpleNamespace(
        APITimeoutError=FakeAPITimeoutError,
        RateLimitError=FakeRateLimitError,
        APIError=FakeAPIError,
    )


class FakeAsyncOpenAI:
    """Records constructor kwargs and exposes a mockable create() call."""

    last_instance: "FakeAsyncOpenAI | None" = None

    def __init__(self, **kwargs: object) -> None:
        self.init_kwargs = kwargs
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        FakeAsyncOpenAI.last_instance = self


def _response_with_content(content: str) -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@pytest.fixture
def config() -> OpenAIProviderConfig:
    return OpenAIProviderConfig(api_key="sk-test", model="gpt-test", base_url=None, temperature=0.0)


@pytest.fixture(autouse=True)
def patched_sdk(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(openai_provider_module, "_import_sdk", lambda: (_fake_openai_module(), FakeAsyncOpenAI))


SAMPLE_MESSAGES = [
    Message(role="system", content="系统提示"),
    Message(role="user", content="用户问题"),
]


async def test_generate_structured_maps_request_correctly(config, sample_conclusion) -> None:
    provider = OpenAIProvider(config)
    client = FakeAsyncOpenAI.last_instance
    assert client is not None
    client.chat.completions.create.return_value = _response_with_content(sample_conclusion.model_dump_json())

    result = await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)

    assert result == sample_conclusion
    call_kwargs = client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-test"
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["messages"] == [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": "用户问题"},
    ]
    assert call_kwargs["response_format"]["type"] == "json_schema"
    assert call_kwargs["response_format"]["json_schema"]["name"] == "DivinationConclusion"
    assert call_kwargs["response_format"]["json_schema"]["schema"] == DivinationConclusion.model_json_schema()


def test_client_constructed_with_config_values(config) -> None:
    OpenAIProvider(config)
    client = FakeAsyncOpenAI.last_instance
    assert client is not None
    assert client.init_kwargs["api_key"] == "sk-test"
    assert client.init_kwargs["base_url"] is None
    assert client.init_kwargs["timeout"] == config.timeout
    assert client.init_kwargs["max_retries"] == 0


async def test_timeout_is_translated(config) -> None:
    provider = OpenAIProvider(config)
    client = FakeAsyncOpenAI.last_instance
    client.chat.completions.create.side_effect = FakeAPITimeoutError("timed out")

    with pytest.raises(LLMTimeoutError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_rate_limit_is_translated(config) -> None:
    provider = OpenAIProvider(config)
    client = FakeAsyncOpenAI.last_instance
    client.chat.completions.create.side_effect = FakeRateLimitError("too many requests")

    with pytest.raises(LLMRateLimitError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_generic_api_error_is_translated(config) -> None:
    provider = OpenAIProvider(config)
    client = FakeAsyncOpenAI.last_instance
    client.chat.completions.create.side_effect = FakeAPIError("server exploded")

    with pytest.raises(LLMRequestError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_unsupported_temperature_is_omitted_and_cached(
    config,
    sample_conclusion,
) -> None:
    provider = OpenAIProvider(config)
    client = FakeAsyncOpenAI.last_instance
    response = _response_with_content(sample_conclusion.model_dump_json())
    client.chat.completions.create.side_effect = [
        FakeUnsupportedTemperatureError(),
        response,
        response,
    ]

    first = await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)
    second = await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)

    assert first == sample_conclusion
    assert second == sample_conclusion
    calls = client.chat.completions.create.call_args_list
    assert calls[0].kwargs["temperature"] == 0.0
    assert "temperature" not in calls[1].kwargs
    assert "temperature" not in calls[2].kwargs


async def test_invalid_json_content_raises_response_error(config) -> None:
    provider = OpenAIProvider(config)
    client = FakeAsyncOpenAI.last_instance
    client.chat.completions.create.return_value = _response_with_content("this is not json{{{")

    with pytest.raises(LLMResponseError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_empty_content_raises_response_error(config) -> None:
    provider = OpenAIProvider(config)
    client = FakeAsyncOpenAI.last_instance
    client.chat.completions.create.return_value = _response_with_content("")

    with pytest.raises(LLMResponseError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_json_not_matching_schema_raises_response_error(config) -> None:
    provider = OpenAIProvider(config)
    client = FakeAsyncOpenAI.last_instance
    client.chat.completions.create.return_value = _response_with_content('{"unexpected": "shape"}')

    with pytest.raises(LLMResponseError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


def test_missing_sdk_dependency_raises_llm_dependency_error(config, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_import_error() -> None:
        raise ImportError("No module named 'openai'")

    monkeypatch.setattr(openai_provider_module, "_import_sdk", _raise_import_error)

    with pytest.raises(LLMDependencyError):
        OpenAIProvider(config)
