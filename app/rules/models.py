from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class Element(StrEnum):
    WOOD = "木"
    FIRE = "火"
    EARTH = "土"
    METAL = "金"
    WATER = "水"


class Relative(StrEnum):
    PARENT = "父母"
    SIBLING = "兄弟"
    OFFICIAL = "官鬼"
    WEALTH = "妻财"
    CHILD = "子孙"


class ChangedLineContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    branch: str
    element: Element
    relative: Relative
    is_yang: bool


class HiddenSpiritContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    branch: str
    element: Element
    relative: Relative
    stem: str | None = None


class LineContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=1, le=6)
    branch: str
    element: Element
    relative: Relative
    is_yang: bool
    is_moving: bool
    is_world: bool = False
    is_response: bool = False
    changed: ChangedLineContext | None = None
    hidden_spirit: HiddenSpiritContext | None = None


class RuleContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str
    month_branch: str
    day_stem: str
    day_branch: str
    void_branches: tuple[str, str]
    palace_element: Element
    primary_hexagram: str
    changed_hexagram: str
    primary_is_six_clash: bool = False
    primary_is_six_harmony: bool = False
    changed_is_six_clash: bool = False
    changed_is_six_harmony: bool = False
    primary_is_wandering_soul: bool = False
    primary_is_returning_soul: bool = False
    lines: tuple[LineContext, ...]


class UsefulGodChoice(BaseModel):
    model_config = ConfigDict(frozen=True)

    target: str
    mode: Literal["world", "relative"]
    useful_relative: Relative | None = None
    rationale: str
    source_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_mode_and_relative(self) -> "UsefulGodChoice":
        if self.mode == "world" and self.useful_relative is not None:
            raise ValueError("世爻模式不得指定六亲")
        if self.mode == "relative" and self.useful_relative is None:
            raise ValueError("六亲模式必须指定六亲")
        if not self.source_ids:
            raise ValueError("模型用神判定必须有原文出处")
        return self


class RuleFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    line: int | None = None
    related_lines: tuple[int, ...] = ()
    value: JsonValue
    evidence: dict[str, JsonValue] = Field(default_factory=dict)
    rule_source: str


class UsefulGodCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["visible", "hidden", "world", "response"]
    line: int | None
    relative: Relative | None
    branch: str | None
    element: Element | None
    score: int
    reasons: tuple[str, ...] = ()


class UsefulGodSelection(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["selected", "multiple", "unresolved"]
    target: str
    selection_mode: Literal["world", "relative"] | None = None
    useful_relative: Relative | None
    candidates: tuple[UsefulGodCandidate, ...] = ()
    selected_line: int | None = None
    useful_element: Element | None = None
    yuan_element: Element | None = None
    taboo_element: Element | None = None
    enemy_element: Element | None = None
    rationale: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()


class TimingCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    trigger: str
    branches: tuple[str, ...]
    time_unit_hint: Literal["时/日", "日/月", "月/年", "依问题远近"]
    confidence_limit: str
    fact_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()


class RuleAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    useful_god: UsefulGodSelection
    facts: tuple[RuleFact, ...]
    timing_candidates: tuple[TimingCandidate, ...]
    implemented_rule_types: tuple[str, ...]
    unimplemented_rules: tuple[str, ...]
