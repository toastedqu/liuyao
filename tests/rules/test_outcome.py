from __future__ import annotations

from app.rules import ChangedLineContext, RuleEngine
from app.rules.models import (
    Element,
    OutcomeEvidenceDirection,
    OutcomeGuardrail,
    Relative,
)
from tests.rules.test_engine import context_for_wealth, relative_choice


def _analyze(context):
    return RuleEngine().analyze(context, relative_choice())


def _positive_context():
    base = context_for_wealth()
    lines = list(base.lines)
    lines[4] = lines[4].model_copy(
        update={
            "changed": ChangedLineContext(
                branch="亥",
                element=Element.WATER,
                relative=Relative.CHILD,
                is_yang=True,
            )
        }
    )
    return base.model_copy(
        update={
            "month_branch": "亥",
            "day_branch": "卯",
            "void_branches": ("辰", "巳"),
            "lines": tuple(lines),
        }
    )


def test_clear_support_produces_favorable_only_guardrail() -> None:
    outcome = _analyze(_positive_context()).outcome_analysis

    assert outcome.guardrail == OutcomeGuardrail.FAVORABLE_ONLY
    assert any(
        evidence.id.endswith("day-supports-useful")
        and evidence.direction == OutcomeEvidenceDirection.FAVORABLE
        for evidence in outcome.evidence
    )
    assert any(
        evidence.id.endswith("useful-return-generate")
        for evidence in outcome.evidence
    )


def test_two_present_candidates_each_enter_outcome_analysis() -> None:
    analysis = _analyze(context_for_wealth())
    evidence_ids = {item.id for item in analysis.outcome_analysis.evidence}

    assert analysis.useful_god.selected_line == 5
    assert [candidate.line for candidate in analysis.useful_god.candidates] == [5, 3]
    assert any(item.startswith("candidate-l5-") for item in evidence_ids)
    assert any(item.startswith("candidate-l3-") for item in evidence_ids)
    assert any(
        "旬空、月破候选仍可在填实时应验" in limitation
        for limitation in analysis.outcome_analysis.limitations
    )


def test_clear_harm_produces_adverse_only_guardrail() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[4] = lines[4].model_copy(
        update={
            "changed": ChangedLineContext(
                branch="申",
                element=Element.METAL,
                relative=Relative.SIBLING,
                is_yang=True,
            )
        }
    )
    outcome = _analyze(
        base.model_copy(
            update={
                "month_branch": "申",
                "day_branch": "申",
                "void_branches": ("辰", "巳"),
                "lines": tuple(lines),
            }
        )
    ).outcome_analysis

    assert outcome.guardrail == OutcomeGuardrail.ADVERSE_ONLY
    assert any(
        evidence.id.endswith("day-overcomes-useful")
        for evidence in outcome.evidence
    )
    assert any(
        evidence.id.endswith("useful-return-overcome")
        for evidence in outcome.evidence
    )


def test_unrooted_useful_god_is_not_rescued_by_quiet_generator() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[4] = lines[4].model_copy(
        update={
            "relative": Relative.PARENT,
            "is_moving": False,
            "changed": None,
        }
    )
    outcome = _analyze(
        base.model_copy(
            update={"day_branch": "酉", "lines": tuple(lines)}
        )
    ).outcome_analysis

    assert outcome.guardrail == OutcomeGuardrail.ADVERSE_ONLY
    assert any(item.id.endswith("useful-unrooted") for item in outcome.evidence)
    assert not any(
        "quiet-strong-generator" in item.id
        for item in outcome.evidence
    )


def test_unrooted_useful_god_is_not_rescued_by_harmony_generation() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[0] = lines[0].model_copy(update={"is_moving": True})
    lines[1] = lines[1].model_copy(
        update={"branch": "辰", "is_moving": True}
    )
    lines[4] = lines[4].model_copy(
        update={
            "relative": Relative.PARENT,
            "is_moving": False,
            "changed": None,
        }
    )
    lines[5] = lines[5].model_copy(update={"branch": "申"})
    outcome = _analyze(
        base.model_copy(
            update={
                "day_branch": "酉",
                "void_branches": ("戌", "亥"),
                "lines": tuple(lines),
            }
        )
    ).outcome_analysis

    assert outcome.guardrail == OutcomeGuardrail.ADVERSE_ONLY
    harmony = next(
        item
        for item in outcome.evidence
        if "effective-three-harmony-effect" in item.id
    )
    assert harmony.direction == OutcomeEvidenceDirection.CONTEXT


def test_moving_month_break_is_conditional_not_automatic_harm() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[2] = lines[2].model_copy(update={"relative": Relative.PARENT})
    lines[4] = lines[4].model_copy(
        update={
            "branch": "寅",
            "element": Element.WOOD,
            "changed": ChangedLineContext(
                branch="子",
                element=Element.WATER,
                relative=Relative.CHILD,
                is_yang=True,
            ),
        }
    )
    outcome = _analyze(
        base.model_copy(
            update={
                "month_branch": "申",
                "day_branch": "酉",
                "void_branches": ("辰", "巳"),
                "lines": tuple(lines),
            }
        )
    ).outcome_analysis

    assert any(
        evidence.id.endswith("useful-month-break-conditional")
        and evidence.direction == OutcomeEvidenceDirection.CONDITIONAL
        for evidence in outcome.evidence
    )
    assert all(
        evidence.id != "useful-static-month-break"
        for evidence in outcome.evidence
    )
    assert all(evidence.id != "useful-unrooted" for evidence in outcome.evidence)


def test_mere_taboo_presence_is_not_adverse_evidence() -> None:
    analysis = _analyze(_positive_context())

    assert any(fact.id == "fact-taboo-god-l6" for fact in analysis.facts)
    assert all(
        "fact-taboo-god-l6" not in evidence.fact_ids
        for evidence in analysis.outcome_analysis.evidence
    )


def test_origin_and_taboo_moving_together_diverts_attacker() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[2] = lines[2].model_copy(update={"branch": "卯"})
    lines[4] = lines[4].model_copy(
        update={
            "relative": Relative.PARENT,
            "is_moving": False,
            "changed": None,
        }
    )
    lines[0] = lines[0].model_copy(update={"is_moving": True, "changed": None})
    lines[5] = lines[5].model_copy(update={"is_moving": True, "changed": None})
    outcome = _analyze(
        base.model_copy(
            update={
                "month_branch": "亥",
                "day_branch": "卯",
                "void_branches": ("辰", "巳"),
                "lines": tuple(lines),
            }
        )
    ).outcome_analysis

    assert any(
        evidence.id.endswith("active-generator-l1")
        and evidence.direction == OutcomeEvidenceDirection.FAVORABLE
        for evidence in outcome.evidence
    )
    assert any(
        evidence.id.endswith("attacker-diverted-l6")
        and evidence.direction == OutcomeEvidenceDirection.CONDITIONAL
        for evidence in outcome.evidence
    )
    assert all(evidence.id != "active-attacker-l6" for evidence in outcome.evidence)


def test_weak_moving_taboo_hurt_by_month_and_day_is_not_effective() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[2] = lines[2].model_copy(update={"branch": "卯"})
    lines[4] = lines[4].model_copy(
        update={
            "relative": Relative.PARENT,
            "is_moving": False,
            "changed": None,
        }
    )
    lines[5] = lines[5].model_copy(update={"is_moving": True, "changed": None})
    outcome = _analyze(
        base.model_copy(
            update={
                "month_branch": "午",
                "day_branch": "巳",
                "void_branches": ("辰", "巳"),
                "lines": tuple(lines),
            }
        )
    ).outcome_analysis

    assert any(
        evidence.id.endswith("attacker-constrained-l6")
        and evidence.direction == OutcomeEvidenceDirection.CONDITIONAL
        for evidence in outcome.evidence
    )
    assert all(evidence.id != "active-attacker-l6" for evidence in outcome.evidence)


def test_unrooted_useful_god_blocks_generator_from_forcing_good() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[4] = lines[4].model_copy(
        update={
            "relative": Relative.PARENT,
            "is_moving": False,
            "changed": None,
        }
    )
    lines[0] = lines[0].model_copy(update={"is_moving": True, "changed": None})
    outcome = _analyze(
        base.model_copy(
            update={
                "month_branch": "申",
                "day_branch": "酉",
                "void_branches": ("辰", "巳"),
                "lines": tuple(lines),
            }
        )
    ).outcome_analysis

    assert outcome.guardrail == OutcomeGuardrail.ADVERSE_ONLY
    assert any(
        evidence.id.endswith("useful-unrooted")
        for evidence in outcome.evidence
    )
    assert any(
        evidence.id.endswith("generator-cannot-root-l1")
        and evidence.direction == OutcomeEvidenceDirection.CONDITIONAL
        for evidence in outcome.evidence
    )


def test_resting_useful_god_with_direct_support_is_not_forced_adverse() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[2] = lines[2].model_copy(update={"branch": "卯"})
    lines[4] = lines[4].model_copy(
        update={
            "relative": Relative.PARENT,
            "is_moving": False,
            "changed": None,
        }
    )
    lines[0] = lines[0].model_copy(update={"is_moving": True, "changed": None})
    outcome = _analyze(
        base.model_copy(
            update={
                "month_branch": "申",
                "day_branch": "亥",
                "void_branches": ("辰", "巳"),
                "lines": tuple(lines),
            }
        )
    ).outcome_analysis

    assert outcome.guardrail == OutcomeGuardrail.MIXED
    assert any(
        evidence.direction == OutcomeEvidenceDirection.FAVORABLE
        for evidence in outcome.evidence
    )
    assert any(
        evidence.id.endswith("useful-seasonally-weak")
        for evidence in outcome.evidence
    )
