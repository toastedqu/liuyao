from __future__ import annotations

import pytest

from app.rules import (
    ChangedLineContext,
    LineContext,
    RuleContext,
    RuleEngine,
)
from app.rules.models import (
    Element,
    HiddenSpiritContext,
    OutcomeEvidenceDirection,
    OutcomeEvidenceWeight,
    QuestionPerspective,
    Relative,
    RuleAnalysis,
    RuleStatus,
    UsefulGodChoice,
)
from app.rules.registry import get_rule


def context_for_wealth() -> RuleContext:
    return RuleContext(
        question="今年求财是否可成？",
        month_branch="申",
        day_stem="甲",
        day_branch="午",
        void_branches=("辰", "巳"),
        palace_element=Element.METAL,
        primary_hexagram="测试主卦",
        changed_hexagram="测试变卦",
        primary_is_six_clash=True,
        lines=(
            LineContext(
                position=1,
                branch="子",
                element=Element.WATER,
                relative=Relative.CHILD,
                is_yang=True,
                is_moving=False,
                is_world=True,
            ),
            LineContext(
                position=2,
                branch="丑",
                element=Element.EARTH,
                relative=Relative.PARENT,
                is_yang=False,
                is_moving=False,
            ),
            LineContext(
                position=3,
                branch="寅",
                element=Element.WOOD,
                relative=Relative.WEALTH,
                is_yang=True,
                is_moving=False,
            ),
            LineContext(
                position=4,
                branch="午",
                element=Element.FIRE,
                relative=Relative.OFFICIAL,
                is_yang=True,
                is_moving=False,
            ),
            LineContext(
                position=5,
                branch="卯",
                element=Element.WOOD,
                relative=Relative.WEALTH,
                is_yang=False,
                is_moving=True,
                changed=ChangedLineContext(
                    branch="酉",
                    element=Element.METAL,
                    relative=Relative.SIBLING,
                    is_yang=True,
                ),
            ),
            LineContext(
                position=6,
                branch="酉",
                element=Element.METAL,
                relative=Relative.SIBLING,
                is_yang=False,
                is_moving=False,
                is_response=True,
            ),
        ),
    )


SOURCE_BY_RELATIVE = {
    Relative.PARENT: "008_用神章:p0001",
    Relative.OFFICIAL: "008_用神章:p0002",
    Relative.SIBLING: "008_用神章:p0003",
    Relative.WEALTH: "008_用神章:p0006",
    Relative.CHILD: "008_用神章:p0007",
}


def relative_choice(
    relative: Relative = Relative.WEALTH,
    *,
    target: str = "所占之事",
    source_ids: tuple[str, ...] | None = None,
) -> UsefulGodChoice:
    return UsefulGodChoice(
        target=target,
        mode="relative",
        useful_relative=relative,
        rationale="用户选择该六亲",
        source_ids=source_ids or (SOURCE_BY_RELATIVE[relative],),
    )


def analyze_with_relative(
    context: RuleContext,
    relative: Relative = Relative.WEALTH,
) -> RuleAnalysis:
    return RuleEngine().analyze(context, relative_choice(relative))


def test_engine_selects_visible_useful_god_and_computes_gods() -> None:
    analysis = analyze_with_relative(context_for_wealth())

    assert analysis.useful_god.status == "selected"
    assert analysis.useful_god.useful_relative is Relative.WEALTH
    assert analysis.useful_god.selected_line == 5
    assert analysis.useful_god.useful_element is Element.WOOD
    assert analysis.useful_god.yuan_element is Element.WATER
    assert analysis.useful_god.taboo_element is Element.METAL
    assert analysis.useful_god.enemy_element is Element.EARTH
    assert analysis.useful_god.source_ids[0] == "008_用神章:p0006"
    assert "《两现章》古法" in analysis.useful_god.rationale[0]
    useful_fact = next(fact for fact in analysis.facts if fact.type == "USEFUL_GOD")
    assert useful_fact.rule_source == "008_用神章:p0006"


def test_engine_emits_auditable_strength_and_change_facts() -> None:
    analysis = analyze_with_relative(context_for_wealth())
    facts = {fact.id: fact for fact in analysis.facts}

    assert facts["fact-month-break-l3"].evidence == {
        "month_branch": "申",
        "line_branch": "寅",
        "moving": False,
    }
    assert facts["fact-dark-movement-l1"].type == "DARK_MOVEMENT"
    assert facts["fact-return-overcome-l5"].value is True
    assert facts["fact-return-clash-l5"].value is True
    assert facts["fact-primary-six-clash"].rule_source.startswith("022_")


def test_engine_limits_timing_to_generated_candidates() -> None:
    analysis = analyze_with_relative(context_for_wealth())

    candidates = {candidate.id: candidate for candidate in analysis.timing_candidates}
    moving = candidates["timing-moving-value-l5"]
    assert moving.branches == ("卯", "戌")
    assert moving.time_unit_hint == "月/年"
    assert moving.source_ids == ("032_各门类应期总注章:p0002",)


def test_model_world_choice_uses_world_line() -> None:
    context = context_for_wealth().model_copy(
        update={"question": "我近日疾病如何？"}
    )
    choice = UsefulGodChoice(
        target="我的疾病",
        mode="world",
        rationale="模型判定为问占者本人事项",
        source_ids=("031_各门类题头总注章:p0010",),
    )

    useful = RuleEngine().analyze(context, choice).useful_god

    assert useful.status == "selected"
    assert useful.selection_mode == "world"
    assert useful.candidates[0].role == "world"
    assert useful.selected_line == 1


def test_deterministic_response_choice_uses_response_line() -> None:
    choice = UsefulGodChoice(
        target="表兄弟",
        mode="response",
        rationale="原书明确表兄弟取应爻",
        source_ids=("008_用神章:p0005",),
    )

    useful = RuleEngine().analyze(context_for_wealth(), choice).useful_god

    assert useful.status == "selected"
    assert useful.selection_mode == "response"
    assert useful.candidates[0].role == "response"
    assert useful.selected_line == 6


def test_three_harmony_requires_at_least_two_active_branches() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[0] = lines[0].model_copy(update={"branch": "子", "is_moving": True})
    lines[1] = lines[1].model_copy(
        update={"branch": "辰", "element": Element.EARTH, "is_moving": True}
    )
    lines[5] = lines[5].model_copy(update={"branch": "申"})
    context = base.model_copy(
        update={"void_branches": ("戌", "亥"), "lines": tuple(lines)}
    )

    analysis = analyze_with_relative(context)

    harmony = next(fact for fact in analysis.facts if fact.type == "THREE_HARMONY")
    assert harmony.value == "水"
    assert harmony.evidence["active_branch_count"] >= 2


def test_three_harmony_can_be_completed_by_month_command() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[0] = lines[0].model_copy(update={"is_moving": True})
    lines[1] = lines[1].model_copy(
        update={"branch": "辰", "is_moving": True}
    )
    context = base.model_copy(
        update={"void_branches": ("戌", "亥"), "lines": tuple(lines)}
    )

    harmony = next(
        fact
        for fact in analyze_with_relative(context).facts
        if fact.type == "THREE_HARMONY" and fact.value == "水"
    )

    assert harmony.evidence["calendar_completion"] == "申"
    assert harmony.evidence["present_branches"] == ["子", "辰"]
    assert harmony.evidence["status"] == "formed"


def test_three_harmony_preserves_virtual_and_blocked_states() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[0] = lines[0].model_copy(update={"is_moving": True})
    lines[1] = lines[1].model_copy(
        update={"branch": "辰", "is_moving": True}
    )
    pending_context = base.model_copy(
        update={
            "month_branch": "午",
            "day_branch": "卯",
            "void_branches": ("戌", "亥"),
            "lines": tuple(lines),
        }
    )
    pending = next(
        fact
        for fact in analyze_with_relative(pending_context).facts
        if fact.type == "THREE_HARMONY_PENDING" and fact.value == "水"
    )
    assert pending.evidence["status"] == "virtual_pending"
    assert pending.evidence["missing_branch"] == "申"

    lines[5] = lines[5].model_copy(update={"branch": "申"})
    blocked_context = base.model_copy(update={"lines": tuple(lines)})
    blocked = next(
        fact
        for fact in analyze_with_relative(blocked_context).facts
        if fact.type == "THREE_HARMONY_PENDING" and fact.value == "水"
    )
    assert blocked.evidence["status"] == "blocked"
    assert "fact-void-l2" in blocked.evidence["blocker_fact_ids"]


def test_three_harmony_changed_line_requires_inner_or_outer_pair() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[0] = lines[0].model_copy(
        update={
            "branch": "寅",
            "element": Element.WOOD,
            "is_moving": True,
            "changed": ChangedLineContext(
                branch="午",
                element=Element.FIRE,
                relative=Relative.OFFICIAL,
                is_yang=False,
            ),
        }
    )
    lines[1] = lines[1].model_copy(
        update={
            "branch": "戌",
            "element": Element.EARTH,
            "is_moving": True,
        }
    )
    lines[3] = lines[3].model_copy(update={"branch": "巳"})
    invalid = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "卯",
                "day_branch": "酉",
                "void_branches": ("子", "丑"),
                "lines": tuple(lines),
            }
        )
    )
    assert not any(
        fact.type == "THREE_HARMONY" and fact.value == "火"
        for fact in invalid.facts
    )

    lines[1] = base.lines[1]
    lines[2] = lines[2].model_copy(
        update={
            "branch": "戌",
            "element": Element.EARTH,
            "relative": Relative.PARENT,
            "is_moving": True,
        }
    )
    valid = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "卯",
                "day_branch": "酉",
                "void_branches": ("子", "丑"),
                "lines": tuple(lines),
            }
        )
    )
    harmony = next(
        fact
        for fact in valid.facts
        if fact.type == "THREE_HARMONY" and fact.value == "火"
    )
    assert harmony.evidence["formation_mode"] == "inner_changed"
    assert harmony.related_lines == (1, 3)


def test_hexagram_change_relation_has_explicit_effect() -> None:
    context = context_for_wealth().model_copy(
        update={"changed_palace_element": Element.FIRE}
    )
    analysis = analyze_with_relative(context)
    by_type = {fact.type: fact for fact in analysis.facts}

    assert by_type["HEXAGRAM_CHANGE_RELATION"].value == "变来克我"
    assert (
        by_type["HEXAGRAM_CHANGE_EFFECT"].value
        == "adverse_overrides_useful_strength"
    )
    assert any(
        by_type["HEXAGRAM_CHANGE_EFFECT"].id in evidence.fact_ids
        for evidence in analysis.outcome_analysis.evidence
    )


def test_three_harmony_effect_follows_useful_god_not_unrelated_world() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[0] = lines[0].model_copy(
        update={"branch": "午", "element": Element.FIRE}
    )
    lines[1] = lines[1].model_copy(
        update={
            "branch": "子",
            "element": Element.WATER,
            "is_moving": True,
        }
    )
    lines[2] = lines[2].model_copy(
        update={
            "branch": "辰",
            "element": Element.EARTH,
            "relative": Relative.PARENT,
            "is_moving": True,
        }
    )
    lines[5] = lines[5].model_copy(update={"branch": "申"})
    analysis = analyze_with_relative(
        base.model_copy(
            update={"void_branches": ("戌", "亥"), "lines": tuple(lines)}
        )
    )
    effect = next(
        fact
        for fact in analysis.facts
        if fact.type == "THREE_HARMONY_EFFECT" and fact.value == "generates_useful"
    )

    assert effect.evidence["world_relation"] == "overcomes_world"
    assert effect.evidence["useful_element"] == "木"
    world_effect = next(
        fact
        for fact in analysis.facts
        if fact.type == "THREE_HARMONY_WORLD_EFFECT"
    )
    assert world_effect.value == "overcomes_world"
    assert analysis.outcome_analysis.guardrail.value == "正反证据并见"


def test_useful_god_in_harmony_is_detained_for_return_question() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[0] = lines[0].model_copy(
        update={
            "branch": "亥",
            "element": Element.WATER,
            "is_moving": True,
        }
    )
    lines[1] = lines[1].model_copy(
        update={"branch": "未", "is_moving": True}
    )
    analysis = analyze_with_relative(
        base.model_copy(
            update={
                "question": "妻子何时回来？",
                "void_branches": ("戌", "酉"),
                "lines": tuple(lines),
            }
        )
    )
    effect = next(
        fact
        for fact in analysis.facts
        if fact.type == "THREE_HARMONY_EFFECT"
        and fact.evidence["useful_line"] == analysis.useful_god.selected_line
    )

    assert effect.value == "useful_in_group_detained"
    assert any(
        effect.id in evidence.fact_ids
        and evidence.direction == OutcomeEvidenceDirection.ADVERSE
        for evidence in analysis.outcome_analysis.evidence
    )


def test_six_harm_pair_is_recorded_with_zero_predictive_weight() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[0] = lines[0].model_copy(update={"is_moving": True})
    lines[1] = lines[1].model_copy(update={"branch": "未"})
    analysis = analyze_with_relative(base.model_copy(update={"lines": tuple(lines)}))

    harm = next(fact for fact in analysis.facts if fact.type == "LINE_HARM")
    assert harm.evidence["predictive_weight"] == 0
    assert get_rule(harm.rule_id).status is RuleStatus.DISCARDED
    assert all(harm.id not in evidence.fact_ids for evidence in analysis.outcome_analysis.evidence)


def test_unresolved_useful_god_is_explicit() -> None:
    context = context_for_wealth().model_copy(
        update={"question": "此事如何？"}
    )

    useful = RuleEngine().analyze(context).useful_god

    assert useful.status == "unresolved"
    assert "用户明确选择用神" in useful.rationale[0]


def test_base_analysis_does_not_guess_a_useful_god_from_question_text() -> None:
    context = context_for_wealth().model_copy(
        update={"question": "行人何时回来？"}
    )

    useful = RuleEngine().analyze(context).useful_god

    assert useful.status == "unresolved"
    assert useful.selected_line is None


@pytest.mark.parametrize(
    ("question", "relative", "source_id", "weather_source_id"),
    [
        (
            "近日会下雨吗？",
            Relative.PARENT,
            "008_用神章:p0001",
            "041_天时章:p0003",
        ),
        (
            "近日能否放晴？",
            Relative.CHILD,
            "008_用神章:p0007",
            "041_天时章:p0002",
        ),
        (
            "今日会打雷吗？",
            Relative.OFFICIAL,
            "008_用神章:p0002",
            "041_天时章:p0005",
        ),
    ],
)
def test_user_weather_selection_is_respected_by_rule_engine(
    question: str,
    relative: Relative,
    source_id: str,
    weather_source_id: str,
) -> None:
    context = context_for_wealth().model_copy(
        update={"question": question}
    )
    choice = relative_choice(
        relative,
        target=question,
        source_ids=(source_id, weather_source_id),
    )

    useful = RuleEngine().analyze(context, choice).useful_god

    assert useful.useful_relative is relative
    assert useful.source_ids[0] == source_id
    assert weather_source_id in useful.source_ids


@pytest.mark.parametrize(
    ("question", "relative"),
    [
        ("我老婆何时回来？", Relative.WEALTH),
        ("我老公何时回来？", Relative.OFFICIAL),
        ("我妈妈的疾病如何？", Relative.PARENT),
        ("我哥哥的疾病如何？", Relative.SIBLING),
    ],
)
def test_user_relation_selection_is_respected(
    question: str,
    relative: Relative,
) -> None:
    context = context_for_wealth().model_copy(
        update={"question": question}
    )

    analysis = RuleEngine().analyze(
        context,
        relative_choice(relative, target=question),
    )
    assert analysis.useful_god.useful_relative is relative


def test_user_can_choose_one_target_from_conflicting_weather_text() -> None:
    context = context_for_wealth().model_copy(
        update={"question": "何时停雨放晴？"}
    )

    useful = RuleEngine().analyze(
        context,
        relative_choice(
            Relative.CHILD,
            target="放晴",
            source_ids=("041_天时章:p0002",),
        ),
    ).useful_god

    assert useful.status == "selected"
    assert useful.useful_relative is Relative.CHILD


def test_equal_useful_god_candidates_remain_ambiguous_with_separate_timing() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[2] = lines[2].model_copy(update={"branch": "卯"})
    lines[4] = lines[4].model_copy(update={"is_moving": False, "changed": None})
    analysis = RuleEngine().analyze(
        base.model_copy(update={"lines": tuple(lines)}),
        relative_choice(),
    )

    assert analysis.useful_god.status == "multiple"
    assert analysis.useful_god.selected_line is None
    assert {
        "timing-two-present-l3",
        "timing-two-present-l5",
    }.issubset(
        {candidate.id for candidate in analysis.timing_candidates}
    )


def test_hidden_useful_god_fact_uses_hidden_spirit_not_flying_line() -> None:
    base = context_for_wealth()
    lines = [
        line.model_copy(
            update={
                "relative": Relative.PARENT
                if line.relative is Relative.WEALTH
                else line.relative
            }
        )
        for line in base.lines
    ]
    lines[1] = lines[1].model_copy(
        update={
            "hidden_spirit": HiddenSpiritContext(
                stem="乙",
                branch="卯",
                element=Element.WOOD,
                relative=Relative.WEALTH,
            )
        }
    )
    analysis = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "亥",
                "day_branch": "子",
                "lines": tuple(lines),
            }
        )
    )

    assert analysis.useful_god.candidates[0].role == "hidden"
    useful_fact = next(fact for fact in analysis.facts if fact.type == "USEFUL_GOD")
    assert useful_fact.line == 2
    assert useful_fact.evidence["role"] == "hidden"
    assert useful_fact.evidence["relative"] == "妻财"
    assert useful_fact.evidence["branch"] == "卯"
    assert useful_fact.rule_source == "008_用神章:p0006"
    static_timing = next(
        candidate
        for candidate in analysis.timing_candidates
        if candidate.id == "timing-static-value-l2"
    )
    assert static_timing.branches == ("卯", "酉")
    hidden_effect = next(
        fact
        for fact in analysis.facts
        if fact.type == "HIDDEN_SPIRIT_EFFECT"
    )
    assert hidden_effect.value == "useful"
    assert hidden_effect.source_ids == (
        "035_飞伏神章:p0010",
        "035_飞伏神章:p0014",
    )


def test_absent_useful_god_uses_month_before_hidden_spirit() -> None:
    base = context_for_wealth()
    lines = [
        line.model_copy(
            update={
                "relative": Relative.PARENT
                if line.relative is Relative.WEALTH
                else line.relative
            }
        )
        for line in base.lines
    ]
    lines[1] = lines[1].model_copy(
        update={
            "hidden_spirit": HiddenSpiritContext(
                stem="乙",
                branch="卯",
                element=Element.WOOD,
                relative=Relative.WEALTH,
            )
        }
    )
    analysis = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "卯",
                "lines": tuple(lines),
            }
        )
    )

    assert analysis.useful_god.status == "selected"
    assert analysis.useful_god.selected_line is None
    assert analysis.useful_god.candidates == ()
    assert analysis.useful_god.useful_element is Element.WOOD
    assert "先以月建为用" in analysis.useful_god.rationale[-1]


def test_changed_useful_god_is_selected_before_hidden_spirit() -> None:
    base = context_for_wealth()
    lines = [
        line.model_copy(
            update={
                "relative": Relative.PARENT
                if line.relative is Relative.WEALTH
                else line.relative
            }
        )
        for line in base.lines
    ]
    lines[4] = lines[4].model_copy(
        update={
            "changed": ChangedLineContext(
                branch="卯",
                element=Element.WOOD,
                relative=Relative.WEALTH,
                is_yang=True,
            ),
            "hidden_spirit": HiddenSpiritContext(
                stem="乙",
                branch="寅",
                element=Element.WOOD,
                relative=Relative.WEALTH,
            ),
        }
    )
    analysis = analyze_with_relative(
        base.model_copy(update={"lines": tuple(lines)})
    )

    assert analysis.useful_god.status == "selected"
    assert analysis.useful_god.selected_line == 5
    assert analysis.useful_god.candidates[0].role == "changed"
    assert analysis.useful_god.candidates[0].branch == "卯"
    assert "先取变爻" in analysis.useful_god.rationale[0]
    assert not any(
        "用神只现于变爻" in limitation
        for limitation in analysis.outcome_analysis.limitations
    )
    assert any(
        "fact-changed-strength-l5" in evidence.fact_ids
        for evidence in analysis.outcome_analysis.evidence
    )
    assert any(
        candidate.id == "timing-moving-value-l5"
        for candidate in analysis.timing_candidates
    )


def test_changed_useful_god_does_not_consume_original_line_tomb_effect() -> None:
    base = context_for_wealth()
    lines = [
        line.model_copy(
            update={
                "relative": Relative.PARENT
                if line.relative is Relative.WEALTH
                else line.relative
            }
        )
        for line in base.lines
    ]
    lines[4] = lines[4].model_copy(
        update={
            "branch": "子",
            "element": Element.WATER,
            "relative": Relative.PARENT,
            "changed": ChangedLineContext(
                branch="卯",
                element=Element.WOOD,
                relative=Relative.WEALTH,
                is_yang=True,
            ),
        }
    )
    analysis = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "午",
                "day_branch": "辰",
                "lines": tuple(lines),
            }
        )
    )

    assert analysis.useful_god.candidates[0].role == "changed"
    assert any(
        fact.id == "fact-life-stage-effect-墓-l5"
        for fact in analysis.facts
    )
    assert all(
        "fact-life-stage-effect-墓-l5" not in evidence.fact_ids
        for evidence in analysis.outcome_analysis.evidence
    )


def test_changed_official_useful_god_is_not_misread_as_useful_changing_to_ghost() -> None:
    base = context_for_wealth()
    lines = [
        line.model_copy(
            update={
                "relative": Relative.PARENT
                if line.relative is Relative.OFFICIAL
                else line.relative
            }
        )
        for line in base.lines
    ]
    lines[4] = lines[4].model_copy(
        update={
            "changed": ChangedLineContext(
                branch="巳",
                element=Element.FIRE,
                relative=Relative.OFFICIAL,
                is_yang=True,
            )
        }
    )
    analysis = analyze_with_relative(
        base.model_copy(
            update={
                "day_branch": "亥",
                "lines": tuple(lines),
            }
        ),
        Relative.OFFICIAL,
    )
    effect = next(
        fact
        for fact in analysis.facts
        if fact.type == "CHANGED_TO_OFFICIAL_EFFECT"
    )

    assert analysis.useful_god.candidates[0].role == "changed"
    assert effect.value == "context_only"


def test_equal_hidden_candidates_do_not_require_a_user_selected_line() -> None:
    base = context_for_wealth()
    lines = [
        line.model_copy(
            update={
                "relative": Relative.PARENT
                if line.relative is Relative.WEALTH
                else line.relative
            }
        )
        for line in base.lines
    ]
    for index in (1, 3):
        lines[index] = lines[index].model_copy(
            update={
                "hidden_spirit": HiddenSpiritContext(
                    stem="乙",
                    branch="卯",
                    element=Element.WOOD,
                    relative=Relative.WEALTH,
                )
            }
        )
    analysis = RuleEngine().analyze(
        base.model_copy(update={"lines": tuple(lines)}),
        relative_choice(),
    )

    assert analysis.useful_god.status == "multiple"
    assert analysis.useful_god.selected_line is None
    assert [candidate.line for candidate in analysis.useful_god.candidates] == [
        2,
        4,
    ]
    assert {
        "timing-two-present-l2",
        "timing-two-present-l4",
    }.issubset(
        {candidate.id for candidate in analysis.timing_candidates}
    )


def test_day_generation_gives_seasonally_weak_hidden_spirit_qi() -> None:
    base = context_for_wealth()
    lines = [
        line.model_copy(
            update={
                "relative": Relative.PARENT
                if line.relative is Relative.WEALTH
                else line.relative
            }
        )
        for line in base.lines
    ]
    lines[1] = lines[1].model_copy(
        update={
            "hidden_spirit": HiddenSpiritContext(
                stem="乙",
                branch="卯",
                element=Element.WOOD,
                relative=Relative.WEALTH,
            )
        }
    )
    analysis = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "午",
                "day_branch": "亥",
                "lines": tuple(lines),
            }
        )
    )
    strength = next(
        fact
        for fact in analysis.facts
        if fact.type == "HIDDEN_SEASONAL_STRENGTH"
    )
    effect = next(
        fact
        for fact in analysis.facts
        if fact.type == "HIDDEN_SPIRIT_EFFECT"
    )

    assert strength.value == "休囚"
    assert effect.value == "useful"
    assert effect.evidence["hidden_has_direct_support"] is True


def test_mapping_source_order_does_not_break_useful_fact() -> None:
    choice = relative_choice(
        source_ids=(
            "039_两现章:p0001",
            "008_用神章:p0006",
        )
    )
    analysis = RuleEngine().analyze(context_for_wealth(), choice)
    useful_fact = next(
        fact for fact in analysis.facts if fact.type == "USEFUL_GOD"
    )

    assert useful_fact.rule_source == "008_用神章:p0006"


def test_void_and_month_break_have_effective_states() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[3] = lines[3].model_copy(update={"branch": "巳", "is_moving": True})
    analysis = analyze_with_relative(base.model_copy(update={"lines": tuple(lines)}))
    by_id = {fact.id: fact for fact in analysis.facts}

    assert by_id["fact-void-effect-l4"].value == "nominal_only_moving"
    assert by_id["fact-month-break-effect-l3"].value == "inactive_static"


def test_true_void_does_not_override_moving_or_day_support() -> None:
    base = context_for_wealth().model_copy(
        update={"void_branches": ("寅", "卯")}
    )
    moving = analyze_with_relative(base)
    assert next(
        fact
        for fact in moving.facts
        if fact.type == "VOID_EFFECT" and fact.line == 5
    ).value == "nominal_only_moving"

    lines = list(base.lines)
    lines[4] = lines[4].model_copy(update={"is_moving": False, "changed": None})
    supported = analyze_with_relative(
        base.model_copy(
            update={"day_branch": "亥", "lines": tuple(lines)}
        )
    )
    effect = next(
        fact
        for fact in supported.facts
        if fact.type == "VOID_EFFECT" and fact.line == 5
    )
    assert effect.value == "nominal_only_supported"
    assert effect.evidence["true_void"] is True


def test_day_clashed_moving_line_is_not_mechanically_scattered() -> None:
    weak = analyze_with_relative(
        context_for_wealth().model_copy(update={"day_branch": "酉"})
    )
    weak_effect = next(
        fact
        for fact in weak.facts
        if fact.type == "MOVING_DAY_CLASH_EFFECT" and fact.line == 5
    )
    assert weak_effect.value == "conditional_possible_scatter"

    strong = analyze_with_relative(
        context_for_wealth().model_copy(
            update={"month_branch": "卯", "day_branch": "酉"}
        )
    )
    strong_effect = next(
        fact
        for fact in strong.facts
        if fact.type == "MOVING_DAY_CLASH_EFFECT" and fact.line == 5
    )
    assert strong_effect.value == "not_scattered"


def test_changed_void_break_and_tomb_are_evaluated() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[4] = lines[4].model_copy(
        update={
            "changed": ChangedLineContext(
                branch="巳",
                element=Element.FIRE,
                relative=Relative.OFFICIAL,
                is_yang=True,
            )
        }
    )
    changed_void = analyze_with_relative(
        base.model_copy(
            update={"day_branch": "子", "lines": tuple(lines)}
        )
    )
    assert next(
        fact
        for fact in changed_void.facts
        if fact.type == "CHANGED_VOID_EFFECT"
    ).value == "nominal_only_transformation"
    assert any(
        candidate.id == "timing-changed-void-fill-l5"
        for candidate in changed_void.timing_candidates
    )

    lines[4] = lines[4].model_copy(
        update={
            "changed": ChangedLineContext(
                branch="寅",
                element=Element.WOOD,
                relative=Relative.WEALTH,
                is_yang=True,
            )
        }
    )
    changed_break = analyze_with_relative(
        base.model_copy(update={"lines": tuple(lines)})
    )
    assert next(
        fact
        for fact in changed_break.facts
        if fact.type == "CHANGED_MONTH_BREAK_EFFECT"
    ).value == "effective_transformation"
    assert any(
        candidate.id == "timing-changed-break-fill-l5"
        for candidate in changed_break.timing_candidates
    )

    lines[4] = lines[4].model_copy(
        update={
            "changed": ChangedLineContext(
                branch="未",
                element=Element.EARTH,
                relative=Relative.PARENT,
                is_yang=False,
            )
        }
    )
    changed_tomb = analyze_with_relative(
        base.model_copy(update={"lines": tuple(lines)})
    )
    tomb_effect = next(
        fact
        for fact in changed_tomb.facts
        if fact.type == "CHANGED_LIFE_STAGE_EFFECT"
        and fact.evidence["basis"] == "original_line_element"
    )
    assert tomb_effect.value == "effective_adverse"


def test_moving_tomb_is_evaluated_against_target_strength() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[1] = lines[1].model_copy(
        update={"branch": "未", "is_moving": True}
    )
    analysis = analyze_with_relative(
        base.model_copy(update={"lines": tuple(lines)})
    )
    effect = next(
        fact
        for fact in analysis.facts
        if fact.type == "DYNAMIC_LIFE_STAGE_EFFECT"
        and fact.line == 5
        and fact.value == "effective_adverse"
    )

    assert effect.related_lines == (2,)
    assert effect.evidence["stage"] == "墓"


def test_advance_effect_depends_on_the_lines_god_role() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[2] = lines[2].model_copy(
        update={
            "relative": Relative.OFFICIAL,
            "is_moving": True,
            "changed": ChangedLineContext(
                branch="卯",
                element=Element.WOOD,
                relative=Relative.OFFICIAL,
                is_yang=False,
            ),
        }
    )
    lines[3] = lines[3].model_copy(update={"relative": Relative.PARENT})
    analysis = analyze_with_relative(
        base.model_copy(update={"lines": tuple(lines)}),
        Relative.OFFICIAL,
    )
    advance = next(
        fact for fact in analysis.facts if fact.type == "ADVANCE_EFFECT"
    )

    assert advance.value == "favorable"
    assert advance.evidence["role"] == "useful"


def test_ghost_tomb_requires_weak_unsupported_official_useful_god() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[4] = lines[4].model_copy(update={"is_moving": False, "changed": None})
    context = base.model_copy(
        update={
            "month_branch": "亥",
            "day_branch": "戌",
            "perspective": QuestionPerspective.PROXY,
            "lines": tuple(lines),
        }
    )
    analysis = analyze_with_relative(context, Relative.OFFICIAL)
    ghost_tomb = next(
        fact for fact in analysis.facts if fact.type == "GHOST_TOMB"
    )

    assert ghost_tomb.value == "adverse_real_tomb"
    assert ghost_tomb.evidence["modes"] == ["day_tomb"]


def test_proxy_divination_checks_useful_god_tomb() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[4] = lines[4].model_copy(update={"is_moving": False, "changed": None})
    analysis = analyze_with_relative(
        base.model_copy(
            update={
                "day_branch": "未",
                "perspective": QuestionPerspective.PROXY,
                "lines": tuple(lines),
            }
        )
    )
    ghost_tomb = next(
        fact for fact in analysis.facts if fact.type == "GHOST_TOMB"
    )

    assert ghost_tomb.value == "adverse_real_tomb"
    assert ghost_tomb.evidence["tomb_branch"] == "未"
    assert ghost_tomb.evidence["target_role"] == "visible"
    assert ghost_tomb.evidence["perspective"] == "proxy"


def test_tomb_without_weakness_and_actual_harm_is_only_conditional() -> None:
    base = context_for_wealth()
    analysis = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "午",
                "day_branch": "未",
                "perspective": QuestionPerspective.PROXY,
            }
        )
    )
    ghost_tomb = next(
        fact for fact in analysis.facts if fact.type == "GHOST_TOMB"
    )

    assert ghost_tomb.evidence["target_weak"] is True
    assert ghost_tomb.evidence["target_harmed"] is False
    assert ghost_tomb.value == "conditional_opened_or_supported"


def test_self_divination_checks_world_tomb_instead_of_selected_relative() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[4] = lines[4].model_copy(update={"is_moving": False, "changed": None})
    analysis = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "午",
                "day_branch": "辰",
                "perspective": QuestionPerspective.SELF,
                "lines": tuple(lines),
            }
        )
    )
    ghost_tomb = next(
        fact for fact in analysis.facts if fact.type == "GHOST_TOMB"
    )

    assert ghost_tomb.line == 1
    assert ghost_tomb.evidence["tomb_branch"] == "辰"
    assert ghost_tomb.evidence["target_role"] == "world"
    assert ghost_tomb.evidence["perspective"] == "self"


def test_six_god_only_amplifies_an_existing_matching_direction() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[2] = lines[2].model_copy(update={"relative": Relative.PARENT})
    lines[4] = lines[4].model_copy(
        update={
            "spirit": "白虎",
            "changed": ChangedLineContext(
                branch="亥",
                element=Element.WATER,
                relative=Relative.CHILD,
                is_yang=True,
            ),
        }
    )
    favorable = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "亥",
                "day_branch": "卯",
                "void_branches": ("辰", "巳"),
                "lines": tuple(lines),
            }
        )
    )

    assert any(
        fact.type == "SIX_GOD" and fact.line == 5 and fact.value == "白虎"
        for fact in favorable.facts
    )
    assert not any(
        evidence.id == "six-god-白虎-l5"
        for evidence in favorable.outcome_analysis.evidence
    )

    lines[4] = lines[4].model_copy(
        update={
            "spirit": "青龙",
            "changed": ChangedLineContext(
                branch="申",
                element=Element.METAL,
                relative=Relative.SIBLING,
                is_yang=True,
            ),
        }
    )
    adverse = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "申",
                "day_branch": "申",
                "void_branches": ("辰", "巳"),
                "lines": tuple(lines),
            }
        )
    )
    assert not any(
        evidence.id == "six-god-青龙-l5"
        for evidence in adverse.outcome_analysis.evidence
    )


def test_combine_with_overcoming_without_support_is_treated_as_overcoming() -> None:
    base = context_for_wealth()
    unsupported = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "丑",
                "day_branch": "辰",
            }
        ),
        Relative.CHILD,
    )
    combine = next(
        fact
        for fact in unsupported.facts
        if fact.type == "MONTH_COMBINE" and fact.line == 1
    )

    assert combine.evidence["effect"] == "言克不言合"
    assert combine.rule_source == "020_六合章:p0026"
    assert any(
        evidence.id == "useful-month-combine"
        and evidence.direction == OutcomeEvidenceDirection.ADVERSE
        for evidence in unsupported.outcome_analysis.evidence
    )

    lines = list(base.lines)
    lines[5] = lines[5].model_copy(update={"is_moving": True})
    supported = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "丑",
                "day_branch": "辰",
                "lines": tuple(lines),
            }
        ),
        Relative.CHILD,
    )
    supported_combine = next(
        fact
        for fact in supported.facts
        if fact.type == "MONTH_COMBINE" and fact.line == 1
    )
    assert supported_combine.evidence["effect"] == "合起"


def test_litigation_reverses_useful_god_combine_direction() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[2] = lines[2].model_copy(update={"relative": Relative.PARENT})
    lines[4] = lines[4].model_copy(update={"is_moving": False, "changed": None})
    litigation = analyze_with_relative(
        base.model_copy(
            update={
                "category": "诉讼",
                "day_branch": "戌",
                "lines": tuple(lines),
            }
        )
    )
    ordinary = analyze_with_relative(
        base.model_copy(
            update={
                "category": "求财",
                "day_branch": "戌",
                "lines": tuple(lines),
            }
        )
    )

    assert any(
        evidence.id == "useful-day-combine"
        and evidence.direction == OutcomeEvidenceDirection.ADVERSE
        for evidence in litigation.outcome_analysis.evidence
    )
    assert any(
        evidence.id == "useful-day-combine"
        and evidence.direction == OutcomeEvidenceDirection.FAVORABLE
        for evidence in ordinary.outcome_analysis.evidence
    )


def test_six_clash_changing_to_harmony_is_primary_evidence_with_category_exception() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[2] = lines[2].model_copy(update={"relative": Relative.PARENT})
    ordinary = analyze_with_relative(
        base.model_copy(
            update={
                "category": "求财",
                "changed_is_six_harmony": True,
                "lines": tuple(lines),
            }
        )
    )
    litigation = analyze_with_relative(
        base.model_copy(
            update={
                "category": "诉讼",
                "changed_is_six_harmony": True,
                "lines": tuple(lines),
            }
        )
    )

    assert any(fact.type == "CLASH_TO_HARMONY" for fact in ordinary.facts)
    ordinary_evidence = next(
        evidence
        for evidence in ordinary.outcome_analysis.evidence
        if evidence.id == "clash-to-harmony"
    )
    litigation_evidence = next(
        evidence
        for evidence in litigation.outcome_analysis.evidence
        if evidence.id == "clash-to-harmony"
    )
    assert ordinary_evidence.direction == OutcomeEvidenceDirection.FAVORABLE
    assert ordinary_evidence.weight == OutcomeEvidenceWeight.PRIMARY
    assert litigation_evidence.direction == OutcomeEvidenceDirection.ADVERSE


def test_verified_star_is_only_supporting_when_useful_god_is_supported() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[4] = lines[4].model_copy(update={"relative": Relative.PARENT})
    strong = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "寅",
                "lines": tuple(lines),
            }
        )
    )
    star = next(
        fact
        for fact in strong.facts
        if fact.type == "STAR_LU" and fact.line == 3
    )
    star_evidence = next(
        evidence
        for evidence in strong.outcome_analysis.evidence
        if evidence.id == "useful-star-lu"
    )

    assert star.value == "禄神"
    assert star_evidence.direction == OutcomeEvidenceDirection.FAVORABLE
    assert star_evidence.weight == OutcomeEvidenceWeight.SUPPORTING

    weak = analyze_with_relative(
        base.model_copy(
            update={
                "month_branch": "申",
                "day_branch": "巳",
                "lines": tuple(lines),
            }
        )
    )
    assert any(
        fact.type == "STAR_LU" and fact.line == 3
        for fact in weak.facts
    )
    assert not any(
        evidence.id == "useful-star-lu"
        for evidence in weak.outcome_analysis.evidence
    )


def test_year_command_is_context_and_unsupported_doctrines_are_disclosed() -> None:
    analysis = analyze_with_relative(
        context_for_wealth().model_copy(update={"year_branch": "午"})
    )
    year = next(fact for fact in analysis.facts if fact.type == "YEAR_COMMAND")

    assert year.value == "午"
    assert year.evidence["predictive_weight"] == 0
    assert any("卦化墓、卦化绝" in item for item in analysis.unimplemented_rules)
    assert any("太岁作用力" in item for item in analysis.unimplemented_rules)


def test_changed_to_official_is_role_and_generation_aware() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[4] = lines[4].model_copy(
        update={
            "changed": ChangedLineContext(
                branch="巳",
                element=Element.FIRE,
                relative=Relative.OFFICIAL,
                is_yang=True,
            )
        }
    )
    adverse = analyze_with_relative(
        base.model_copy(update={"lines": tuple(lines)})
    )
    assert next(
        fact
        for fact in adverse.facts
        if fact.type == "CHANGED_TO_OFFICIAL_EFFECT"
    ).value == "adverse_changed_to_official"

    lines = list(base.lines)
    lines[1] = lines[1].model_copy(
        update={
            "is_moving": True,
            "changed": ChangedLineContext(
                branch="午",
                element=Element.FIRE,
                relative=Relative.OFFICIAL,
                is_yang=True,
            ),
        }
    )
    generated = analyze_with_relative(
        base.model_copy(update={"lines": tuple(lines)}),
        Relative.PARENT,
    )
    effect = next(
        fact
        for fact in generated.facts
        if fact.type == "CHANGED_TO_OFFICIAL_EFFECT"
    )
    assert effect.value == "conflict_with_return_generation"
    assert effect.evidence["return_generation_fact_id"] == (
        "fact-return-generate-l2"
    )


def test_reverse_and_repeated_chant_generate_role_aware_effects() -> None:
    base = context_for_wealth()
    reverse_lines = list(base.lines)
    for index, branch, element in (
        (0, "午", Element.FIRE),
        (1, "未", Element.EARTH),
        (2, "申", Element.METAL),
    ):
        line = reverse_lines[index]
        reverse_lines[index] = line.model_copy(
            update={
                "is_moving": True,
                "changed": ChangedLineContext(
                    branch=branch,
                    element=element,
                    relative=line.relative,
                    is_yang=not line.is_yang,
                ),
            }
        )
    reverse = analyze_with_relative(
        base.model_copy(update={"lines": tuple(reverse_lines)})
    )
    assert next(
        fact for fact in reverse.facts if fact.type == "REVERSE_CHANT_EFFECT"
    ).value == "adverse_return_harm"

    repeated_lines = list(base.lines)
    for index in range(3):
        line = repeated_lines[index]
        repeated_lines[index] = line.model_copy(
            update={
                "is_moving": True,
                "changed": ChangedLineContext(
                    branch=line.branch,
                    element=line.element,
                    relative=line.relative,
                    is_yang=not line.is_yang,
                ),
            }
        )
    repeated = analyze_with_relative(
        base.model_copy(update={"lines": tuple(repeated_lines)})
    )
    assert next(
        fact
        for fact in repeated.facts
        if fact.type == "REPEATED_CHANT_EFFECT"
    ).value == "adverse_stagnation"
    assert any(
        candidate.id == "timing-open-repeated-chant-l5"
        for candidate in repeated.timing_candidates
    )
    repeated_timing = {
        candidate.id: candidate
        for candidate in repeated.timing_candidates
        if candidate.id.startswith("timing-open-repeated-chant-")
    }
    assert repeated_timing["timing-open-repeated-chant-l3"].fact_ids == (
        "fact-repeated-chant-effect-l3",
    )
    assert repeated_timing["timing-open-repeated-chant-l5"].fact_ids == (
        "fact-repeated-chant-effect-l5",
    )


def test_earth_month_does_not_mark_month_break_as_strong() -> None:
    context = context_for_wealth()
    lines = list(context.lines)
    lines[0] = lines[0].model_copy(
        update={
            "branch": "戌",
            "element": Element.EARTH,
            "relative": Relative.PARENT,
        }
    )
    context = context.model_copy(
        update={"month_branch": "辰", "lines": tuple(lines)}
    )

    facts = analyze_with_relative(context).facts
    by_id = {fact.id: fact for fact in facts}

    assert by_id["fact-strength-l1"].value == "休囚"
    assert by_id["fact-month-break-l1"].value is True
