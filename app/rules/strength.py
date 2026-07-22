from __future__ import annotations

from app.rules.elements import (
    BRANCH_ELEMENT,
    CLASH,
    COMBINE,
    EXTINCTION,
    GENERATES,
    GROWTH,
    OVERCOMES,
    PROSPERITY,
    TOMB,
    generates,
    overcomes,
)
from app.rules.models import Element, LineContext, RuleContext, RuleFact
from app.rules.registry import make_fact


SEASONAL_RESIDUAL: dict[str, Element] = {
    "辰": Element.WOOD,
    "未": Element.FIRE,
    "丑": Element.WATER,
}
EARTH_MONTH_STRONG_BRANCHES: dict[str, frozenset[str]] = {
    "辰": frozenset(("辰", "丑", "未")),
    "未": frozenset(("未", "辰", "戌")),
    "戌": frozenset(("戌", "丑", "未")),
    "丑": frozenset(("丑", "辰", "戌")),
}
SEASONAL_SOURCE_BY_MONTH = {
    "寅": "016_四时旺相章:p0001",
    "卯": "016_四时旺相章:p0001",
    "辰": "016_四时旺相章:p0002",
    "巳": "016_四时旺相章:p0003",
    "午": "016_四时旺相章:p0003",
    "未": "016_四时旺相章:p0004",
    "申": "016_四时旺相章:p0005",
    "酉": "016_四时旺相章:p0005",
    "戌": "016_四时旺相章:p0006",
    "亥": "016_四时旺相章:p0007",
    "子": "016_四时旺相章:p0007",
    "丑": "016_四时旺相章:p0008",
}


def seasonal_strength(line: LineContext, month_branch: str) -> str:
    return seasonal_strength_for(line.branch, line.element, month_branch)


def seasonal_strength_for(
    branch: str,
    element: Element,
    month_branch: str,
) -> str:
    month_element = BRANCH_ELEMENT[month_branch]
    if branch == month_branch:
        return "月建"
    if month_branch in EARTH_MONTH_STRONG_BRANCHES:
        if branch in EARTH_MONTH_STRONG_BRANCHES[month_branch]:
            return "旺"
        if SEASONAL_RESIDUAL.get(month_branch) is element:
            return "余气"
        if GENERATES[month_element] is element:
            return "相"
        return "休囚"
    if element is month_element:
        return "旺"
    if GENERATES[month_element] is element:
        return "相"
    return "休囚"


def _day_relation(element: Element, day_element: Element) -> str:
    if generates(day_element, element):
        return "日辰生爻"
    if overcomes(day_element, element):
        return "日辰克爻"
    if overcomes(element, day_element):
        return "爻克日辰"
    if generates(element, day_element):
        return "爻生日辰"
    return "比扶"


def _life_stage(element: Element, branch: str) -> str | None:
    stages = {
        "长生": GROWTH[element],
        "帝旺": PROSPERITY[element],
        "墓": TOMB[element],
        "绝": EXTINCTION[element],
    }
    return next((name for name, stage_branch in stages.items() if stage_branch == branch), None)


def _combine_effect(
    context: RuleContext,
    line: LineContext,
    *,
    partner_branch: str,
    scope: str,
    strength_level: str,
) -> tuple[str, bool]:
    default = "合绊" if line.is_moving else "合起"
    partner_element = BRANCH_ELEMENT[partner_branch]
    if not overcomes(partner_element, line.element):
        return default, False

    moving_support = any(
        actor.position != line.position
        and actor.is_moving
        and generates(actor.element, line.element)
        for actor in context.lines
    )
    return_support = (
        line.changed is not None
        and generates(line.changed.element, line.element)
    )
    if scope == "month":
        other_calendar = BRANCH_ELEMENT[context.day_branch]
        calendar_support = (
            other_calendar is line.element
            or generates(other_calendar, line.element)
        )
    else:
        calendar_support = strength_level in {"月建", "旺", "相", "余气"}
    if moving_support or return_support or calendar_support:
        return default, False
    return "言克不言合", True


def strength_facts(context: RuleContext) -> list[RuleFact]:
    facts: list[RuleFact] = []
    month_element = BRANCH_ELEMENT[context.month_branch]
    day_element = BRANCH_ELEMENT[context.day_branch]

    for line in context.lines:
        level = seasonal_strength(line, context.month_branch)
        facts.append(
            make_fact(
                "ZSBY-016-SEASONAL-STRENGTH",
                id=f"fact-strength-l{line.position}",
                type="SEASONAL_STRENGTH",
                line=line.position,
                value=level,
                evidence={
                    "month_branch": context.month_branch,
                    "month_element": month_element.value,
                    "line_branch": line.branch,
                    "line_element": line.element.value,
                },
                source_id=SEASONAL_SOURCE_BY_MONTH[context.month_branch],
            )
        )

        if line.branch in context.void_branches:
            facts.append(
                make_fact(
                    "ZSBY-029-VOID",
                    id=f"fact-void-l{line.position}",
                    type="旬空",
                    line=line.position,
                    value=True,
                    evidence={
                        "branch": line.branch,
                        "void_branches": list(context.void_branches),
                        "moving": line.is_moving,
                    },
                    source_id="029_旬空章:p0003",
                )
            )

        if CLASH[context.month_branch] == line.branch:
            facts.append(
                make_fact(
                    "ZSBY-034-MONTH-BREAK",
                    id=f"fact-month-break-l{line.position}",
                    type="MONTH_BREAK",
                    line=line.position,
                    value=True,
                    evidence={
                        "month_branch": context.month_branch,
                        "line_branch": line.branch,
                        "moving": line.is_moving,
                    },
                    source_id="034_月破章:p0004",
                )
            )

        day_relation = _day_relation(line.element, day_element)
        facts.append(
            make_fact(
                "ZSBY-018-DAY-ACTION",
                id=f"fact-day-relation-l{line.position}",
                type="DAY_RELATION",
                line=line.position,
                value=day_relation,
                evidence={
                    "day_branch": context.day_branch,
                    "day_element": day_element.value,
                    "line_element": line.element.value,
                },
                source_id="018_日辰章:p0005",
            )
        )

        if CLASH[context.day_branch] == line.branch:
            if line.is_moving:
                fact_type = "MOVING_DAY_CLASH"
                value = "旺相愈动；休囚仅标记潜在冲散，不作消失"
                source = "026_动散章:p0001"
            elif level in {"月建", "旺", "相", "余气"}:
                fact_type = "DARK_MOVEMENT"
                value = True
                source = "025_暗动章:p0001"
            else:
                fact_type = "DAY_BREAK"
                value = True
                source = "018_日辰章:p0003"
            rule_id = {
                "MOVING_DAY_CLASH": "ZSBY-026-MOVING-DAY-CLASH",
                "DARK_MOVEMENT": "ZSBY-025-DARK-MOVEMENT",
                "DAY_BREAK": "ZSBY-018-DAY-ACTION",
            }[fact_type]
            facts.append(
                make_fact(
                    rule_id,
                    id=f"fact-{fact_type.lower().replace('_', '-')}-l{line.position}",
                    type=fact_type,
                    line=line.position,
                    value=value,
                    evidence={
                        "day_branch": context.day_branch,
                        "line_branch": line.branch,
                        "seasonal_strength": level,
                        "moving": line.is_moving,
                    },
                    source_id=source,
                )
            )

        if COMBINE[context.month_branch] == line.branch:
            combine_effect, combine_overcomes = _combine_effect(
                context,
                line,
                partner_branch=context.month_branch,
                scope="month",
                strength_level=level,
            )
            facts.append(
                make_fact(
                    "ZSBY-020-COMBINE",
                    id=f"fact-month-combine-l{line.position}",
                    type="MONTH_COMBINE",
                    line=line.position,
                    value=True,
                    evidence={
                        "month_branch": context.month_branch,
                        "line_branch": line.branch,
                        "moving": line.is_moving,
                        "effect": combine_effect,
                        "overcome": combine_overcomes,
                    },
                    source_id=(
                        "020_六合章:p0026"
                        if combine_overcomes
                        else "020_六合章:p0009"
                    ),
                )
            )
        if COMBINE[context.day_branch] == line.branch:
            combine_effect, combine_overcomes = _combine_effect(
                context,
                line,
                partner_branch=context.day_branch,
                scope="day",
                strength_level=level,
            )
            facts.append(
                make_fact(
                    "ZSBY-020-COMBINE",
                    id=f"fact-day-combine-l{line.position}",
                    type="DAY_COMBINE",
                    line=line.position,
                    value=True,
                    evidence={
                        "day_branch": context.day_branch,
                        "line_branch": line.branch,
                        "moving": line.is_moving,
                        "effect": combine_effect,
                        "overcome": combine_overcomes,
                    },
                    source_id=(
                        "020_六合章:p0026"
                        if combine_overcomes
                        else "020_六合章:p0009"
                    ),
                )
            )

        stage = _life_stage(line.element, context.day_branch)
        if stage is not None:
            facts.append(
                make_fact(
                    "ZSBY-030-LIFE-STAGE",
                    id=f"fact-life-stage-{stage}-l{line.position}",
                    type="LIFE_STAGE",
                    line=line.position,
                    value=stage,
                    evidence={
                        "line_element": line.element.value,
                        "day_branch": context.day_branch,
                    },
                    source_id="030_生旺墓绝章:p0003",
                )
            )

        changed = line.changed
        if changed is not None:
            changed_level = seasonal_strength_for(
                changed.branch,
                changed.element,
                context.month_branch,
            )
            facts.append(
                make_fact(
                    "ZSBY-016-SEASONAL-STRENGTH",
                    id=f"fact-changed-strength-l{line.position}",
                    type="CHANGED_SEASONAL_STRENGTH",
                    line=line.position,
                    value=changed_level,
                    evidence={
                        "actor": "changed",
                        "month_branch": context.month_branch,
                        "branch": changed.branch,
                        "element": changed.element.value,
                    },
                    source_id=SEASONAL_SOURCE_BY_MONTH[context.month_branch],
                )
            )
            if changed.branch in context.void_branches:
                facts.append(
                    make_fact(
                        "ZSBY-029-VOID",
                        id=f"fact-changed-void-l{line.position}",
                        type="CHANGED_VOID",
                        line=line.position,
                        value=True,
                        evidence={
                            "actor": "changed",
                            "branch": changed.branch,
                            "void_branches": list(context.void_branches),
                        },
                        source_id="029_旬空章:p0005",
                    )
                )
            if CLASH[context.month_branch] == changed.branch:
                facts.append(
                    make_fact(
                        "ZSBY-034-MONTH-BREAK",
                        id=f"fact-changed-month-break-l{line.position}",
                        type="CHANGED_MONTH_BREAK",
                        line=line.position,
                        value=True,
                        evidence={
                            "actor": "changed",
                            "month_branch": context.month_branch,
                            "branch": changed.branch,
                        },
                        source_id="034_月破章:p0004",
                    )
                )
            facts.append(
                make_fact(
                    "ZSBY-018-DAY-ACTION",
                    id=f"fact-changed-day-relation-l{line.position}",
                    type="CHANGED_DAY_RELATION",
                    line=line.position,
                    value=_day_relation(changed.element, day_element),
                    evidence={
                        "actor": "changed",
                        "day_branch": context.day_branch,
                        "day_element": day_element.value,
                        "branch": changed.branch,
                        "element": changed.element.value,
                        "branch_clash": CLASH[context.day_branch] == changed.branch,
                        "branch_combine": COMBINE[context.day_branch] == changed.branch,
                    },
                    source_id="018_日辰章:p0005",
                )
            )
            changed_stage = _life_stage(changed.element, context.day_branch)
            if changed_stage is not None:
                facts.append(
                    make_fact(
                        "ZSBY-030-LIFE-STAGE",
                        id=f"fact-changed-life-stage-{changed_stage}-l{line.position}",
                        type="CHANGED_LIFE_STAGE",
                        line=line.position,
                        value=changed_stage,
                        evidence={
                            "actor": "changed",
                            "element": changed.element.value,
                            "day_branch": context.day_branch,
                        },
                        source_id="030_生旺墓绝章:p0003",
                    )
                )

        hidden = line.hidden_spirit
        if hidden is not None:
            hidden_level = seasonal_strength_for(
                hidden.branch,
                hidden.element,
                context.month_branch,
            )
            facts.append(
                make_fact(
                    "ZSBY-016-SEASONAL-STRENGTH",
                    id=f"fact-hidden-strength-l{line.position}",
                    type="HIDDEN_SEASONAL_STRENGTH",
                    line=line.position,
                    value=hidden_level,
                    evidence={
                        "actor": "hidden",
                        "month_branch": context.month_branch,
                        "branch": hidden.branch,
                        "element": hidden.element.value,
                    },
                    source_id=SEASONAL_SOURCE_BY_MONTH[context.month_branch],
                )
            )
            if hidden.branch in context.void_branches:
                facts.append(
                    make_fact(
                        "ZSBY-029-VOID",
                        id=f"fact-hidden-void-l{line.position}",
                        type="HIDDEN_VOID",
                        line=line.position,
                        value=True,
                        evidence={
                            "actor": "hidden",
                            "branch": hidden.branch,
                            "void_branches": list(context.void_branches),
                        },
                        source_id="029_旬空章:p0005",
                    )
                )
            if CLASH[context.month_branch] == hidden.branch:
                facts.append(
                    make_fact(
                        "ZSBY-034-MONTH-BREAK",
                        id=f"fact-hidden-month-break-l{line.position}",
                        type="HIDDEN_MONTH_BREAK",
                        line=line.position,
                        value=True,
                        evidence={
                            "actor": "hidden",
                            "month_branch": context.month_branch,
                            "branch": hidden.branch,
                        },
                        source_id="034_月破章:p0004",
                    )
                )
            facts.append(
                make_fact(
                    "ZSBY-018-DAY-ACTION",
                    id=f"fact-hidden-day-relation-l{line.position}",
                    type="HIDDEN_DAY_RELATION",
                    line=line.position,
                    value=_day_relation(hidden.element, day_element),
                    evidence={
                        "actor": "hidden",
                        "day_branch": context.day_branch,
                        "day_element": day_element.value,
                        "branch": hidden.branch,
                        "element": hidden.element.value,
                        "branch_clash": CLASH[context.day_branch] == hidden.branch,
                        "branch_combine": COMBINE[context.day_branch] == hidden.branch,
                    },
                    source_id="018_日辰章:p0005",
                )
            )
            hidden_stage = _life_stage(hidden.element, context.day_branch)
            if hidden_stage is not None:
                facts.append(
                    make_fact(
                        "ZSBY-030-LIFE-STAGE",
                        id=f"fact-hidden-life-stage-{hidden_stage}-l{line.position}",
                        type="HIDDEN_LIFE_STAGE",
                        line=line.position,
                        value=hidden_stage,
                        evidence={
                            "actor": "hidden",
                            "element": hidden.element.value,
                            "day_branch": context.day_branch,
                        },
                        source_id="030_生旺墓绝章:p0003",
                    )
                )

    return facts
