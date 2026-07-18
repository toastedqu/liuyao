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


def seasonal_strength(line: LineContext, month_branch: str) -> str:
    month_element = BRANCH_ELEMENT[month_branch]
    if line.branch == month_branch:
        return "月建"
    if month_branch in EARTH_MONTH_STRONG_BRANCHES:
        if line.branch in EARTH_MONTH_STRONG_BRANCHES[month_branch]:
            return "旺"
        if SEASONAL_RESIDUAL.get(month_branch) is line.element:
            return "余气"
        if GENERATES[month_element] is line.element:
            return "相"
        return "休囚"
    if line.element is month_element:
        return "旺"
    if GENERATES[month_element] is line.element:
        return "相"
    return "休囚"


def strength_facts(context: RuleContext) -> list[RuleFact]:
    facts: list[RuleFact] = []
    month_element = BRANCH_ELEMENT[context.month_branch]
    day_element = BRANCH_ELEMENT[context.day_branch]

    for line in context.lines:
        level = seasonal_strength(line, context.month_branch)
        facts.append(
            RuleFact(
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
                rule_source="016_四时旺相章:p0001",
            )
        )

        if line.branch in context.void_branches:
            facts.append(
                RuleFact(
                    id=f"fact-void-l{line.position}",
                    type="旬空",
                    line=line.position,
                    value=True,
                    evidence={
                        "branch": line.branch,
                        "void_branches": list(context.void_branches),
                        "moving": line.is_moving,
                        "effect": "动不为空，仍须待填实" if line.is_moving else "旬内为空",
                    },
                    rule_source="029_旬空章:p0001",
                )
            )

        if CLASH[context.month_branch] == line.branch:
            facts.append(
                RuleFact(
                    id=f"fact-month-break-l{line.position}",
                    type="MONTH_BREAK",
                    line=line.position,
                    value=True,
                    evidence={
                        "month_branch": context.month_branch,
                        "line_branch": line.branch,
                        "moving": line.is_moving,
                    },
                    rule_source="034_月破章:p0002",
                )
            )

        day_relation = "比扶"
        if generates(day_element, line.element):
            day_relation = "日辰生爻"
        elif overcomes(day_element, line.element):
            day_relation = "日辰克爻"
        elif overcomes(line.element, day_element):
            day_relation = "爻克日辰"
        elif generates(line.element, day_element):
            day_relation = "爻生日辰"
        facts.append(
            RuleFact(
                id=f"fact-day-relation-l{line.position}",
                type="DAY_RELATION",
                line=line.position,
                value=day_relation,
                evidence={
                    "day_branch": context.day_branch,
                    "day_element": day_element.value,
                    "line_element": line.element.value,
                },
                rule_source="018_日辰章:p0002",
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
            facts.append(
                RuleFact(
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
                    rule_source=source,
                )
            )

        if COMBINE[context.month_branch] == line.branch:
            facts.append(
                RuleFact(
                    id=f"fact-month-combine-l{line.position}",
                    type="MONTH_COMBINE",
                    line=line.position,
                    value=True,
                    evidence={
                        "month_branch": context.month_branch,
                        "line_branch": line.branch,
                        "moving": line.is_moving,
                        "effect": "合绊" if line.is_moving else "合起",
                    },
                    rule_source="020_六合章:p0002",
                )
            )
        if COMBINE[context.day_branch] == line.branch:
            facts.append(
                RuleFact(
                    id=f"fact-day-combine-l{line.position}",
                    type="DAY_COMBINE",
                    line=line.position,
                    value=True,
                    evidence={
                        "day_branch": context.day_branch,
                        "line_branch": line.branch,
                        "moving": line.is_moving,
                        "effect": "合绊" if line.is_moving else "合起",
                    },
                    rule_source="020_六合章:p0002",
                )
            )

        stages = {
            "长生": GROWTH[line.element],
            "帝旺": PROSPERITY[line.element],
            "墓": TOMB[line.element],
            "绝": EXTINCTION[line.element],
        }
        matching = [name for name, branch in stages.items() if branch == context.day_branch]
        if matching:
            stage = matching[0]
            facts.append(
                RuleFact(
                    id=f"fact-life-stage-{stage}-l{line.position}",
                    type="LIFE_STAGE",
                    line=line.position,
                    value=stage,
                    evidence={
                        "line_element": line.element.value,
                        "day_branch": context.day_branch,
                    },
                    rule_source="030_生旺墓绝章:example0001:judgement",
                )
            )

    return facts
