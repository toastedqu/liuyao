"""Per-provider configuration loading for the LLM layer.

Reads the same environment variable names documented in ``.env.example`` and
``app.config.Settings`` (``OPENAI_API_KEY``/``OPENAI_MODEL``/..., ``LLM_PROVIDER``,
``LLM_TEMPERATURE``), but is intentionally self-contained: it does not import
``app.config`` so this package stays independently usable and testable, and
callers may pass any ``Mapping[str, str]`` (e.g. ``os.environ``, a ``dict``
built from ``Settings.model_dump()``, or a test fixture) instead of only the
real process environment.

Every loader fails fast with :class:`app.llm.errors.LLMConfigurationError`
when a required variable for the *requested* provider is missing -- it never
silently falls back to another provider.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from app.llm.errors import LLMConfigurationError

SUPPORTED_PROVIDERS: tuple[str, ...] = ("openai", "azure_openai", "anthropic")


class OpenAIProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_key: str = Field(min_length=1)
    model: str = Field(min_length=1)
    base_url: str | None = None
    timeout: float = Field(default=120.0, gt=0)
    temperature: float = Field(default=0.0, ge=0, le=0)


class AzureOpenAIProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_key: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    deployment: str = Field(min_length=1)
    api_version: str = Field(min_length=1)
    timeout: float = Field(default=120.0, gt=0)
    temperature: float = Field(default=0.0, ge=0, le=0)


class AnthropicProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_key: str = Field(min_length=1)
    model: str = Field(min_length=1)
    timeout: float = Field(default=120.0, gt=0)
    temperature: float = Field(default=0.0, ge=0, le=0)
    max_tokens: int = Field(default=4096, gt=0)


def _env_value(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _require(env: Mapping[str, str], name: str, provider_label: str) -> str:
    value = _env_value(env, name)
    if not value:
        raise LLMConfigurationError(
            f"缺少 {provider_label} Provider 所需的环境变量 {name}，"
            "请在 .env 中配置后重试；系统不会静默切换到其他 Provider。"
        )
    return value


def _parse_temperature(env: Mapping[str, str], provider_label: str) -> float:
    raw = _env_value(env, "LLM_TEMPERATURE")
    if raw is None:
        return 0.0
    try:
        value = float(raw)
    except ValueError as exc:
        raise LLMConfigurationError(
            f"环境变量 LLM_TEMPERATURE 的值 {raw!r} 不是合法数字。"
        ) from exc
    if value != 0:
        raise LLMConfigurationError(
            f"{provider_label} Provider 要求 temperature=0 以保证可复现性，"
            f"但 LLM_TEMPERATURE={value!r}。"
        )
    return value


def _parse_timeout(env: Mapping[str, str]) -> float:
    raw = _env_value(env, "LLM_TIMEOUT_SECONDS")
    if raw is None:
        return 120.0
    try:
        value = float(raw)
    except ValueError as exc:
        raise LLMConfigurationError(
            f"环境变量 LLM_TIMEOUT_SECONDS 的值 {raw!r} 不是合法数字。"
        ) from exc
    if not 1 <= value <= 600:
        raise LLMConfigurationError(
            "环境变量 LLM_TIMEOUT_SECONDS 必须介于 1 至 600 秒。"
        )
    return value


def load_openai_config(env: Mapping[str, str] | None = None) -> OpenAIProviderConfig:
    env = env if env is not None else os.environ
    return OpenAIProviderConfig(
        api_key=_require(env, "OPENAI_API_KEY", "OpenAI"),
        model=_require(env, "OPENAI_MODEL", "OpenAI"),
        base_url=_env_value(env, "OPENAI_BASE_URL"),
        temperature=_parse_temperature(env, "OpenAI"),
        timeout=_parse_timeout(env),
    )


def load_azure_openai_config(env: Mapping[str, str] | None = None) -> AzureOpenAIProviderConfig:
    env = env if env is not None else os.environ
    return AzureOpenAIProviderConfig(
        api_key=_require(env, "AZURE_OPENAI_API_KEY", "Azure OpenAI"),
        endpoint=_require(env, "AZURE_OPENAI_ENDPOINT", "Azure OpenAI"),
        deployment=_require(env, "AZURE_OPENAI_DEPLOYMENT", "Azure OpenAI"),
        api_version=_require(env, "AZURE_OPENAI_API_VERSION", "Azure OpenAI"),
        temperature=_parse_temperature(env, "Azure OpenAI"),
        timeout=_parse_timeout(env),
    )


def load_anthropic_config(env: Mapping[str, str] | None = None) -> AnthropicProviderConfig:
    env = env if env is not None else os.environ
    return AnthropicProviderConfig(
        api_key=_require(env, "ANTHROPIC_API_KEY", "Anthropic"),
        model=_require(env, "ANTHROPIC_MODEL", "Anthropic"),
        temperature=_parse_temperature(env, "Anthropic"),
        timeout=_parse_timeout(env),
    )
