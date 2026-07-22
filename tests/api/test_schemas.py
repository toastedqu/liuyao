from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.schemas import DivinationRequest


def valid_payload() -> dict:
    return {
        "question": " 本次求财是否可成？ ",
        "useful_god": "妻财",
        "calendar": {
            "year": 2026,
            "month": 7,
            "day": 17,
            "hour": 9,
            "timezone": "Asia/Shanghai",
        },
        "lines": [7, 8, 6, 9, 7, 8],
    }


def test_request_normalizes_question_and_preserves_bottom_to_top_lines() -> None:
    request = DivinationRequest.model_validate(valid_payload())

    assert request.question == "本次求财是否可成？"
    assert request.useful_god == "妻财"
    assert request.lines == [7, 8, 6, 9, 7, 8]
    assert request.calendar.as_datetime().utcoffset().total_seconds() == 8 * 3600


@pytest.mark.parametrize("lines", ([7] * 5, [7] * 7, [7, 8, 6, 9, 5, 8]))
def test_request_rejects_invalid_lines(lines: list[int]) -> None:
    payload = valid_payload()
    payload["lines"] = lines

    with pytest.raises(ValidationError):
        DivinationRequest.model_validate(payload)


def test_request_rejects_impossible_calendar_date() -> None:
    payload = valid_payload()
    payload["calendar"]["day"] = 32

    with pytest.raises(ValidationError, match="less than or equal to 31"):
        DivinationRequest.model_validate(payload)

    payload["calendar"]["day"] = 31
    payload["calendar"]["month"] = 4
    with pytest.raises(ValidationError, match="公历日期或时间无效"):
        DivinationRequest.model_validate(payload)


def test_removed_category_and_subject_fields_are_rejected() -> None:
    payload = valid_payload()
    payload["category"] = "求财"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DivinationRequest.model_validate(payload)

    payload = valid_payload()
    payload["subject"] = {"mode": "self", "relation": None}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DivinationRequest.model_validate(payload)


def test_request_requires_a_valid_user_selected_useful_god() -> None:
    payload = valid_payload()
    del payload["useful_god"]
    with pytest.raises(ValidationError, match="Field required"):
        DivinationRequest.model_validate(payload)

    payload = valid_payload()
    payload["useful_god"] = "恋爱"
    with pytest.raises(ValidationError):
        DivinationRequest.model_validate(payload)


def test_request_forbids_unknown_fields_and_timezones() -> None:
    payload = valid_payload()
    payload["computed_hexagram"] = "乾为天"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DivinationRequest.model_validate(payload)

    payload = valid_payload()
    payload["calendar"]["timezone"] = "UTC"
    with pytest.raises(ValidationError):
        DivinationRequest.model_validate(payload)
