"""Tests for app.divination.validator: fact ids, source ids, verbatim quotes,
timing candidates, fact-conflicting line assertions, and forbidden terms.

The validator never calls a model; every test here constructs a
``DivinationConclusion`` directly (as if it had already been parsed from an
LLM response) and checks the returned ``ValidationResult``.
"""

from __future__ import annotations

from app.divination.validator import (
    validate_divination_conclusion,
    validate_useful_god_decision,
)
from app.llm.context import ExampleContext, SourceContext
from app.llm.schemas import (
    CaseAnalysis,
    CaseComparison,
    Judgement,
    LineAssertion,
    LineProperty,
    RiskItem,
    SourceCitation,
    UsefulGodDecision,
)
from tests.llm.conftest import make_conclusion


def _context_with_case(sample_context):
    question = SourceContext(
        source_id="076_求财章:example0001:question",
        chapter="求财章",
        text="占求财，得泽火革。",
    )
    judgement = SourceContext(
        source_id="076_求财章:example0001:judgement",
        chapter="求财章",
        text="断曰：财爻不现，如缘木以求鱼也。",
    )
    return sample_context.model_copy(
        update={
            "sources": [*sample_context.sources, question, judgement],
            "examples": [
                ExampleContext(
                    example_id="076_求财章:example0001",
                    chapter="求财章",
                    match_score=8.5,
                    match_reasons=["同占类：求财"],
                    question=question,
                    judgement=judgement,
                )
            ],
        }
    )


def _valid_case_analysis() -> CaseAnalysis:
    return CaseAnalysis(
        comparisons=[
            CaseComparison(
                example_id="076_求财章:example0001",
                similarities=Judgement(
                    statement="本问与原例同属求财。",
                    fact_ids=["fact-0001"],
                    citations=[
                        SourceCitation(
                            source_id="076_求财章:example0001:question",
                            quote="占求财",
                        )
                    ],
                ),
                differences=Judgement(
                    statement="本卦须以自己的月破事实区别于原例。",
                    fact_ids=["fact-0001"],
                    citations=[
                        SourceCitation(
                            source_id="076_求财章:example0001:judgement",
                            quote="财爻不现",
                        )
                    ],
                ),
                application=Judgement(
                    statement="原例断财难求，本问只迁移其权衡方法。",
                    fact_ids=["fact-0001"],
                    citations=[
                        SourceCitation(
                            source_id="076_求财章:example0001:judgement",
                            quote="如缘木以求鱼也",
                        )
                    ],
                ),
            )
        ]
    )


def test_valid_conclusion_passes(sample_context, sample_conclusion) -> None:
    result = validate_divination_conclusion(sample_conclusion, sample_context)
    assert result.valid is True
    assert result.issues == []


def test_question_synthesis_must_use_current_chart_fact(sample_context) -> None:
    conclusion = make_conclusion()
    conclusion.question_application.synthesis.fact_ids = []
    conclusion.question_application.synthesis.citations = [
        SourceCitation(
            source_id="008_用神章:p0001",
            quote="用神旺相，诸事可成",
        )
    ]

    result = validate_divination_conclusion(conclusion, sample_context)

    assert "question_synthesis_missing_current_fact" in {
        issue.code for issue in result.issues
    }


def test_uncertain_outlook_requires_explicit_two_sided_conflict(sample_context) -> None:
    conclusion = make_conclusion()
    conclusion.overall.outlook = "不确定"

    result = validate_divination_conclusion(conclusion, sample_context)

    assert "uncertain_without_explicit_conflict" in {
        issue.code for issue in result.issues
    }


def test_provided_cases_must_be_compared(sample_context) -> None:
    context = _context_with_case(sample_context)

    result = validate_divination_conclusion(make_conclusion(), context)

    assert "case_comparison_required" in {issue.code for issue in result.issues}


def test_traceable_case_comparison_passes(sample_context) -> None:
    context = _context_with_case(sample_context)
    conclusion = make_conclusion()
    conclusion.case_analysis = _valid_case_analysis()

    assert validate_divination_conclusion(conclusion, context).valid is True


def test_case_application_must_cite_original_outcome(sample_context) -> None:
    context = _context_with_case(sample_context)
    conclusion = make_conclusion()
    conclusion.case_analysis = _valid_case_analysis()
    conclusion.case_analysis.comparisons[0].application.citations = [
        SourceCitation(
            source_id="076_求财章:example0001:question",
            quote="占求财",
        )
    ]

    result = validate_divination_conclusion(conclusion, context)

    assert "case_application_missing_outcome" in {
        issue.code for issue in result.issues
    }


def test_unknown_fact_id_is_rejected(sample_context) -> None:
    conclusion = make_conclusion(fact_ids=["fact-does-not-exist"])
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is False
    codes = {issue.code for issue in result.issues}
    assert "unknown_fact_id" in codes
    issue = next(i for i in result.issues if i.code == "unknown_fact_id")
    assert issue.details["fact_id"] == "fact-does-not-exist"
    assert "overall.judgements[0].fact_ids[0]" == issue.path


def test_judgement_without_fact_or_source_is_rejected(sample_context) -> None:
    conclusion = make_conclusion(fact_ids=[], citations=[])

    result = validate_divination_conclusion(conclusion, sample_context)

    assert result.valid is False
    assert "judgement_missing_evidence" in {issue.code for issue in result.issues}


def test_forged_source_id_is_rejected(sample_context) -> None:
    conclusion = make_conclusion(
        citations=[SourceCitation(source_id="999_不存在章:p9999", quote="子虚乌有之言")]
    )
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is False
    codes = {issue.code for issue in result.issues}
    assert "unknown_source_id" in codes


def test_paraphrased_quote_is_rejected(sample_context) -> None:
    """A quote that summarizes rather than verbatim-copies the source must fail."""
    conclusion = make_conclusion(
        citations=[
            SourceCitation(
                source_id="008_用神章:p0001",
                quote="用神旺则事成，衰则事败",  # not a verbatim substring
            )
        ]
    )
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is False
    issue = next(i for i in result.issues if i.code == "citation_quote_mismatch")
    assert issue.details["source_id"] == "008_用神章:p0001"


def test_exact_quote_passes(sample_context) -> None:
    conclusion = make_conclusion(
        citations=[SourceCitation(source_id="008_用神章:p0001", quote="用神休囚，诸事难成")]
    )
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is True


def test_unknown_timing_candidate_is_rejected(sample_context) -> None:
    conclusion = make_conclusion(candidate_ids=["timing-does-not-exist"])
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is False
    codes = {issue.code for issue in result.issues}
    assert "unknown_timing_candidate" in codes


def test_insufficient_evidence_with_candidates_is_rejected(sample_context) -> None:
    conclusion = make_conclusion(candidate_ids=["timing-0001"], insufficient_evidence=True)
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is False
    codes = {issue.code for issue in result.issues}
    assert "timing_evidence_conflict" in codes


def test_insufficient_evidence_without_candidates_passes(sample_context) -> None:
    conclusion = make_conclusion(candidate_ids=[], insufficient_evidence=True)
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is True


def test_line_assertion_without_fact_id_is_rejected(sample_context) -> None:
    conclusion = make_conclusion(
        line_assertions=[LineAssertion(line=3, property=LineProperty.PO, asserted=True, fact_id=None)]
    )
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is False
    codes = {issue.code for issue in result.issues}
    assert "line_assertion_missing_fact" in codes


def test_line_assertion_conflicting_with_fact_value_is_rejected(sample_context) -> None:
    """fact-0001 says line 3 IS month-broken (value=True); asserting the opposite must fail."""
    conclusion = make_conclusion(
        fact_ids=["fact-0001"],
        line_assertions=[LineAssertion(line=3, property=LineProperty.PO, asserted=False, fact_id="fact-0001")],
    )
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is False
    issue = next(i for i in result.issues if i.code == "fact_conflict")
    assert issue.details["fact_id"] == "fact-0001"
    assert issue.details["claimed"] is False
    assert issue.details["actual"] is True


def test_line_assertion_wrong_line_is_rejected(sample_context) -> None:
    """fact-0001 is about line 3; claiming it supports a statement about line 5 must fail."""
    conclusion = make_conclusion(
        fact_ids=["fact-0001"],
        line_assertions=[LineAssertion(line=5, property=LineProperty.PO, asserted=True, fact_id="fact-0001")],
    )
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is False
    codes = {issue.code for issue in result.issues}
    assert "line_assertion_line_mismatch" in codes


def test_line_assertion_wrong_property_is_rejected(sample_context) -> None:
    """fact-0001's property is PO (破); claiming it supports a KONG (空) assertion must fail."""
    conclusion = make_conclusion(
        fact_ids=["fact-0001"],
        line_assertions=[LineAssertion(line=3, property=LineProperty.KONG, asserted=True, fact_id="fact-0001")],
    )
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is False
    codes = {issue.code for issue in result.issues}
    assert "line_assertion_property_mismatch" in codes


def test_line_assertion_requires_a_line_scoped_property_fact(sample_context) -> None:
    context = sample_context.model_copy(
        update={
            "facts": [
                sample_context.facts[0].model_copy(
                    update={"id": "fact-unscoped", "line": None, "property": None}
                )
            ]
        }
    )
    conclusion = make_conclusion(
        fact_ids=["fact-unscoped"],
        line_assertions=[
            LineAssertion(
                line=3,
                property=LineProperty.PO,
                asserted=True,
                fact_id="fact-unscoped",
            )
        ],
    )

    result = validate_divination_conclusion(conclusion, context)

    codes = {issue.code for issue in result.issues}
    assert "line_assertion_fact_has_no_line" in codes
    assert "line_assertion_fact_has_no_property" in codes


def test_prose_line_claim_requires_matching_assertion(sample_context) -> None:
    conclusion = make_conclusion(
        extra_statement="第三爻月破，事情暂时受阻。",
        fact_ids=["fact-0001"],
    )

    result = validate_divination_conclusion(conclusion, sample_context)

    assert "prose_line_claim_missing_assertion" in {
        issue.code for issue in result.issues
    }


def test_generic_six_lines_phrase_is_not_misread_as_sixth_line(
    sample_context,
) -> None:
    conclusion = make_conclusion(
        extra_statement="六爻排盘中的动爻事实均以代码结果为准。",
    )

    assert validate_divination_conclusion(conclusion, sample_context).valid is True


def test_explicit_sixth_line_claim_still_requires_assertion(sample_context) -> None:
    conclusion = make_conclusion(
        extra_statement="第六爻月破，事情暂时受阻。",
    )

    result = validate_divination_conclusion(conclusion, sample_context)

    assert "prose_line_claim_missing_assertion" in {
        issue.code for issue in result.issues
    }


def test_timing_claim_must_come_from_selected_candidate(sample_context) -> None:
    invalid = make_conclusion(
        candidate_ids=["timing-0001"],
        extra_statement="此事可能在子日应验。",
    )
    result = validate_divination_conclusion(invalid, sample_context)
    assert "unauthorized_timing_claim" in {issue.code for issue in result.issues}

    valid = make_conclusion(
        candidate_ids=["timing-0001"],
        extra_statement="此事可能在午日应验。",
    )
    assert validate_divination_conclusion(valid, sample_context).valid is True


def test_absolute_timing_date_is_rejected(sample_context) -> None:
    conclusion = make_conclusion(
        candidate_ids=["timing-0001"],
        extra_statement="此事将在2026年8月3日应验。",
    )

    result = validate_divination_conclusion(conclusion, sample_context)

    assert "unauthorized_absolute_timing" in {issue.code for issue in result.issues}


def test_absolute_timing_in_summary_is_rejected(sample_context) -> None:
    conclusion = make_conclusion()
    conclusion.overall.summary = "预计2026年8月3日应验"

    result = validate_divination_conclusion(conclusion, sample_context)

    assert "unauthorized_absolute_timing" in {issue.code for issue in result.issues}


def test_branch_timing_in_risk_description_is_rejected(sample_context) -> None:
    conclusion = make_conclusion()
    conclusion.risks.items = [
        RiskItem(description="须等待子日才能确定", judgements=[])
    ]

    result = validate_divination_conclusion(conclusion, sample_context)

    assert "unauthorized_timing_claim" in {issue.code for issue in result.issues}


def test_line_claim_in_summary_must_move_to_a_judgement(sample_context) -> None:
    conclusion = make_conclusion()
    conclusion.overall.summary = "第三爻月破，故暂时受阻"

    result = validate_divination_conclusion(conclusion, sample_context)

    assert "line_claim_outside_judgement" in {issue.code for issue in result.issues}


def test_interpretation_cannot_override_preselected_useful_god(sample_context) -> None:
    conclusion = make_conclusion()
    conclusion.useful_god.useful_god = "兄弟"

    result = validate_divination_conclusion(conclusion, sample_context)

    assert "useful_god_conflict" in {issue.code for issue in result.issues}


def test_useful_god_accepts_matching_relative_and_selected_line(
    sample_context,
) -> None:
    context = sample_context.model_copy(
        update={
            "useful_god": (
                '{"status":"selected","selection_mode":"relative",'
                '"useful_relative":"妻财",'
                '"selected_line":5}'
            )
        }
    )
    conclusion = make_conclusion()
    conclusion.useful_god.useful_god = "第五爻妻财"

    assert validate_divination_conclusion(conclusion, context).valid is True


def test_useful_god_rejects_wrong_selected_line(sample_context) -> None:
    context = sample_context.model_copy(
        update={
            "useful_god": (
                '{"status":"selected","selection_mode":"relative",'
                '"useful_relative":"妻财",'
                '"selected_line":5}'
            )
        }
    )
    conclusion = make_conclusion()
    conclusion.useful_god.useful_god = "第三爻妻财"

    result = validate_divination_conclusion(conclusion, context)

    assert "useful_god_conflict" in {issue.code for issue in result.issues}


def test_world_useful_god_requires_world_line_wording(sample_context) -> None:
    context = sample_context.model_copy(
        update={
            "useful_god": (
                '{"status":"selected","selection_mode":"world",'
                '"useful_relative":"子孙","selected_line":1}'
            )
        }
    )
    conclusion = make_conclusion()
    conclusion.useful_god.useful_god = "初爻世爻（子孙）"
    assert validate_divination_conclusion(conclusion, context).valid is True

    conclusion.useful_god.useful_god = "初爻子孙"
    result = validate_divination_conclusion(conclusion, context)
    assert "useful_god_conflict" in {issue.code for issue in result.issues}


def test_useful_god_decision_citations_must_be_verbatim(sample_context) -> None:
    decision = UsefulGodDecision(
        category="求财",
        target="求财",
        mode="relative",
        useful_relative="妻财",
        rationale="用户询问财物。",
        citations=[
            SourceCitation(
                source_id="008_用神章:p0001",
                quote="用神旺相，诸事可成",
            )
        ],
    )
    assert validate_useful_god_decision(
        decision,
        sample_context.sources,
    ).valid is True

    decision.citations[0].quote = "并非逐字原文"
    result = validate_useful_god_decision(decision, sample_context.sources)
    assert "citation_quote_mismatch" in {issue.code for issue in result.issues}


def test_forbidden_term_is_rejected(sample_context) -> None:
    conclusion = make_conclusion(extra_statement="结合紫微斗数来看，此爻大吉。")
    result = validate_divination_conclusion(conclusion, sample_context)
    assert result.valid is False
    issue = next(i for i in result.issues if i.code == "forbidden_term")
    assert issue.details["term"] == "紫微斗数"


def test_custom_forbidden_terms_override_default_list(sample_context) -> None:
    conclusion = make_conclusion(extra_statement="此判断涉及自定义黑名单术语。")
    result = validate_divination_conclusion(conclusion, sample_context, forbidden_terms=["自定义黑名单术语"])
    assert result.valid is False
    assert result.issues[0].code == "forbidden_term"
    assert result.issues[0].details["term"] == "自定义黑名单术语"


def test_multiple_issues_are_all_reported(sample_context) -> None:
    conclusion = make_conclusion(
        fact_ids=["missing-fact"],
        citations=[SourceCitation(source_id="missing-source", quote="不存在的引用")],
        candidate_ids=["missing-timing"],
    )
    result = validate_divination_conclusion(conclusion, sample_context)
    codes = [issue.code for issue in result.issues]
    assert "unknown_fact_id" in codes
    assert "unknown_source_id" in codes
    assert "unknown_timing_candidate" in codes


def test_format_for_correction_contains_all_messages(sample_context) -> None:
    conclusion = make_conclusion(fact_ids=["missing-fact"])
    result = validate_divination_conclusion(conclusion, sample_context)
    rendered = result.format_for_correction()
    assert "missing-fact" in rendered
    assert rendered.startswith("1. [unknown_fact_id]")
    assert result.correction_messages() == [issue.message for issue in result.issues]
