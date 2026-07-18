"""Tests for app.llm.base: Message validation and the shared JSON/dict
parsing helpers used by the provider adapters.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.base import Message, parse_structured_json, validate_structured_payload
from app.llm.errors import LLMResponseError


class _Toy:
    pass


def test_message_rejects_invalid_role() -> None:
    with pytest.raises(ValidationError):
        Message(role="tool", content="x")  # type: ignore[arg-type]


def test_message_rejects_empty_content() -> None:
    with pytest.raises(ValidationError):
        Message(role="user", content="")


def test_message_is_frozen() -> None:
    message = Message(role="user", content="hello")
    with pytest.raises(ValidationError):
        message.content = "changed"  # type: ignore[misc]


def test_parse_structured_json_none_content_raises() -> None:
    from app.llm.schemas import RisksAndUncertainties

    with pytest.raises(LLMResponseError):
        parse_structured_json(None, RisksAndUncertainties)


def test_parse_structured_json_blank_content_raises() -> None:
    from app.llm.schemas import RisksAndUncertainties

    with pytest.raises(LLMResponseError):
        parse_structured_json("   ", RisksAndUncertainties)


def test_parse_structured_json_invalid_json_raises() -> None:
    from app.llm.schemas import RisksAndUncertainties

    with pytest.raises(LLMResponseError):
        parse_structured_json("{not valid", RisksAndUncertainties)


def test_parse_structured_json_schema_mismatch_raises() -> None:
    from app.llm.schemas import RisksAndUncertainties

    with pytest.raises(LLMResponseError):
        parse_structured_json('{"items": "should be a list"}', RisksAndUncertainties)


def test_parse_structured_json_valid_payload_returns_instance() -> None:
    from app.llm.schemas import RisksAndUncertainties

    result = parse_structured_json('{"items": []}', RisksAndUncertainties)
    assert isinstance(result, RisksAndUncertainties)
    assert result.items == []


def test_validate_structured_payload_dict_mismatch_raises() -> None:
    from app.llm.schemas import RisksAndUncertainties

    with pytest.raises(LLMResponseError):
        validate_structured_payload({"items": "not-a-list"}, RisksAndUncertainties)


def test_validate_structured_payload_valid_dict_returns_instance() -> None:
    from app.llm.schemas import RisksAndUncertainties

    result = validate_structured_payload({"items": []}, RisksAndUncertainties)
    assert isinstance(result, RisksAndUncertainties)
