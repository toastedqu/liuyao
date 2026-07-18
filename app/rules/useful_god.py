from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from app.rules.elements import (
    BRANCH_ELEMENT,
    source_element_for,
    overcoming_element_for,
)
from app.rules.models import (
    Element,
    Relative,
    RuleContext,
    RuleFact,
    UsefulGodCandidate,
    UsefulGodChoice,
    UsefulGodSelection,
)


RELATIVE_SOURCE_IDS: dict[Relative, str] = {
    Relative.PARENT: "008_用神章:p0001",
    Relative.OFFICIAL: "008_用神章:p0002",
    Relative.SIBLING: "008_用神章:p0003",
    Relative.WEALTH: "008_用神章:p0006",
    Relative.CHILD: "008_用神章:p0007",
}
ALL_RELATIVE_SOURCE_IDS = tuple(RELATIVE_SOURCE_IDS.values())


def _line_fact_types(facts: Iterable[RuleFact]) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    for fact in facts:
        if fact.line is not None:
            result.setdefault(fact.line, set()).add(fact.type)
    return result


def select_useful_god(
    context: RuleContext,
    facts: Iterable[RuleFact],
    choice: UsefulGodChoice,
) -> UsefulGodSelection:
    facts = tuple(facts)
    target = choice.target
    relative = choice.useful_relative
    reason = choice.rationale
    types = _line_fact_types(facts)

    if choice.mode == "world":
        world = next((line for line in context.lines if line.is_world), None)
        if world is None:
            return UsefulGodSelection(
                status="unresolved",
                target=target,
                selection_mode="world",
                useful_relative=None,
                rationale=("排盘缺少世爻，无法确定用神",),
                source_ids=choice.source_ids,
            )
        candidate = UsefulGodCandidate(
            role="world",
            line=world.position,
            relative=world.relative,
            branch=world.branch,
            element=world.element,
            score=100,
            reasons=(reason,),
        )
        return _selection(
            target,
            world.relative,
            (candidate,),
            reason,
            selection_mode="world",
            source_ids=choice.source_ids,
        )

    if relative is None:
        return UsefulGodSelection(
            status="unresolved",
            target=target,
            selection_mode="relative",
            useful_relative=None,
            rationale=(reason, "模型未给出六亲，无法定位用神"),
            source_ids=choice.source_ids,
        )

    relative_source_ids = choice.source_ids

    visible: list[UsefulGodCandidate] = []
    for line in context.lines:
        if line.relative is not relative:
            continue
        line_types = types.get(line.position, set())
        score = 0
        reasons = []
        if line.is_moving:
            score += 30
            reasons.append("动爻")
        if "SEASONAL_STRENGTH" in line_types:
            strength_fact = next(
                fact
                for fact in facts
                if fact.line == line.position and fact.type == "SEASONAL_STRENGTH"
            )
            strength_score = {
                "月建": 25,
                "旺": 20,
                "相": 15,
                "余气": 5,
                "休囚": 0,
            }[str(strength_fact.value)]
            score += strength_score
            reasons.append(str(strength_fact.value))
        if "旬空" in line_types:
            score -= 5
            reasons.append("旬空")
        if "MONTH_BREAK" in line_types:
            score -= 5
            reasons.append("月破")
        if line.is_world:
            score += 3
            reasons.append("临世")
        if line.is_response:
            score += 2
            reasons.append("临应")
        visible.append(
            UsefulGodCandidate(
                role="visible",
                line=line.position,
                relative=relative,
                branch=line.branch,
                element=line.element,
                score=score,
                reasons=tuple(reasons),
            )
        )

    visible.sort(key=lambda candidate: (-candidate.score, candidate.line or 0))
    if visible:
        status = (
            "multiple"
            if len(visible) > 1 and visible[0].score == visible[1].score
            else "selected"
        )
        source_ids = relative_source_ids
        if len(visible) > 1:
            source_ids += ("039_两现章:p0001", "039_两现章:p0002")
            reason += (
                "；两现时按古法旺相、动静、空破作确定性排序，"
                "但原书另载取空取破的验例"
            )
            if status == "multiple":
                reason += "；最高分并列，保留歧义而不指定爻位"
        return _selection(
            target,
            relative,
            tuple(visible),
            reason,
            selection_mode="relative",
            status=status,
            source_ids=source_ids,
        )

    hidden: list[UsefulGodCandidate] = []
    for line in context.lines:
        spirit = line.hidden_spirit
        if spirit is None or spirit.relative is not relative:
            continue
        hidden.append(
            UsefulGodCandidate(
                role="hidden",
                line=line.position,
                relative=relative,
                branch=spirit.branch,
                element=spirit.element,
                score=0,
                reasons=("用神不上卦，取本宫首卦伏神",),
            )
        )
    if hidden:
        return _selection(
            target,
            relative,
            tuple(hidden),
            "用神不上卦，伏于飞神之下",
            selection_mode="relative",
            status="multiple" if len(hidden) > 1 else "selected",
            source_ids=relative_source_ids
            + ("035_飞伏神章:example0001:question",),
        )

    month_element = BRANCH_ELEMENT[context.month_branch]
    day_element = BRANCH_ELEMENT[context.day_branch]
    if relative_for_element(context.palace_element, month_element) is relative:
        rationale = "用神不上卦且月建为该六亲；依原文以月建为用"
    elif relative_for_element(context.palace_element, day_element) is relative:
        rationale = "用神不上卦且日辰为该六亲；依原文以日辰为用"
    else:
        return UsefulGodSelection(
            status="unresolved",
            target=target,
            selection_mode="relative",
            useful_relative=relative,
            rationale=(reason, "用神不上卦，排盘未提供相应伏神，不能臆定"),
            source_ids=relative_source_ids
            + ("035_飞伏神章:example0001:question",),
        )
    return UsefulGodSelection(
        status="selected",
        target=target,
        selection_mode="relative",
        useful_relative=relative,
        useful_element=(
            month_element
            if relative_for_element(context.palace_element, month_element) is relative
            else day_element
        ),
        rationale=(reason, rationale),
        source_ids=relative_source_ids
        + ("035_飞伏神章:example0001:question",),
    )


def relative_for_element(palace: Element, element: Element) -> Relative:
    from app.rules.elements import relative_for

    return relative_for(palace, element)


def _selection(
    target: str,
    relative: Relative,
    candidates: tuple[UsefulGodCandidate, ...],
    reason: str,
    *,
    selection_mode: Literal["world", "relative"],
    status: Literal["selected", "multiple"] = "selected",
    source_ids: tuple[str, ...] | None = None,
) -> UsefulGodSelection:
    selected = candidates[0]
    useful = selected.element
    if useful is None:
        return UsefulGodSelection(
            status="unresolved",
            target=target,
            selection_mode=selection_mode,
            useful_relative=relative,
            candidates=candidates,
            rationale=(reason, "候选缺少五行，无法计算元忌仇神"),
            source_ids=source_ids or (RELATIVE_SOURCE_IDS[relative],),
        )
    yuan = source_element_for(useful)
    taboo = overcoming_element_for(useful)
    enemy = overcoming_element_for(yuan)
    resolved_source_ids = source_ids or (RELATIVE_SOURCE_IDS[relative],)
    return UsefulGodSelection(
        status=status,
        target=target,
        selection_mode=selection_mode,
        useful_relative=relative,
        candidates=candidates,
        selected_line=selected.line if status == "selected" else None,
        useful_element=useful,
        yuan_element=yuan,
        taboo_element=taboo,
        enemy_element=enemy,
        rationale=(reason,),
        source_ids=resolved_source_ids
        + ("009_用神、元神、忌神、仇神章:p0001",),
    )
