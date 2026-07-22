"""Structured LLM output schemas (implementation_plan.md §11.3).

Every section of the断卦 result is expressed as one or more :class:`Judgement`
objects so that :func:`iter_judgements` (and, in turn,
``app.divination.validator``) can walk the whole tree generically instead of
special-casing each section. Each ``Judgement`` must cite the ``fact_id``s
and ``source_id``s (with verbatim quotes) that support it; ``line_assertions``
make any claim about a specific line's 空/破/动/静/旺/衰/生/克 state an
explicit, machine-checkable statement instead of free prose, which is what
lets the validator catch a judgement that misstates a chart fact.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Iterator, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LineProperty(StrEnum):
    """The line properties implementation_plan.md §12 explicitly guards.

    ``KONG`` (空, 旬空), ``PO`` (破, 月破), ``DONG`` (动, 动爻), ``JING``
    (静, 静爻), ``WANG`` (旺, 旺相), ``SHUAI`` (衰, 休囚), ``SHENG`` (生,
    逢生/回头生), ``KE`` (克, 受克/回头克).
    """

    KONG = "空"
    PO = "破"
    DONG = "动"
    JING = "静"
    WANG = "旺"
    SHUAI = "衰"
    SHENG = "生"
    KE = "克"


class SourceCitation(BaseModel):
    """A verbatim quote from one retrieved 《增删卜易》paragraph."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, description="必须是本次检索结果中的 source_id")
    quote: str = Field(min_length=1, description="从该出处逐字摘录的原文，禁止转述、增删或概括")

    @field_validator("source_id", "quote")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("引用出处和引文不得为空白")
        return stripped


class QuestionCategory(BaseModel):
    """Classify the matter and whether it concerns the asker or another person."""

    model_config = ConfigDict(extra="forbid")

    category: Literal[
        "天时",
        "身命",
        "求财",
        "功名",
        "婚姻",
        "胎产",
        "出行",
        "行人",
        "诉讼",
        "疾病",
        "家宅",
        "茔葬",
        "六亲",
        "学业",
        "其他",
    ]
    perspective: Literal["自占", "代占"] = Field(
        description=(
            "自占=问占者自己的事项；代占=替父母、子女、伴侣、亲友等他人问占"
        )
    )


class LineAssertion(BaseModel):
    """An explicit, checkable claim about one line's chart-fact property."""

    model_config = ConfigDict(extra="forbid")

    line: int = Field(ge=1, le=6, description="1=初爻 ... 6=上爻")
    property: LineProperty
    asserted: bool = Field(default=True, description="True=声称具有该属性；False=声称不具有")
    fact_id: str | None = Field(default=None, description="支撑该声明的排盘事实ID，必须提供")


class Judgement(BaseModel):
    """One traceable statement backed by facts and/or original text."""

    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1, description="判断的中文表述")
    fact_ids: list[str] = Field(default_factory=list)
    citations: list[SourceCitation] = Field(default_factory=list)
    line_assertions: list[LineAssertion] = Field(default_factory=list)


class QuestionApplication(BaseModel):
    """Translate abstract chart facts into the concrete matter being asked."""

    model_config = ConfigDict(extra="forbid")

    focus: str = Field(
        min_length=1,
        max_length=200,
        description="用用户实际问题中的对象和目标表述本次要回答的具体事项",
    )
    favorable: list[Judgement] = Field(default_factory=list)
    adverse: list[Judgement] = Field(default_factory=list)
    synthesis: Judgement


class CaseComparison(BaseModel):
    """A traceable comparison between this chart and one original worked case."""

    model_config = ConfigDict(extra="forbid")

    example_id: str = Field(min_length=1, description="必须来自本次提供的候选卦例")
    role: Literal["reference_only"] = Field(
        description="固定为 reference_only；卦例不能参与本卦吉凶权重"
    )
    similarities: Judgement
    differences: Judgement
    application: Judgement


class CaseAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparisons: list[CaseComparison] = Field(default_factory=list)


class OverallConclusion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outlook: Literal["吉", "凶", "吉中有阻", "凶中有救", "需再占"]
    summary: str = Field(min_length=1)
    judgements: list[Judgement] = Field(default_factory=list)


class UsefulGodAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    useful_god: str = Field(min_length=1)
    judgements: list[Judgement] = Field(default_factory=list)


class MonthDayAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judgements: list[Judgement] = Field(default_factory=list)


class MovingLinesAnalysis(BaseModel):
    """动爻及元神/忌神分析。"""

    model_config = ConfigDict(extra="forbid")

    judgements: list[Judgement] = Field(default_factory=list)


class SpecialPattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="格局名称，须为《增删卜易》原书概念")
    judgements: list[Judgement] = Field(default_factory=list)


class SpecialPatternsAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patterns: list[SpecialPattern] = Field(default_factory=list)


class TimingSelection(BaseModel):
    """应期选择：只能从系统提供的候选中选择，不得自行编造。"""

    model_config = ConfigDict(extra="forbid")

    candidate_ids: list[str] = Field(default_factory=list, description="选中的应期候选ID")
    judgements: list[Judgement] = Field(default_factory=list)
    insufficient_evidence: bool = Field(
        default=False,
        description="证据不足时置真；此时 candidate_ids 必须为空，不得输出确定应期",
    )


class RiskItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)
    judgements: list[Judgement] = Field(default_factory=list)


class RisksAndUncertainties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RiskItem] = Field(default_factory=list)


class DivinationConclusion(BaseModel):
    """The complete structured断卦 result the LLM must return."""

    model_config = ConfigDict(extra="forbid")

    overall: OverallConclusion
    question_application: QuestionApplication
    case_analysis: CaseAnalysis
    useful_god: UsefulGodAnalysis
    month_day: MonthDayAnalysis
    moving_lines: MovingLinesAnalysis
    special_patterns: SpecialPatternsAnalysis
    timing: TimingSelection
    risks: RisksAndUncertainties

    def iter_judgements(self) -> Iterator[tuple[str, Judgement]]:
        """Yield ``(path, judgement)`` for every judgement in the whole tree.

        ``path`` is a stable, human-readable locator (e.g.
        ``"special_patterns.patterns[0].judgements[1]"``) suitable for error
        messages and for building a targeted correction prompt.
        """
        for i, judgement in enumerate(self.overall.judgements):
            yield f"overall.judgements[{i}]", judgement
        for i, judgement in enumerate(self.question_application.favorable):
            yield f"question_application.favorable[{i}]", judgement
        for i, judgement in enumerate(self.question_application.adverse):
            yield f"question_application.adverse[{i}]", judgement
        yield "question_application.synthesis", self.question_application.synthesis
        for ci, comparison in enumerate(self.case_analysis.comparisons):
            yield f"case_analysis.comparisons[{ci}].similarities", comparison.similarities
            yield f"case_analysis.comparisons[{ci}].differences", comparison.differences
            yield f"case_analysis.comparisons[{ci}].application", comparison.application
        for i, judgement in enumerate(self.useful_god.judgements):
            yield f"useful_god.judgements[{i}]", judgement
        for i, judgement in enumerate(self.month_day.judgements):
            yield f"month_day.judgements[{i}]", judgement
        for i, judgement in enumerate(self.moving_lines.judgements):
            yield f"moving_lines.judgements[{i}]", judgement
        for pi, pattern in enumerate(self.special_patterns.patterns):
            for i, judgement in enumerate(pattern.judgements):
                yield f"special_patterns.patterns[{pi}].judgements[{i}]", judgement
        for i, judgement in enumerate(self.timing.judgements):
            yield f"timing.judgements[{i}]", judgement
        for ri, item in enumerate(self.risks.items):
            for i, judgement in enumerate(item.judgements):
                yield f"risks.items[{ri}].judgements[{i}]", judgement
