from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from app.rules.elements import (
    BRANCH_ELEMENT,
    overcoming_element_for,
    overcomes,
    source_element_for,
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
_STRENGTH_PRIORITY = {
    "休囚": 0,
    "余气": 1,
    "相": 2,
    "旺": 3,
    "月建": 4,
}


def _line_fact_types(facts: Iterable[RuleFact]) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    for fact in facts:
        if fact.line is not None:
            result.setdefault(fact.line, set()).add(fact.type)
    return result


def _first_fact(
    facts: tuple[RuleFact, ...],
    line: int,
    fact_type: str,
) -> RuleFact | None:
    return next(
        (fact for fact in facts if fact.line == line and fact.type == fact_type),
        None,
    )


def _candidate_priority(
    context: RuleContext,
    facts: tuple[RuleFact, ...],
    candidate: UsefulGodCandidate,
) -> tuple[tuple[int, int, int, int, int], tuple[str, ...]]:
    assert candidate.line is not None
    assert candidate.element is not None
    line = next(line for line in context.lines if line.position == candidate.line)
    hidden = candidate.role == "hidden"
    changed = candidate.role == "changed"
    strength_type = (
        "HIDDEN_SEASONAL_STRENGTH"
        if hidden
        else "CHANGED_SEASONAL_STRENGTH"
        if changed
        else "SEASONAL_STRENGTH"
    )
    void_type = "HIDDEN_VOID" if hidden else "CHANGED_VOID" if changed else "旬空"
    break_type = (
        "HIDDEN_MONTH_BREAK"
        if hidden
        else "CHANGED_MONTH_BREAK"
        if changed
        else "MONTH_BREAK"
    )
    day_type = (
        "HIDDEN_DAY_RELATION"
        if hidden
        else "CHANGED_DAY_RELATION"
        if changed
        else "DAY_RELATION"
    )
    stage_type = (
        "HIDDEN_LIFE_STAGE"
        if hidden
        else "CHANGED_LIFE_STAGE"
        if changed
        else "LIFE_STAGE"
    )

    strength = _first_fact(facts, candidate.line, strength_type)
    strength_level = str(strength.value) if strength is not None else "休囚"
    moving = line.is_moving and not hidden
    month_broken = _first_fact(facts, candidate.line, break_type) is not None
    void = _first_fact(facts, candidate.line, void_type) is not None

    injuries: list[str] = []
    day_relation = _first_fact(facts, candidate.line, day_type)
    if day_relation is not None and day_relation.value == "日辰克爻":
        injuries.append("受日辰克")
    life_stage = _first_fact(facts, candidate.line, stage_type)
    if life_stage is not None and life_stage.value in {"墓", "绝"}:
        injuries.append(str(life_stage.value))
    if hidden:
        if overcomes(line.element, candidate.element):
            injuries.append("受飞神克")
    elif not changed:
        if _first_fact(facts, candidate.line, "RETURN_OVERCOME") is not None:
            injuries.append("受回头克")
        if any(
            actor.position != candidate.line
            and actor.is_moving
            and overcomes(actor.element, candidate.element)
            for actor in context.lines
        ):
            injuries.append("受动爻克")

    priority = (
        _STRENGTH_PRIORITY.get(strength_level, 0),
        int(moving),
        int(not month_broken),
        int(not void),
        int(not injuries),
    )
    reasons = (
        f"月令={strength_level}",
        "动爻" if moving else "静爻",
        "月破" if month_broken else "不破",
        "旬空" if void else "不空",
        "、".join(injuries) if injuries else "未见受伤",
    )
    return priority, reasons


def _order_multiple_candidates(
    context: RuleContext,
    facts: tuple[RuleFact, ...],
    candidates: list[UsefulGodCandidate],
) -> tuple[tuple[UsefulGodCandidate, ...], Literal["selected", "multiple"], str]:
    ranked = []
    for candidate in candidates:
        priority, reasons = _candidate_priority(context, facts, candidate)
        ranked.append(
            (
                priority,
                candidate.model_copy(
                    update={
                        "reasons": tuple(
                            dict.fromkeys((*candidate.reasons, *reasons))
                        )
                    }
                ),
            )
        )
    best_priority = max(priority for priority, _candidate in ranked)
    best = sorted(
        (
            candidate
            for priority, candidate in ranked
            if priority == best_priority
        ),
        key=lambda candidate: candidate.line or 0,
    )
    remaining = sorted(
        (
            (priority, candidate)
            for priority, candidate in ranked
            if priority != best_priority
        ),
        key=lambda item: (
            tuple(-value for value in item[0]),
            item[1].line or 0,
        ),
    )
    ordered = tuple([*best, *(candidate for _priority, candidate in remaining)])
    if len(best) == 1:
        selected = best[0]
        rationale = (
            "依《两现章》古法按月令旺衰、动静、不破、不空、不伤"
            f"逐项比较，第{selected.line}爻条件优先，取为主用爻；"
            "其他候选仍保留，以防原书所示空破爻填实应验"
        )
        return ordered, "selected", rationale
    return (
        ordered,
        "multiple",
        "各候选按《两现章》古法比较后条件仍完全相同，原文没有依据"
        "强定其中一爻；系统保留全部候选并令裁决暂缓，不要求用户选爻",
    )


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

    if choice.mode in {"world", "response"}:
        role = choice.mode
        selected_role_line = next(
            (
                line
                for line in context.lines
                if (line.is_world if role == "world" else line.is_response)
            ),
            None,
        )
        if selected_role_line is None:
            return UsefulGodSelection(
                status="unresolved",
                target=target,
                selection_mode=role,
                useful_relative=None,
                rationale=(f"排盘缺少{'世爻' if role == 'world' else '应爻'}，无法确定用神",),
                source_ids=choice.source_ids,
            )
        candidate = UsefulGodCandidate(
            role=role,
            line=selected_role_line.position,
            relative=selected_role_line.relative,
            branch=selected_role_line.branch,
            element=selected_role_line.element,
            reasons=(reason,),
        )
        return _selection(
            target,
            selected_role_line.relative,
            (candidate,),
            reason,
            selection_mode=role,
            source_ids=choice.source_ids,
        )

    if relative is None:
        return UsefulGodSelection(
            status="unresolved",
            target=target,
            selection_mode="relative",
            useful_relative=None,
            rationale=(reason, "未提供六亲，无法定位用神"),
            source_ids=choice.source_ids,
        )

    relative_source_ids = choice.source_ids

    visible: list[UsefulGodCandidate] = []
    for line in context.lines:
        if line.relative is not relative:
            continue
        line_types = types.get(line.position, set())
        reasons = []
        if line.is_moving:
            reasons.append("动爻")
        if "SEASONAL_STRENGTH" in line_types:
            strength_fact = next(
                fact
                for fact in facts
                if fact.line == line.position and fact.type == "SEASONAL_STRENGTH"
            )
            reasons.append(str(strength_fact.value))
        if "旬空" in line_types:
            reasons.append("旬空")
        if "MONTH_BREAK" in line_types:
            reasons.append("月破")
        if line.is_world:
            reasons.append("临世")
        if line.is_response:
            reasons.append("临应")
        visible.append(
            UsefulGodCandidate(
                role="visible",
                line=line.position,
                relative=relative,
                branch=line.branch,
                element=line.element,
                reasons=tuple(reasons),
            )
        )

    visible.sort(key=lambda candidate: candidate.line or 0)
    if visible:
        ordered = tuple(visible)
        status: Literal["selected", "multiple"] = "selected"
        source_ids = relative_source_ids
        if len(visible) > 1:
            source_ids += ("039_两现章:p0001", "039_两现章:p0002")
            ordered, status, multiple_reason = _order_multiple_candidates(
                context,
                facts,
                visible,
            )
            reason += f"；{multiple_reason}"
        return _selection(
            target,
            relative,
            ordered,
            reason,
            selection_mode="relative",
            status=status,
            source_ids=source_ids,
        )

    month_element = BRANCH_ELEMENT[context.month_branch]
    day_element = BRANCH_ELEMENT[context.day_branch]
    if relative_for_element(context.palace_element, month_element) is relative:
        return UsefulGodSelection(
            status="selected",
            target=target,
            selection_mode="relative",
            useful_relative=relative,
            useful_element=month_element,
            yuan_element=source_element_for(month_element),
            taboo_element=overcoming_element_for(month_element),
            enemy_element=overcoming_element_for(source_element_for(month_element)),
            rationale=(reason, "用神不上卦，依《飞伏神章》先以月建为用"),
            source_ids=relative_source_ids
            + ("035_飞伏神章:example0001:question",),
        )
    if relative_for_element(context.palace_element, day_element) is relative:
        return UsefulGodSelection(
            status="selected",
            target=target,
            selection_mode="relative",
            useful_relative=relative,
            useful_element=day_element,
            yuan_element=source_element_for(day_element),
            taboo_element=overcoming_element_for(day_element),
            enemy_element=overcoming_element_for(source_element_for(day_element)),
            rationale=(reason, "用神不上卦，依《飞伏神章》先以日辰为用"),
            source_ids=relative_source_ids
            + ("035_飞伏神章:example0001:question",),
        )

    changed_candidates = [
        UsefulGodCandidate(
            role="changed",
            line=line.position,
            relative=relative,
            branch=line.changed.branch,
            element=line.changed.element,
            reasons=("用神不上本卦而现于变爻",),
        )
        for line in context.lines
        if line.changed is not None and line.changed.relative is relative
    ]
    if changed_candidates:
        changed_candidates.sort(key=lambda candidate: candidate.line or 0)
        ordered = tuple(changed_candidates)
        status: Literal["selected", "multiple"] = "selected"
        changed_reason = (
            "用神不上本卦而现于变爻，依《飞伏神章》先取变爻，"
            "不越过变爻径取伏神"
        )
        source_ids = relative_source_ids + ("035_飞伏神章:p0017",)
        if len(changed_candidates) > 1:
            source_ids += ("039_两现章:p0001", "039_两现章:p0002")
            ordered, status, multiple_reason = _order_multiple_candidates(
                context,
                facts,
                changed_candidates,
            )
            changed_reason += f"；{multiple_reason}"
        return _selection(
            target,
            relative,
            ordered,
            changed_reason,
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
                reasons=("用神不上卦，取本宫首卦伏神",),
            )
        )
    if hidden:
        hidden.sort(key=lambda candidate: candidate.line or 0)
        hidden_source_ids = relative_source_ids + (
            "035_飞伏神章:p0013",
        )
        ordered = tuple(hidden)
        hidden_reason = "用神不上卦，伏于飞神之下"
        status: Literal["selected", "multiple"] = "selected"
        if len(hidden) > 1:
            hidden_source_ids += (
                "039_两现章:p0001",
                "039_两现章:p0002",
            )
            ordered, status, multiple_reason = _order_multiple_candidates(
                context,
                facts,
                hidden,
            )
            hidden_reason += f"；{multiple_reason}"
        return _selection(
            target,
            relative,
            ordered,
            hidden_reason,
            selection_mode="relative",
            status=status,
            source_ids=hidden_source_ids,
        )

    return UsefulGodSelection(
        status="unresolved",
        target=target,
        selection_mode="relative",
        useful_relative=relative,
        rationale=(
            reason,
            "用神不上卦，日月亦非用神，且排盘未提供本宫伏神；"
            "《飞伏神章》主张另占，不可臆定",
        ),
        source_ids=relative_source_ids
        + ("035_飞伏神章:p0013",),
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
    selection_mode: Literal["world", "response", "relative"],
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
