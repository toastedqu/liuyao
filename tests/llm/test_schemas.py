"""Tests for app.llm.schemas: DivinationConclusion.iter_judgements traversal
and basic structural validation (extra keys forbidden, enum constraints).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.schemas import (
    DivinationConclusion,
    Judgement,
    LineAssertion,
    LineProperty,
    MonthDayAnalysis,
    MovingLinesAnalysis,
    OverallConclusion,
    RiskItem,
    RisksAndUncertainties,
    SourceCitation,
    SpecialPattern,
    SpecialPatternsAnalysis,
    TimingSelection,
    UsefulGodDecision,
    UsefulGodAnalysis,
)


def _judgement(text: str) -> Judgement:
    return Judgement(statement=text)


def test_iter_judgements_visits_every_section_in_order() -> None:
    conclusion = DivinationConclusion(
        overall=OverallConclusion(outlook="吉", summary="s", judgements=[_judgement("overall-0")]),
        useful_god=UsefulGodAnalysis(useful_god="妻财", judgements=[_judgement("useful-god-0")]),
        month_day=MonthDayAnalysis(judgements=[_judgement("month-day-0")]),
        moving_lines=MovingLinesAnalysis(judgements=[_judgement("moving-0")]),
        special_patterns=SpecialPatternsAnalysis(
            patterns=[SpecialPattern(name="独发", judgements=[_judgement("pattern-0")])]
        ),
        timing=TimingSelection(candidate_ids=[], judgements=[_judgement("timing-0")]),
        risks=RisksAndUncertainties(items=[RiskItem(description="风险", judgements=[_judgement("risk-0")])]),
    )

    visited = list(conclusion.iter_judgements())
    paths = [path for path, _ in visited]
    statements = [judgement.statement for _, judgement in visited]

    assert paths == [
        "overall.judgements[0]",
        "useful_god.judgements[0]",
        "month_day.judgements[0]",
        "moving_lines.judgements[0]",
        "special_patterns.patterns[0].judgements[0]",
        "timing.judgements[0]",
        "risks.items[0].judgements[0]",
    ]
    assert statements == [
        "overall-0",
        "useful-god-0",
        "month-day-0",
        "moving-0",
        "pattern-0",
        "timing-0",
        "risk-0",
    ]


def test_judgement_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Judgement(statement="x", unexpected_field=True)  # type: ignore[call-arg]


def test_overall_conclusion_outlook_is_restricted_enum() -> None:
    with pytest.raises(ValidationError):
        OverallConclusion(outlook="大凶大吉", summary="s")


def test_line_assertion_line_must_be_in_range() -> None:
    with pytest.raises(ValidationError):
        LineAssertion(line=7, property=LineProperty.KONG, fact_id="fact-1")


def test_line_assertion_defaults_asserted_true() -> None:
    assertion = LineAssertion(line=1, property=LineProperty.DONG, fact_id="fact-1")
    assert assertion.asserted is True


def test_source_citation_requires_nonempty_quote() -> None:
    with pytest.raises(ValidationError):
        SourceCitation(source_id="008_用神章:p0001", quote="")


def test_timing_selection_defaults_to_no_candidates_and_sufficient_evidence() -> None:
    selection = TimingSelection()
    assert selection.candidate_ids == []
    assert selection.insufficient_evidence is False


def test_useful_god_decision_enforces_mode_and_relative() -> None:
    citation = SourceCitation(source_id="008_用神章:p0006", quote="以财爻为用神")
    decision = UsefulGodDecision(
        category="求财",
        target="求财",
        mode="relative",
        useful_relative="妻财",
        rationale="问题所问为财物。",
        citations=[citation],
    )
    assert decision.useful_relative == "妻财"

    with pytest.raises(ValidationError, match="mode=world"):
        UsefulGodDecision(
            category="身命",
            target="本人近况",
            mode="world",
            useful_relative="妻财",
            rationale="问本人。",
            citations=[citation],
        )
