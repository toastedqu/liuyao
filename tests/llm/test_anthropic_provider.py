"""Tests for app.llm.anthropic_provider: forced tool-use request mapping and
error translation.

Anthropic has no ``response_format`` JSON mode; structured output is
obtained by forcing a single tool call. These tests build a fake
``AsyncAnthropic`` client (via monkeypatching ``_import_sdk``) whose
``messages.create`` returns objects shaped like real ``ToolUseBlock``
content, so we exercise only our own mapping/error-translation logic.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.llm.anthropic_provider as anthropic_provider_module
from app.llm.anthropic_provider import _TOOL_NAME, AnthropicProvider
from app.llm.base import Message
from app.llm.config import AnthropicProviderConfig
from app.llm.errors import (
    LLMDependencyError,
    LLMRateLimitError,
    LLMRequestError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.llm.schemas import DivinationConclusion


class FakeAPITimeoutError(Exception):
    pass


class FakeRateLimitError(Exception):
    pass


class FakeAPIError(Exception):
    pass


def _fake_anthropic_module() -> SimpleNamespace:
    return SimpleNamespace(
        APITimeoutError=FakeAPITimeoutError,
        RateLimitError=FakeRateLimitError,
        APIError=FakeAPIError,
    )


class FakeAsyncAnthropic:
    last_instance: "FakeAsyncAnthropic | None" = None

    def __init__(self, **kwargs: object) -> None:
        self.init_kwargs = kwargs
        self.messages = SimpleNamespace(create=AsyncMock())
        FakeAsyncAnthropic.last_instance = self


def _tool_use_response(tool_input: dict, *, name: str = _TOOL_NAME) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", name=name, input=tool_input)
    return SimpleNamespace(content=[block])


def _text_only_response(text: str = "抱歉，我不能使用工具。") -> SimpleNamespace:
    block = SimpleNamespace(type="text", name=None, input=None, text=text)
    return SimpleNamespace(content=[block])


@pytest.fixture
def config() -> AnthropicProviderConfig:
    return AnthropicProviderConfig(api_key="key", model="claude-test", temperature=0.0)


@pytest.fixture(autouse=True)
def patched_sdk(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        anthropic_provider_module, "_import_sdk", lambda: (_fake_anthropic_module(), FakeAsyncAnthropic)
    )


SAMPLE_MESSAGES = [
    Message(role="system", content="系统提示"),
    Message(role="user", content="用户问题"),
]


async def test_generate_structured_maps_request_correctly(config, sample_conclusion) -> None:
    provider = AnthropicProvider(config)
    client = FakeAsyncAnthropic.last_instance
    assert client is not None
    client.messages.create.return_value = _tool_use_response(sample_conclusion.model_dump(mode="json"))

    result = await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)

    assert result == sample_conclusion
    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-test"
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["system"] == "系统提示"
    assert call_kwargs["messages"] == [{"role": "user", "content": "用户问题"}]
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": _TOOL_NAME}
    assert call_kwargs["tools"][0]["name"] == _TOOL_NAME
    assert call_kwargs["tools"][0]["input_schema"] == DivinationConclusion.model_json_schema()


def test_client_constructed_with_config_values(config) -> None:
    AnthropicProvider(config)
    client = FakeAsyncAnthropic.last_instance
    assert client is not None
    assert client.init_kwargs["api_key"] == "key"
    assert client.init_kwargs["timeout"] == config.timeout
    assert client.init_kwargs["max_retries"] == 0


async def test_timeout_is_translated(config) -> None:
    provider = AnthropicProvider(config)
    client = FakeAsyncAnthropic.last_instance
    client.messages.create.side_effect = FakeAPITimeoutError("timed out")

    with pytest.raises(LLMTimeoutError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_rate_limit_is_translated(config) -> None:
    provider = AnthropicProvider(config)
    client = FakeAsyncAnthropic.last_instance
    client.messages.create.side_effect = FakeRateLimitError("too many requests")

    with pytest.raises(LLMRateLimitError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_generic_api_error_is_translated(config) -> None:
    provider = AnthropicProvider(config)
    client = FakeAsyncAnthropic.last_instance
    client.messages.create.side_effect = FakeAPIError("server exploded")

    with pytest.raises(LLMRequestError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_missing_tool_use_block_raises_response_error(config) -> None:
    provider = AnthropicProvider(config)
    client = FakeAsyncAnthropic.last_instance
    client.messages.create.return_value = _text_only_response()

    with pytest.raises(LLMResponseError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_tool_input_not_matching_schema_raises_response_error(config) -> None:
    provider = AnthropicProvider(config)
    client = FakeAsyncAnthropic.last_instance
    client.messages.create.return_value = _tool_use_response({"unexpected": "shape"})

    with pytest.raises(LLMResponseError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


async def test_wrong_tool_name_is_treated_as_missing(config) -> None:
    provider = AnthropicProvider(config)
    client = FakeAsyncAnthropic.last_instance
    client.messages.create.return_value = _tool_use_response({"anything": True}, name="some_other_tool")

    with pytest.raises(LLMResponseError):
        await provider.generate_structured(SAMPLE_MESSAGES, DivinationConclusion)


def test_missing_sdk_dependency_raises_llm_dependency_error(config, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_import_error() -> None:
        raise ImportError("No module named 'anthropic'")

    monkeypatch.setattr(anthropic_provider_module, "_import_sdk", _raise_import_error)

    with pytest.raises(LLMDependencyError):
        AnthropicProvider(config)
