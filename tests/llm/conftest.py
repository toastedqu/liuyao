"""Shared fixtures for the ``app.llm`` / ``app.divination.validator`` test suite."""

from __future__ import annotations

import pytest

from app.llm.context import DivinationRequestContext, FactContext, SourceContext, TimingCandidateContext
from app.llm.schemas import (
    CaseAnalysis,
    DivinationConclusion,
    Judgement,
    LineAssertion,
    LineProperty,
    MonthDayAnalysis,
    MovingLinesAnalysis,
    OverallConclusion,
    QuestionApplication,
    RisksAndUncertainties,
    SourceCitation,
    SpecialPatternsAnalysis,
    TimingSelection,
    UsefulGodAnalysis,
)

SOURCE_TEXT = "用神旺相，诸事可成；用神休囚，诸事难成，此乃野鹤断卦总纲。"


@pytest.fixture
def sample_context() -> DivinationRequestContext:
    return DivinationRequestContext(
        question="本次求财是否可成？",
        category="求财",
        chart_summary={"gua_name": "水地比", "palace": "坤宫"},
        useful_god=(
            '{"selection_mode":"relative","useful_relative":"妻财",'
            '"selected_line":null}'
        ),
        facts=[
            FactContext(
                id="fact-0001",
                type="MONTH_BREAK",
                description="三爻月破",
                line=3,
                value=True,
                property=LineProperty.PO,
            ),
            FactContext(
                id="fact-0002",
                type="MOVING",
                description="二爻动而化退",
                line=2,
                value=True,
                property=LineProperty.DONG,
            ),
        ],
        timing_candidates=[
            TimingCandidateContext(
                candidate_id="timing-0001",
                condition="静爻逢冲",
                description="预计在午日应验",
                source_ids=["008_用神章:p0001"],
            ),
        ],
        sources=[
            SourceContext(
                source_id="008_用神章:p0001",
                chapter="008_用神章",
                text=SOURCE_TEXT,
            ),
        ],
    )


def make_conclusion(
    *,
    fact_ids: list[str] | None = None,
    citations: list[SourceCitation] | None = None,
    line_assertions: list[LineAssertion] | None = None,
    candidate_ids: list[str] | None = None,
    insufficient_evidence: bool = False,
    extra_statement: str = "用神妻财旺相，求财可成。",
) -> DivinationConclusion:
    """Build a minimal-but-valid ``DivinationConclusion`` for one judgement."""
    resolved_fact_ids = ["fact-0001"] if fact_ids is None else fact_ids
    judgement = Judgement(
        statement=extra_statement,
        fact_ids=resolved_fact_ids,
        citations=citations or [],
        line_assertions=line_assertions or [],
    )
    return DivinationConclusion(
        overall=OverallConclusion(outlook="吉", summary="求财可成", judgements=[judgement]),
        question_application=QuestionApplication(
            focus="本次所问求财能否办成",
            synthesis=Judgement(
                statement="结合本卦事实，本次求财有明确判断方向。",
                fact_ids=["fact-0001"],
            ),
        ),
        case_analysis=CaseAnalysis(comparisons=[]),
        useful_god=UsefulGodAnalysis(useful_god="妻财", judgements=[]),
        month_day=MonthDayAnalysis(judgements=[]),
        moving_lines=MovingLinesAnalysis(judgements=[]),
        special_patterns=SpecialPatternsAnalysis(patterns=[]),
        timing=TimingSelection(
            candidate_ids=candidate_ids or [],
            judgements=[],
            insufficient_evidence=insufficient_evidence,
        ),
        risks=RisksAndUncertainties(items=[]),
    )


@pytest.fixture
def sample_conclusion() -> DivinationConclusion:
    return make_conclusion(
        fact_ids=["fact-0001"],
        citations=[SourceCitation(source_id="008_用神章:p0001", quote="用神旺相，诸事可成")],
        line_assertions=[LineAssertion(line=3, property=LineProperty.PO, asserted=True, fact_id="fact-0001")],
        candidate_ids=["timing-0001"],
    )
