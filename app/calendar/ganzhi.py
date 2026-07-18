"""干支 (ganzhi) computations: day/month/year/hour pillars, 旬空, 六神.

All formulas here are the standard ones used throughout Chinese ganzhi
calendars and cross-checked against known reference dates (see
``tests/calendar/test_ganzhi.py``). Day-pillar arithmetic uses the Julian Day
Number so it needs no external table; month/year pillars are anchored to the
precise solar-term crossings from :mod:`app.calendar.solar_terms` per
``implementation_plan.md`` §6 ("依据节气交界计算月建，不按农历初一切月").
"""

from __future__ import annotations

from datetime import date

from app.calendar.constants import (
    BRANCH_INDEX,
    BRANCHES,
    STEM_INDEX,
    STEMS,
    yin_month_stem_index,
    zi_hour_stem_index,
)
from app.calendar.models import GanZhi, VoidBranches

# `julian_day_number(1900, 1, 31) % 60 == 51`, and 1900-01-31 is the
# well-documented 甲辰 day (stem index 0, branch index 4 -> 60-cycle index
# 40). The additive constant 49 is calibrated so that `(jdn + 49) % 60`
# reproduces 40 for that date (and therefore the correct day ganzhi for any
# Gregorian date). See tests/calendar/test_ganzhi.py for cross-checks against
# several independently documented reference dates.
_DAY_PILLAR_JDN_OFFSET = 49


def julian_day_number(year: int, month: int, day: int) -> int:
    """Julian Day Number (integer, noon convention) for a Gregorian date."""

    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return (
        day
        + (153 * m + 2) // 5
        + 365 * y
        + y // 4
        - y // 100
        + y // 400
        - 32045
    )


def day_ganzhi_index(gregorian_date: date) -> int:
    """Return the 0-59 index into the 60-jiazi cycle for a Gregorian date."""

    jdn = julian_day_number(gregorian_date.year, gregorian_date.month, gregorian_date.day)
    return (jdn + _DAY_PILLAR_JDN_OFFSET) % 60


def ganzhi_from_index(index_0_59: int) -> GanZhi:
    index_0_59 %= 60
    return GanZhi(stem=STEMS[index_0_59 % 10], branch=BRANCHES[index_0_59 % 12])


def year_ganzhi_index(bazi_year: int) -> int:
    """0-59 jiazi-cycle index for a BaZi year (already adjusted for 立春)."""

    return (bazi_year - 4) % 60


def compute_void_branches(day_stem: str, day_branch: str) -> VoidBranches:
    """旬空 (void/empty branches) for the decade (旬) containing this day.

    See 029_旬空章.md: "甲子旬中，戌亥空。甲戌旬中，申酉空。..." The decade's
    "missing" branches are the two branches that follow immediately after the
    tenth stem-branch pairing of the decade.
    """

    stem_index = STEM_INDEX[day_stem]
    branch_index = BRANCH_INDEX[day_branch]
    xun_start_branch = (branch_index - stem_index) % 12
    first = BRANCHES[(xun_start_branch + 10) % 12]
    second = BRANCHES[(xun_start_branch + 11) % 12]
    return VoidBranches(first=first, second=second)


# 六神 (six spirits) fixed cycle order starting from whichever spirit the
# day stem assigns to 初爻 (line 1); see 019_六神章.md.
SIX_SPIRITS_CYCLE: tuple[str, ...] = ("青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武")
_DAY_STEM_TO_STARTING_SPIRIT_INDEX: dict[str, int] = {
    "甲": 0, "乙": 0,
    "丙": 1, "丁": 1,
    "戊": 2,
    "己": 3,
    "庚": 4, "辛": 4,
    "壬": 5, "癸": 5,
}


def six_spirits_by_line(day_stem: str) -> tuple[str, ...]:
    """Return the six-spirit name for lines 1..6 (初爻 to 上爻), in order."""

    if day_stem not in _DAY_STEM_TO_STARTING_SPIRIT_INDEX:
        raise ValueError(f"unknown heavenly stem: {day_stem!r}")
    start = _DAY_STEM_TO_STARTING_SPIRIT_INDEX[day_stem]
    return tuple(SIX_SPIRITS_CYCLE[(start + line - 1) % 6] for line in range(1, 7))


def hour_ganzhi(day_stem: str, hour: int) -> GanZhi:
    """五鼠遁: the ganzhi of the two-hour block (时辰) containing ``hour``.

    ``hour`` is 0-23 in the already zi-hour-boundary-adjusted local time
    frame; the two-hour block index is ``((hour + 1) // 2) % 12`` so that
    23:00-00:59 and 00:00 (pre-boundary callers already folded into 23:00)
    map to 子 (index 0), 01:00-02:59 map to 丑, etc.
    """

    block_index = ((hour + 1) // 2) % 12
    day_stem_index = STEM_INDEX[day_stem]
    zi_stem = zi_hour_stem_index(day_stem_index)
    stem_index = (zi_stem + block_index) % 10
    return GanZhi(stem=STEMS[stem_index], branch=BRANCHES[block_index])


def year_stem_for_month_building(bazi_year: int) -> int:
    """Heavenly-stem index (0-9) of a BaZi year, used for 五虎遁."""

    return (bazi_year - 4) % 10


def month_ganzhi(bazi_year: int, jie_sector_index: int) -> GanZhi:
    """月建 ganzhi for the ``jie_sector_index``-th (0-11, 0 = 立春/寅) month.

    Month branch cycles fixed by solar-term sector; month stem follows the
    五虎遁 mnemonic keyed off the BaZi year stem (see 004_混天甲子章.md /
    universal 五虎遁 convention).
    """

    year_stem_index = year_stem_for_month_building(bazi_year)
    yin_stem = yin_month_stem_index(year_stem_index)
    stem_index = (yin_stem + jie_sector_index) % 10
    branch_index = (2 + jie_sector_index) % 12
    return GanZhi(stem=STEMS[stem_index], branch=BRANCHES[branch_index])
