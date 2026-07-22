"""Generic, provider-agnostic input context for a divination LLM call.

Deliberately decoupled from ``app.chart``/``app.rules``/``app.knowledge``
(which this task must not touch and which may not exist yet): every field
here is a plain, self-describing primitive so that whichever module builds
the real chart/fact/knowledge objects only needs a thin adapter (e.g.
``FactContext(id=fact.id, type=fact.type, line=fact.line, value=fact.value,
property=..., description=...)``) to hand data to :mod:`app.llm.prompts` and
:mod:`app.divination.validator`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.llm.schemas import LineProperty


class FactContext(BaseModel):
    """One deterministically computed chart fact, as handed to the LLM.

    Mirrors the fact contract in implementation_plan.md §5.2 (``id``,
    ``type``, ``line``, ``value``, ``rule_source``) plus an optional
    normalized ``property`` tag used by the validator to catch a judgement
    that mislabels what a fact actually represents (e.g. claiming a fact
    about 月破 supports a claim about 旬空).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, description="本次排盘中稳定唯一的事实ID，如 fact-0012")
    type: str = Field(
        min_length=1,
        description="面向 LLM 的中文事实类型",
    )
    layer: Literal["chart", "raw", "derived", "effective"] = "chart"
    description: str = Field(min_length=1, description="供 LLM 阅读的事实中文描述")
    line: int | None = Field(default=None, ge=1, le=6, description="事实关联的爻位，1=初爻...6=上爻")
    related_lines: list[int] = Field(
        default_factory=list,
        description="事实关联的其他爻位，1=初爻...6=上爻",
    )
    value: bool | None = Field(default=None, description="事实的布尔结果，例如是否月破")
    property: LineProperty | None = Field(
        default=None,
        description="事实对应的规范化爻位属性标签，用于校验判断中的空/破/动/旺/衰/生克声明",
    )
    rule_source: str | None = Field(default=None, description="产生该事实所依据的规则出处 source_id")
    source_ids: list[str] = Field(default_factory=list, description="该规则事实全部直接原文出处")
    data: dict[str, Any] = Field(default_factory=dict, description="其余计算参数，仅供展示")

    @field_validator("description")
    @classmethod
    def description_must_not_expose_machine_codes(cls, description: str) -> str:
        if any("A" <= character <= "Z" or "a" <= character <= "z" for character in description):
            raise ValueError("LLM 事实描述不得包含英文机器码")
        return description


class SourceContext(BaseModel):
    """One retrieved 《增删卜易》 paragraph available for citation this turn."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, description="稳定引用ID，如 008_用神章:p0001")
    chapter: str = Field(min_length=1, description="章节标题")
    text: str = Field(min_length=1, description="逐字原文，citation.quote 必须是其子串")


class ExampleContext(BaseModel):
    """One complete worked example selected for explicit analogical reasoning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    example_id: str = Field(min_length=1)
    chapter: str = Field(min_length=1)
    match_score: float = Field(ge=0)
    match_reasons: list[str] = Field(default_factory=list)
    question: SourceContext | None = None
    chart: SourceContext | None = None
    judgement: SourceContext


class DecisionEvidenceContext(BaseModel):
    """One pre-classified fact group allowed to influence the outlook."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1)
    direction: Literal["有利", "不利", "条件性", "仅背景"]
    weight: Literal["主证", "辅证"]
    description: str = Field(min_length=1)
    fact_ids: list[str] = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)


class TimingCandidateContext(BaseModel):
    """One code-generated 应期 candidate the LLM may choose from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1, description="应期候选的稳定ID")
    condition: str = Field(min_length=1, description="触发该候选的规则条件")
    description: str = Field(min_length=1, description="候选时间范围或地支描述")
    source_ids: list[str] = Field(default_factory=list, description="支撑该候选的原文出处")


class DivinationRequestContext(BaseModel):
    """Everything the LLM is allowed to see and reason about for one request.

    The interpretation call receives the model-classified category, the
    code-resolved useful god, deterministic chart/facts, timing candidates
    and retrieved source paragraphs.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str = Field(min_length=1)
    category: str = Field(min_length=1)
    perspective: Literal["自占", "代占"]
    chart_summary: dict[str, Any] = Field(description="结构化排盘（由排盘引擎产生），原样转述给模型")
    useful_god: str = Field(min_length=1)
    facts: list[FactContext] = Field(default_factory=list)
    decision_guardrail: Literal[
        "仅有利主证",
        "仅不利主证",
        "正反证据并见",
        "暂不裁决",
    ] = "暂不裁决"
    decision_evidence: list[DecisionEvidenceContext] = Field(default_factory=list)
    decision_limitations: list[str] = Field(default_factory=list)
    timing_candidates: list[TimingCandidateContext] = Field(default_factory=list)
    sources: list[SourceContext] = Field(default_factory=list)
    examples: list[ExampleContext] = Field(default_factory=list)
