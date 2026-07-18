"""Precise solar-term (节气) crossing lookups, backed by ``lunar_python``.

``implementation_plan.md`` §6 requires month-building (月建) to switch
exactly at the instant the sun's ecliptic longitude crosses one of the
twelve "节" (jie) boundaries -- not at Gregorian-date granularity. A
from-scratch low-precision solar-longitude formula (Jean Meeus's "low
accuracy" series, accurate to ~0.01 degree) was evaluated first, but it
disagreed with the published exact instant for the 2026-02-04 立春
(04:01:51 Beijing time, per public almanac sources) by several minutes,
which is unsafe this close to a boundary. ``lunar_python`` is already a
pinned project dependency (see ``pyproject.toml``) and computes these
instants to sub-minute accuracy from a fuller ephemeris, so this module
wraps its public ``getJieQiTable()`` API instead of re-deriving solar
longitude from scratch -- this follows the task brief's guidance to prefer a
mature calendar library where one is already available.

Only the twelve "节" (jie) terms mark 月建 boundaries; the twelve "气" (qi,
mid-month) terms do not. ``lunar_python``'s table alternates jie/qi starting
with a jie term, so even list positions (0, 2, 4, ...) are always jie terms
in chronological order. This module relies on that structural invariant
rather than on name matching, because the library aliases repeated Chinese
term names with ALL-CAPS pinyin keys across year boundaries (an internal
detail of ``lunar_python`` we should not depend on).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from lunar_python import Solar

from app.calendar.constants import JIE_NAMES_FROM_LICHUN, LICHUN_LONGITUDE

_SHANGHAI = ZoneInfo("Asia/Shanghai")

# Nominal (approximate) Gregorian month/day for each of the twelve 节, used
# only to disambiguate *which* named jie a lunar_python-reported instant is
# (each jie recurs once a year, roughly a fixed calendar date +/- a day or
# two, so nearest-nominal-date matching is unambiguous).
_NOMINAL_MONTH_DAY: tuple[tuple[int, int], ...] = (
    (2, 4), (3, 6), (4, 5), (5, 6), (6, 6), (7, 7),
    (8, 8), (9, 8), (10, 8), (11, 7), (12, 7), (1, 6),
)


@dataclass(frozen=True)
class JieCrossing:
    """One exact 节 (jie) solar-term crossing instant, with its sector index."""

    name: str
    sector_index: int  # 0 = 立春 (寅月), 1 = 惊蛰 (卯月), ... 11 = 小寒 (丑月)
    longitude: float
    moment: datetime  # timezone-aware, Asia/Shanghai


def _jieqi_table(local_moment: datetime) -> list[datetime]:
    """Return every jie-and-qi instant lunar_python knows about, in order.

    ``lunar_python``'s ``getJieQiTable()`` always returns roughly 30 entries
    spanning from the previous December's 大雪 through the following March's
    惊蛰, regardless of which date within that window is queried, so a single
    call is enough to bracket any moment in the query year.
    """

    solar = Solar.fromYmdHms(
        local_moment.year,
        local_moment.month,
        local_moment.day,
        local_moment.hour,
        local_moment.minute,
        local_moment.second,
    )
    table = solar.getLunar().getJieQiTable()
    moments = []
    for jie_solar in table.values():
        naive = datetime(
            jie_solar.getYear(),
            jie_solar.getMonth(),
            jie_solar.getDay(),
            jie_solar.getHour(),
            jie_solar.getMinute(),
            jie_solar.getSecond(),
        )
        moments.append(naive.replace(tzinfo=_SHANGHAI))
    moments.sort()
    return moments


def _jie_only(all_moments: list[datetime]) -> list[datetime]:
    """Keep only the "节" entries: every other entry, starting at index 0."""

    return all_moments[0::2]


def _sector_index_for_moment(moment: datetime) -> int:
    """Determine the jie sector index (0=立春..11=小寒) for a known jie instant."""

    best_index = 0
    best_distance = None
    for index, (nominal_month, nominal_day) in enumerate(_NOMINAL_MONTH_DAY):
        for year_delta in (-1, 0, 1):
            candidate_year = moment.year + year_delta
            try:
                nominal = datetime(candidate_year, nominal_month, nominal_day, tzinfo=_SHANGHAI)
            except ValueError:
                continue
            distance = abs((moment - nominal).total_seconds())
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_index = index
    return best_index


def find_bracketing_jie_crossings(local_moment: datetime) -> tuple[JieCrossing, JieCrossing]:
    """Return the (previous, next) exact 节 crossings bracketing ``local_moment``.

    ``local_moment`` must be a timezone-aware Asia/Shanghai ``datetime``.
    """

    if local_moment.tzinfo is None:
        raise ValueError("find_bracketing_jie_crossings requires a timezone-aware datetime")

    jie_moments = _jie_only(_jieqi_table(local_moment))

    prev_moment = max((m for m in jie_moments if m <= local_moment), default=None)
    next_moment = min((m for m in jie_moments if m > local_moment), default=None)

    if prev_moment is None or next_moment is None:
        # `local_moment` sits outside the ~14-month window lunar_python
        # returned for this query (can happen very close to the table's own
        # edges); widen the search by querying again from a shifted moment.
        shift = timedelta(days=45) if prev_moment is None else timedelta(days=-45)
        wider = _jie_only(_jieqi_table(local_moment + shift))
        candidates = sorted(set(jie_moments) | set(wider))
        prev_moment = prev_moment or max(
            (m for m in candidates if m <= local_moment), default=None
        )
        next_moment = next_moment or min(
            (m for m in candidates if m > local_moment), default=None
        )
        if prev_moment is None or next_moment is None:
            raise RuntimeError(f"could not bracket {local_moment} with solar-term crossings")

    prev_index = _sector_index_for_moment(prev_moment)
    next_index = (prev_index + 1) % 12
    prev = JieCrossing(
        name=JIE_NAMES_FROM_LICHUN[prev_index],
        sector_index=prev_index,
        longitude=(LICHUN_LONGITUDE + 30 * prev_index) % 360.0,
        moment=prev_moment,
    )
    next_ = JieCrossing(
        name=JIE_NAMES_FROM_LICHUN[next_index],
        sector_index=next_index,
        longitude=(LICHUN_LONGITUDE + 30 * next_index) % 360.0,
        moment=next_moment,
    )
    return prev, next_


def find_nearest_lichun_crossing(local_moment: datetime) -> JieCrossing:
    """Return the 立春 crossing in ``local_moment``'s Gregorian year."""

    guess_this_year = local_moment.replace(
        month=2, day=4, hour=4, minute=0, second=0, microsecond=0
    )
    jie_moments = _jie_only(_jieqi_table(guess_this_year))
    lichun_moments = [m for m in jie_moments if _sector_index_for_moment(m) == 0]
    if not lichun_moments:
        raise RuntimeError("could not locate a 立春 crossing in the jieqi table")
    same_year = [moment for moment in lichun_moments if moment.year == local_moment.year]
    if not same_year:
        raise RuntimeError(
            f"could not locate the {local_moment.year} 立春 crossing in the jieqi table"
        )
    crossing = min(
        same_year,
        key=lambda moment: abs((moment - guess_this_year).total_seconds()),
    )
    return JieCrossing(
        name="立春",
        sector_index=0,
        longitude=LICHUN_LONGITUDE,
        moment=crossing,
    )
