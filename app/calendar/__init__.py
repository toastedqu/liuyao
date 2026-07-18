"""Deterministic calendar module: Gregorian validation, solar terms, ganzhi.

Everything in this package is pure, offline computation (stdlib ``datetime``,
``zoneinfo`` and arithmetic only). Nothing here calls a network or an LLM, per
``implementation_plan.md`` §6 ("确定性历法模块").

Public entry point: :func:`app.calendar.service.build_calendar_context`.
"""

from __future__ import annotations

from app.calendar.errors import InvalidGregorianDateTimeError
from app.calendar.models import (
    CalendarContext,
    DayPillar,
    GanZhi,
    HourPillar,
    MonthPillar,
    SolarTermCrossing,
    VoidBranches,
    YearPillar,
)
from app.calendar.service import build_calendar_context

__all__ = [
    "InvalidGregorianDateTimeError",
    "CalendarContext",
    "DayPillar",
    "GanZhi",
    "HourPillar",
    "MonthPillar",
    "SolarTermCrossing",
    "VoidBranches",
    "YearPillar",
    "build_calendar_context",
]
