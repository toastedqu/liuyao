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
    Relative,
    UsefulGodChoice,
)


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
        rationale="模型依据用户所占之事与原文选择该六亲",
        source_ids=source_ids or (SOURCE_BY_RELATIVE[relative],),
    )


def analyze_with_relative(
    context: RuleContext,
    relative: Relative = Relative.WEALTH,
) -> object:
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


def test_three_harmony_requires_at_least_two_active_branches() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[0] = lines[0].model_copy(update={"branch": "子", "is_moving": True})
    lines[1] = lines[1].model_copy(
        update={"branch": "辰", "element": Element.EARTH, "is_moving": True}
    )
    lines[5] = lines[5].model_copy(update={"branch": "申"})
    context = base.model_copy(update={"lines": tuple(lines)})

    analysis = analyze_with_relative(context)

    harmony = next(fact for fact in analysis.facts if fact.type == "THREE_HARMONY")
    assert harmony.value == "水"
    assert harmony.evidence["active_branch_count"] >= 2


def test_six_harm_pair_is_not_used_as_predictive_evidence() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[0] = lines[0].model_copy(update={"is_moving": True})
    lines[1] = lines[1].model_copy(update={"branch": "未"})
    analysis = analyze_with_relative(base.model_copy(update={"lines": tuple(lines)}))

    assert all(fact.type != "LINE_HARM" for fact in analysis.facts)
    assert any("六害" in limitation for limitation in analysis.unimplemented_rules)


def test_unresolved_useful_god_is_explicit() -> None:
    context = context_for_wealth().model_copy(
        update={"question": "此事如何？"}
    )

    useful = RuleEngine().analyze(context).useful_god

    assert useful.status == "unresolved"
    assert "由模型" in useful.rationale[0]


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
def test_model_weather_decision_is_respected_by_rule_engine(
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
def test_model_relation_decision_is_respected(
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


def test_model_can_choose_one_target_from_conflicting_weather_text() -> None:
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


def test_equal_useful_god_candidates_remain_ambiguous_without_timing() -> None:
    base = context_for_wealth()
    lines = list(base.lines)
    lines[2] = lines[2].model_copy(update={"branch": "卯"})
    lines[4] = lines[4].model_copy(update={"is_moving": False, "changed": None})
    analysis = analyze_with_relative(base.model_copy(update={"lines": tuple(lines)}))

    assert analysis.useful_god.status == "multiple"
    assert analysis.useful_god.selected_line is None
    assert analysis.timing_candidates == ()


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
    analysis = analyze_with_relative(base.model_copy(update={"lines": tuple(lines)}))

    assert analysis.useful_god.candidates[0].role == "hidden"
    useful_fact = next(fact for fact in analysis.facts if fact.type == "USEFUL_GOD")
    assert useful_fact.line == 2
    assert useful_fact.evidence["role"] == "hidden"
    assert useful_fact.evidence["relative"] == "妻财"
    assert useful_fact.evidence["branch"] == "卯"
    assert useful_fact.rule_source == "008_用神章:p0006"


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
