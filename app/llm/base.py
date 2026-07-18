"""Provider-agnostic core types for the LLM layer.

``LLMProvider`` is the single seam between ``app.divination.service`` (not
part of this task) and the concrete OpenAI/Azure OpenAI/Anthropic SDKs. Every
provider implementation returns an *instance of the requested Pydantic
schema*, never a raw string or dict, so downstream code can rely on
structural validation having already happened.
"""

from __future__ import annotations

import json
from typing import Literal, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm.errors import LLMResponseError

Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    """A single chat message exchanged with an LLM provider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Role
    content: str = Field(min_length=1)


ResponseT = TypeVar("ResponseT", bound=BaseModel)


@runtime_checkable
class LLMProvider(Protocol):
    """Unified async interface implemented by every provider adapter.

    Implementations must:

    * use ``temperature=0`` (or the closest deterministic setting the
      provider exposes);
    * never fall back to a different provider when configuration is
      missing -- that must fail at construction time instead;
    * raise the exceptions defined in :mod:`app.llm.errors` instead of
      leaking SDK-specific exceptions.
    """

    async def generate_structured(
        self,
        messages: list[Message],
        response_schema: type[ResponseT],
    ) -> ResponseT:
        """Call the provider and return a validated ``response_schema`` instance."""
        ...


def parse_structured_json(content: str | None, response_schema: type[ResponseT]) -> ResponseT:
    """Parse and validate a raw JSON string returned by a text-based provider.

    Shared by OpenAI-compatible providers (OpenAI, Azure OpenAI), which return
    the structured payload as a JSON *string* inside a chat completion
    message. Anthropic's tool-use path returns an already-parsed ``dict`` and
    therefore validates directly against ``response_schema`` without going
    through this helper.
    """
    if content is None or content.strip() == "":
        raise LLMResponseError("模型未返回任何内容，无法解析结构化结果。")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"模型返回内容不是合法 JSON：{exc}") from exc
    return validate_structured_payload(data, response_schema)


def validate_structured_payload(data: object, response_schema: type[ResponseT]) -> ResponseT:
    """Validate an already-parsed payload (dict) against ``response_schema``."""
    try:
        return response_schema.model_validate(data)
    except ValidationError as exc:
        raise LLMResponseError(f"模型返回内容不符合结构化 Schema：{exc}") from exc
