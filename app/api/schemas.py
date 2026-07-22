from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.calendar.models import CalendarContext
from app.chart.models import ChartFact, ChartLine, Hexagram
from app.knowledge.models import ContentType
from app.llm.schemas import DivinationConclusion
from app.rules.models import (
    OutcomeAnalysis,
    RuleFact,
    TimingCandidate,
    UsefulGodSelection,
)


class Category(StrEnum):
    WEATHER = "天时"
    LIFE = "身命"
    WEALTH = "求财"
    CAREER = "功名"
    MARRIAGE = "婚姻"
    PREGNANCY = "胎产"
    TRAVEL = "出行"
    TRAVELLER = "行人"
    LITIGATION = "诉讼"
    ILLNESS = "疾病"
    HOME = "家宅"
    BURIAL = "茔葬"
    FAMILY = "六亲"
    STUDY = "学业"
    OTHER = "其他"


class UsefulGodInput(StrEnum):
    WORLD = "世爻"
    RESPONSE = "应爻"
    PARENT = "父母"
    SIBLING = "兄弟"
    OFFICIAL = "官鬼"
    WEALTH = "妻财"
    CHILD = "子孙"


class CalendarInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=1, le=9999)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    hour: int = Field(ge=0, le=23)
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"

    @model_validator(mode="after")
    def validate_datetime(self) -> "CalendarInput":
        try:
            datetime(
                self.year,
                self.month,
                self.day,
                self.hour,
                tzinfo=ZoneInfo(self.timezone),
            )
        except ValueError as error:
            raise ValueError(f"公历日期或时间无效：{error}") from error
        return self

    def as_datetime(self) -> datetime:
        return datetime(
            self.year,
            self.month,
            self.day,
            self.hour,
            tzinfo=ZoneInfo(self.timezone),
        )


Question = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


class ChartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Question
    calendar: CalendarInput
    lines: list[int] = Field(min_length=6, max_length=6)

    @field_validator("lines")
    @classmethod
    def validate_lines(cls, value: list[int]) -> list[int]:
        invalid = [line for line in value if line not in {6, 7, 8, 9}]
        if invalid:
            raise ValueError("六爻每项只能是 6、7、8 或 9")
        return value


class DivinationRequest(ChartRequest):
    useful_god: UsefulGodInput


class InputSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str
    category: str | None
    perspective: Literal["自占", "代占"] | None = None
    calendar: str
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    line_order: Literal["初爻至上爻"] = "初爻至上爻"


class SourceOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    chapter_id: str
    chapter_title: str
    content_type: ContentType
    text: str
    is_editorial: bool
    source_path: str


class CaseEvidenceOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    example_id: str
    chapter_id: str
    chapter_title: str
    match_score: float
    match_reasons: tuple[str, ...]
    question: SourceOutput | None = None
    chart: SourceOutput | None = None
    judgement: SourceOutput


class ChartResponse(BaseModel):
    input_summary: InputSummary
    calendar: CalendarContext
    primary_hexagram: Hexagram
    changed_hexagram: Hexagram
    lines: tuple[ChartLine, ...]
    useful_god: UsefulGodSelection | None = None
    outcome_analysis: OutcomeAnalysis | None = None
    facts: tuple[ChartFact | RuleFact, ...]
    timing_candidates: tuple[TimingCandidate, ...] = ()
    limitations: tuple[str, ...] = ()


class DivinationResponse(ChartResponse):
    interpretation: DivinationConclusion
    case_evidence: tuple[CaseEvidenceOutput, ...]
    sources: tuple[SourceOutput, ...]
