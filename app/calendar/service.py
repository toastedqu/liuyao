"""Top-level orchestrator for the deterministic calendar module.

:func:`build_calendar_context` is the single entry point other packages
(``app.chart``, and eventually ``app.rules``/``app.api``) should call. It
validates the Gregorian input, interprets it in ``Asia/Shanghai`` (or another
IANA zone, though the first version only ever passes the default), and
returns an immutable, fully audited :class:`~app.calendar.models.CalendarContext`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.calendar.constants import (
    MONTH_BRANCH_FOR_JIE_INDEX,  # noqa: F401  (re-exported for callers/tests)
)
from app.calendar.errors import ConfigurationError, InvalidGregorianDateTimeError
from app.calendar.ganzhi import (
    compute_void_branches,
    day_ganzhi_index,
    ganzhi_from_index,
    hour_ganzhi,
    month_ganzhi,
    six_spirits_by_line,
    year_ganzhi_index,
)
from app.calendar.models import (
    CalendarContext,
    DayPillar,
    HourPillar,
    MonthPillar,
    SolarTermCrossing,
    YearPillar,
)
from app.calendar.solar_terms import find_bracketing_jie_crossings, find_nearest_lichun_crossing

_DEFAULT_TIMEZONE = "Asia/Shanghai"
_DEFAULT_ZI_HOUR_BOUNDARY = 23
_BOUNDARY_NOTE_WINDOW = timedelta(hours=1)


def _validate_and_build_moment(
    year: int, month: int, day: int, hour: int, minute: int, second: int, timezone: str
) -> datetime:
    try:
        tzinfo = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ConfigurationError(f"未知时区：{timezone!r}") from error

    if not (0 <= hour <= 23):
        raise InvalidGregorianDateTimeError(f"小时必须介于 0-23 之间，收到 {hour}")
    if not (0 <= minute <= 59):
        raise InvalidGregorianDateTimeError(f"分钟必须介于 0-59 之间，收到 {minute}")
    if not (0 <= second <= 59):
        raise InvalidGregorianDateTimeError(f"秒必须介于 0-59 之间，收到 {second}")

    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=tzinfo)
    except ValueError as error:
        raise InvalidGregorianDateTimeError(f"公历日期或时间无效：{error}") from error


def _crossing_to_model(crossing) -> SolarTermCrossing:
    return SolarTermCrossing(name=crossing.name, longitude=crossing.longitude, moment=crossing.moment)


def _bazi_year(local_moment: datetime) -> tuple[int, SolarTermCrossing]:
    """Determine the BaZi (立春-anchored) year and return that year's 立春 instant."""

    lichun = find_nearest_lichun_crossing(local_moment)
    bazi_year = local_moment.year if local_moment >= lichun.moment else local_moment.year - 1
    return bazi_year, _crossing_to_model(lichun)


def build_calendar_context(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
    second: int = 0,
    *,
    timezone: str = _DEFAULT_TIMEZONE,
    zi_hour_boundary: int = _DEFAULT_ZI_HOUR_BOUNDARY,
) -> CalendarContext:
    """Validate a Gregorian moment and compute its full ganzhi calendar context.

    ``zi_hour_boundary`` is the local hour (0-23, or 24 to disable) at which
    the day pillar advances to the next Gregorian day (子初换日边界，默认
    23:00，可通过 ``ZI_HOUR_DAY_BOUNDARY`` 环境变量配置——见
    ``implementation_plan.md`` §6/§15).
    """

    if not (0 <= zi_hour_boundary <= 24):
        raise ConfigurationError(f"子初换日边界必须介于 0-24 之间，收到 {zi_hour_boundary}")

    local_moment = _validate_and_build_moment(year, month, day, hour, minute, second, timezone)

    # --- day pillar (with configurable 23:00 zi-hour day boundary) ---------
    effective_date = local_moment.date()
    if hour >= zi_hour_boundary:
        effective_date = effective_date + timedelta(days=1)
    day_index = day_ganzhi_index(effective_date)
    day_gz = ganzhi_from_index(day_index)
    void_branches = compute_void_branches(day_gz.stem, day_gz.branch)
    day_pillar = DayPillar(
        ganzhi=day_gz, effective_date=effective_date.isoformat(), void_branches=void_branches
    )

    # --- year pillar (立春-anchored) ----------------------------------------
    try:
        bazi_year, _lichun_crossing = _bazi_year(local_moment)
        prev_crossing_raw, next_crossing_raw = find_bracketing_jie_crossings(
            local_moment
        )
    except (RuntimeError, ValueError) as error:
        raise InvalidGregorianDateTimeError(
            f"固定历法库无法计算该公历年份的节气：{error}"
        ) from error
    year_pillar = YearPillar(ganzhi=ganzhi_from_index(year_ganzhi_index(bazi_year)), bazi_year=bazi_year)

    # --- month pillar (precise solar-term / 节气 boundary) ------------------
    sector = prev_crossing_raw.sector_index
    prev_crossing = _crossing_to_model(prev_crossing_raw)
    next_crossing = _crossing_to_model(next_crossing_raw)
    month_pillar = MonthPillar(
        ganzhi=month_ganzhi(bazi_year, sector),
        jie_sector_index=sector,
        starting_jie=prev_crossing,
        next_jie=next_crossing,
    )

    # --- hour pillar (五鼠遁, keyed off the day pillar's stem) ---------------
    hour_pillar = HourPillar(ganzhi=hour_ganzhi(day_gz.stem, hour))

    # --- 六神 (day-stem keyed, line 1..6) ------------------------------------
    six_spirits = six_spirits_by_line(day_gz.stem)

    note = None
    boundary_bits = []
    if abs((local_moment - prev_crossing.moment)) < _BOUNDARY_NOTE_WINDOW:
        boundary_bits.append(f"距{prev_crossing.name}交节仅 {abs(local_moment - prev_crossing.moment)}")
    if abs((next_crossing.moment - local_moment)) < _BOUNDARY_NOTE_WINDOW:
        boundary_bits.append(f"距{next_crossing.name}交节仅 {abs(next_crossing.moment - local_moment)}")
    if zi_hour_boundary < 24 and hour == zi_hour_boundary:
        boundary_bits.append("输入时辰恰处于子初换日边界小时，日柱已按配置换日")
    if boundary_bits:
        note = "；".join(boundary_bits)

    return CalendarContext(
        input_year=year,
        input_month=month,
        input_day=day,
        input_hour=hour,
        timezone=timezone,
        zi_hour_boundary=zi_hour_boundary,
        local_moment=local_moment,
        year_pillar=year_pillar,
        month_pillar=month_pillar,
        day_pillar=day_pillar,
        hour_pillar=hour_pillar,
        six_spirits_by_line=six_spirits,
        near_boundary_note=note,
    )
