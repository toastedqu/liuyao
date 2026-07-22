from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_serializer,
    field_validator,
    model_validator,
)

from app.fact_display import fact_result_for_display
from app.fact_types import fact_type_label


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


class FactLayer(StrEnum):
    RAW = "raw"
    DERIVED = "derived"
    EFFECTIVE = "effective"


class RuleStatus(StrEnum):
    AUTHORITATIVE = "authoritative"
    CONDITIONAL = "conditional"
    DISCARDED = "discarded"


class QuestionPerspective(StrEnum):
    SELF = "self"
    PROXY = "proxy"


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
    spirit: str | None = None
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
    changed_palace_element: Element | None = None
    primary_hexagram: str
    changed_hexagram: str
    primary_is_six_clash: bool = False
    primary_is_six_harmony: bool = False
    changed_is_six_clash: bool = False
    changed_is_six_harmony: bool = False
    primary_is_wandering_soul: bool = False
    primary_is_returning_soul: bool = False
    lines: tuple[LineContext, ...]
    year_branch: str | None = None
    category: str | None = None
    perspective: QuestionPerspective | None = None


class UsefulGodChoice(BaseModel):
    model_config = ConfigDict(frozen=True)

    target: str
    mode: Literal["world", "response", "relative"]
    useful_relative: Relative | None = None
    rationale: str
    source_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_mode_and_relative(self) -> "UsefulGodChoice":
        if self.mode in {"world", "response"} and self.useful_relative is not None:
            raise ValueError("世爻或应爻模式不得指定六亲")
        if self.mode == "relative" and self.useful_relative is None:
            raise ValueError("六亲模式必须指定六亲")
        if not self.source_ids:
            raise ValueError("用神选择必须有原文出处")
        return self


class RuleFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: str = Field(description="内部稳定类型代码；对外 JSON 统一序列化为中文")
    layer: FactLayer
    rule_id: str
    line: int | None = None
    related_lines: tuple[int, ...] = ()
    value: JsonValue
    evidence: dict[str, JsonValue] = Field(default_factory=dict)
    source_ids: tuple[str, ...]
    rule_source: str

    @field_validator("type")
    @classmethod
    def validate_type_has_label(cls, fact_type: str) -> str:
        fact_type_label(fact_type)
        return fact_type

    @field_serializer("type", when_used="json")
    def serialize_type(self, fact_type: str) -> str:
        return fact_type_label(fact_type)

    @field_serializer("value", when_used="json")
    def serialize_value(self, _value: JsonValue) -> JsonValue:
        return fact_result_for_display(self)

    @model_validator(mode="after")
    def validate_sources(self) -> "RuleFact":
        if not self.source_ids:
            raise ValueError("规则事实必须至少有一个原文出处")
        if self.rule_source not in self.source_ids:
            raise ValueError("rule_source 必须包含在 source_ids 中")
        return self


class UsefulGodCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["visible", "changed", "hidden", "world", "response"]
    line: int | None
    relative: Relative | None
    branch: str | None
    element: Element | None
    reasons: tuple[str, ...] = ()


class UsefulGodSelection(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["selected", "multiple", "unresolved"]
    target: str
    selection_mode: Literal["world", "response", "relative"] | None = None
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


class OutcomeEvidenceDirection(StrEnum):
    FAVORABLE = "有利"
    ADVERSE = "不利"
    CONDITIONAL = "条件性"
    CONTEXT = "仅背景"


class OutcomeEvidenceWeight(StrEnum):
    PRIMARY = "主证"
    SUPPORTING = "辅证"


class OutcomeGuardrail(StrEnum):
    FAVORABLE_ONLY = "仅有利主证"
    ADVERSE_ONLY = "仅不利主证"
    MIXED = "正反证据并见"
    ABSTAIN = "暂不裁决"


class OutcomeEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    direction: OutcomeEvidenceDirection
    weight: OutcomeEvidenceWeight
    description: str
    fact_ids: tuple[str, ...]
    source_ids: tuple[str, ...] = ()


class OutcomeAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    guardrail: OutcomeGuardrail
    evidence: tuple[OutcomeEvidence, ...] = ()
    limitations: tuple[str, ...] = ()


class RuleAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    useful_god: UsefulGodSelection
    facts: tuple[RuleFact, ...]
    outcome_analysis: OutcomeAnalysis
    timing_candidates: tuple[TimingCandidate, ...]
    implemented_rule_types: tuple[str, ...]
    unimplemented_rules: tuple[str, ...]
