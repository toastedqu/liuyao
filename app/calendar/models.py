"""Pydantic models for the deterministic calendar module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GanZhi(BaseModel):
    """A single heavenly-stem/earthly-branch pair (干支)."""

    model_config = ConfigDict(frozen=True)

    stem: str
    branch: str

    @property
    def text(self) -> str:
        return f"{self.stem}{self.branch}"


class VoidBranches(BaseModel):
    """旬空: the two branches that are "empty" for the day's decade (旬)."""

    model_config = ConfigDict(frozen=True)

    first: str
    second: str

    def contains(self, branch: str) -> bool:
        return branch in (self.first, self.second)


class SolarTermCrossing(BaseModel):
    """An exact solar-term (节气) instant used as a month-building boundary."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="节气名称，如 立春")
    longitude: float = Field(description="太阳视黄经（度）")
    moment: datetime = Field(description="节气交接的精确本地时刻（Asia/Shanghai）")


class YearPillar(BaseModel):
    model_config = ConfigDict(frozen=True)

    ganzhi: GanZhi
    bazi_year: int = Field(description="以立春为界的干支纪年所属公历年")


class MonthPillar(BaseModel):
    model_config = ConfigDict(frozen=True)

    ganzhi: GanZhi
    jie_sector_index: int = Field(ge=0, le=11, description="自立春起的节序号（0=寅月）")
    starting_jie: SolarTermCrossing
    next_jie: SolarTermCrossing


class DayPillar(BaseModel):
    model_config = ConfigDict(frozen=True)

    ganzhi: GanZhi
    effective_date: str = Field(description="用于起日柱的公历日期（ISO 8601），已按子初换日规则调整")
    void_branches: VoidBranches


class HourPillar(BaseModel):
    model_config = ConfigDict(frozen=True)

    ganzhi: GanZhi


class CalendarContext(BaseModel):
    """Full, auditable calendar computation for one divination moment."""

    model_config = ConfigDict(frozen=True)

    input_year: int
    input_month: int
    input_day: int
    input_hour: int
    timezone: str
    zi_hour_boundary: int = Field(
        ge=0, le=24, description="子初换日边界小时（默认23，可配置）"
    )
    local_moment: datetime = Field(description="按 Asia/Shanghai 解释的原始输入时刻")

    year_pillar: YearPillar
    month_pillar: MonthPillar
    day_pillar: DayPillar
    hour_pillar: HourPillar
    six_spirits_by_line: tuple[str, str, str, str, str, str] = Field(
        description="初爻至上爻的六神，取自日干（019_六神章）"
    )

    near_boundary_note: str | None = Field(
        default=None,
        description="若输入时刻在节气或子初换日边界附近，说明换算依据，便于复核",
    )
