from __future__ import annotations

import pytest

from app.calendar.errors import ConfigurationError, InvalidGregorianDateTimeError
from app.calendar.service import build_calendar_context


def test_reference_calendar_context() -> None:
    context = build_calendar_context(2026, 7, 17, 9)

    assert context.local_moment.isoformat() == "2026-07-17T09:00:00+08:00"
    assert context.month_pillar.ganzhi.text == "乙未"
    assert context.month_pillar.starting_jie.name == "小暑"
    assert context.month_pillar.next_jie.name == "立秋"
    assert context.day_pillar.ganzhi.text == "壬辰"
    assert (
        context.day_pillar.void_branches.first,
        context.day_pillar.void_branches.second,
    ) == ("午", "未")
    assert context.day_pillar.ganzhi.stem == "壬"
    assert context.six_spirits_by_line == (
        "玄武",
        "青龙",
        "朱雀",
        "勾陈",
        "螣蛇",
        "白虎",
    )


def test_zi_hour_advances_day_at_configured_boundary() -> None:
    before = build_calendar_context(2026, 7, 17, 22)
    after = build_calendar_context(2026, 7, 17, 23)
    disabled = build_calendar_context(2026, 7, 17, 23, zi_hour_boundary=24)
    disabled_midnight = build_calendar_context(2026, 7, 17, 0, zi_hour_boundary=24)

    assert before.day_pillar.ganzhi.text == "壬辰"
    assert before.day_pillar.effective_date == "2026-07-17"
    assert after.day_pillar.ganzhi.text == "癸巳"
    assert after.day_pillar.effective_date == "2026-07-18"
    assert after.near_boundary_note is not None
    assert "子初换日边界" in after.near_boundary_note
    assert disabled.day_pillar.ganzhi.text == "壬辰"
    assert disabled_midnight.near_boundary_note is None


def test_lichun_changes_year_and_month_pillars_at_exact_term() -> None:
    before = build_calendar_context(2024, 2, 4, 15)
    after = build_calendar_context(2024, 2, 4, 17)

    assert before.year_pillar.bazi_year == 2023
    assert before.year_pillar.ganzhi.text == "癸卯"
    assert before.month_pillar.ganzhi.text == "乙丑"
    assert after.year_pillar.bazi_year == 2024
    assert after.year_pillar.ganzhi.text == "甲辰"
    assert after.month_pillar.ganzhi.text == "丙寅"
    assert before.month_pillar.next_jie.moment < after.local_moment


def test_bazi_year_uses_current_year_lichun_not_nearest_across_years() -> None:
    context = build_calendar_context(2031, 8, 13, 12)

    assert context.year_pillar.bazi_year == 2031
    assert context.year_pillar.ganzhi.text == "辛亥"
    assert context.month_pillar.ganzhi.text == "丙申"


@pytest.mark.parametrize(
    ("args", "error"),
    [
        ((2025, 2, 29, 9), InvalidGregorianDateTimeError),
        ((2026, 1, 1, 24), InvalidGregorianDateTimeError),
    ],
)
def test_invalid_gregorian_inputs_are_rejected(
    args: tuple[int, int, int, int],
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        build_calendar_context(*args)


def test_invalid_timezone_and_boundary_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="未知时区"):
        build_calendar_context(2026, 1, 1, 0, timezone="No/Such_Zone")
    with pytest.raises(ConfigurationError, match="子初换日边界"):
        build_calendar_context(2026, 1, 1, 0, zi_hour_boundary=25)


def test_unsupported_ephemeris_edge_year_is_reported_as_calendar_error() -> None:
    with pytest.raises(InvalidGregorianDateTimeError, match="历法库无法计算"):
        build_calendar_context(1, 7, 1, 12)
