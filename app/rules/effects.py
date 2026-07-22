from __future__ import annotations

from collections.abc import Iterable

from app.rules.elements import (
    BRANCH_ELEMENT,
    CLASH,
    EXTINCTION,
    GROWTH,
    PROSPERITY,
    TOMB,
    generates,
    overcomes,
    relation_between,
)
from app.rules.models import (
    Element,
    FactLayer,
    QuestionPerspective,
    RuleContext,
    RuleFact,
    UsefulGodCandidate,
    UsefulGodSelection,
)
from app.rules.registry import make_fact


_STRONG_LEVELS = {"月建", "旺", "相", "余气"}


def _line_facts(
    facts: Iterable[RuleFact],
    line: int,
    *types: str,
) -> list[RuleFact]:
    wanted = set(types)
    return [
        fact
        for fact in facts
        if fact.line == line and (not wanted or fact.type in wanted)
    ]


def _first(
    facts: Iterable[RuleFact],
    line: int,
    fact_type: str,
) -> RuleFact | None:
    return next(
        (
            fact
            for fact in facts
            if fact.line == line and fact.type == fact_type
        ),
        None,
    )


def _is_strong(fact: RuleFact | None) -> bool:
    return fact is not None and fact.value in _STRONG_LEVELS


def _moving_supports(
    context: RuleContext,
    *,
    target_line: int,
    target_element: Element,
) -> list[int]:
    return [
        line.position
        for line in context.lines
        if line.position != target_line
        and line.is_moving
        and generates(line.element, target_element)
    ]


def _day_supports(fact: RuleFact | None) -> bool:
    return fact is not None and fact.value in {"日辰生爻", "比扶"}


def _true_void_element(month_branch: str) -> Element:
    if month_branch in {"寅", "卯", "辰"}:
        return Element.EARTH
    if month_branch in {"巳", "午", "未"}:
        return Element.METAL
    if month_branch in {"申", "酉", "戌"}:
        return Element.WOOD
    return Element.FIRE


def _base_effects(
    context: RuleContext,
    facts: tuple[RuleFact, ...],
) -> list[RuleFact]:
    result: list[RuleFact] = []
    for line in context.lines:
        strength = _first(facts, line.position, "SEASONAL_STRENGTH")
        day = _first(facts, line.position, "DAY_RELATION")
        moving_support = _moving_supports(
            context,
            target_line=line.position,
            target_element=line.element,
        )
        supported = _is_strong(strength) or _day_supports(day) or bool(moving_support)

        void = _first(facts, line.position, "旬空")
        if void is not None:
            true_void = line.element is _true_void_element(context.month_branch)
            month_break = _first(facts, line.position, "MONTH_BREAK") is not None
            if line.is_moving:
                status = "nominal_only_moving"
            elif supported:
                status = "nominal_only_supported"
            elif true_void:
                status = "true_empty"
            elif month_break:
                status = "effective_empty_month_broken"
            else:
                status = "effective_empty"
            result.append(
                make_fact(
                    "ZSBY-029-VOID",
                    id=f"fact-void-effect-l{line.position}",
                    type="VOID_EFFECT",
                    line=line.position,
                    value=status,
                    evidence={
                        "nominal_fact_id": void.id,
                        "moving": line.is_moving,
                        "strong": _is_strong(strength),
                        "day_support": _day_supports(day),
                        "moving_support_lines": moving_support,
                        "month_break": month_break,
                        "true_void": true_void,
                    },
                    source_id="029_旬空章:p0005",
                    layer=FactLayer.EFFECTIVE,
                )
            )

        month_break = _first(facts, line.position, "MONTH_BREAK")
        if month_break is not None:
            if line.is_moving:
                status = "active_moving"
            elif supported:
                status = "conditional_supported"
            else:
                status = "inactive_static"
            result.append(
                make_fact(
                    "ZSBY-034-MONTH-BREAK",
                    id=f"fact-month-break-effect-l{line.position}",
                    type="MONTH_BREAK_EFFECT",
                    line=line.position,
                    value=status,
                    evidence={
                        "nominal_fact_id": month_break.id,
                        "moving": line.is_moving,
                        "strong": _is_strong(strength),
                        "day_support": _day_supports(day),
                        "moving_support_lines": moving_support,
                    },
                    source_id="034_月破章:p0004",
                    layer=FactLayer.EFFECTIVE,
                )
            )

        for stage_fact in _line_facts(facts, line.position, "LIFE_STAGE"):
            stage = str(stage_fact.value)
            if stage in {"墓", "绝"}:
                status = "overridden_by_support" if supported else "effective_adverse"
            elif stage in {"长生", "帝旺"}:
                status = "effective_support" if supported else "conditional"
            else:
                status = "conditional"
            result.append(
                make_fact(
                    "ZSBY-030-LIFE-STAGE",
                    id=f"fact-life-stage-effect-{stage}-l{line.position}",
                    type="LIFE_STAGE_EFFECT",
                    line=line.position,
                    value=status,
                    evidence={
                        "stage": stage,
                        "stage_fact_id": stage_fact.id,
                        "strong": _is_strong(strength),
                        "day_support": _day_supports(day),
                        "moving_support_lines": moving_support,
                    },
                    source_ids=(
                        "030_生旺墓绝章:p0003",
                        "030_生旺墓绝章:p0005",
                        "030_生旺墓绝章:p0006",
                    ),
                    layer=FactLayer.EFFECTIVE,
                )
            )

        for actor in context.lines:
            if not actor.is_moving or actor.position == line.position:
                continue
            stages = {
                "长生": GROWTH[line.element],
                "帝旺": PROSPERITY[line.element],
                "墓": TOMB[line.element],
                "绝": EXTINCTION[line.element],
            }
            stage = next(
                (
                    name
                    for name, branch in stages.items()
                    if branch == actor.branch
                ),
                None,
            )
            if stage is not None:
                dynamic_fact = make_fact(
                    "ZSBY-030-LIFE-STAGE",
                    id=(
                        f"fact-dynamic-life-stage-{stage}-"
                        f"l{line.position}-by-l{actor.position}"
                    ),
                    type="DYNAMIC_LIFE_STAGE",
                    line=line.position,
                    related_lines=(actor.position,),
                    value=stage,
                    evidence={
                        "target_element": line.element.value,
                        "moving_branch": actor.branch,
                    },
                    source_id="030_生旺墓绝章:p0004",
                )
                result.append(dynamic_fact)
                if stage in {"墓", "绝"}:
                    dynamic_status = (
                        "overridden_by_support"
                        if supported
                        else "effective_adverse"
                    )
                elif stage in {"长生", "帝旺"}:
                    dynamic_status = (
                        "effective_support"
                        if supported
                        else "conditional"
                    )
                else:
                    dynamic_status = "conditional"
                result.append(
                    make_fact(
                        "ZSBY-030-LIFE-STAGE",
                        id=(
                            f"fact-dynamic-life-stage-effect-{stage}-"
                            f"l{line.position}-by-l{actor.position}"
                        ),
                        type="DYNAMIC_LIFE_STAGE_EFFECT",
                        line=line.position,
                        related_lines=(actor.position,),
                        value=dynamic_status,
                        evidence={
                            "stage": stage,
                            "stage_fact_id": dynamic_fact.id,
                            "supported": supported,
                        },
                        source_ids=(
                            "030_生旺墓绝章:p0004",
                            "030_生旺墓绝章:p0005",
                            "030_生旺墓绝章:p0006",
                        ),
                        layer=FactLayer.EFFECTIVE,
                    )
                )

        if line.changed is not None:
            changed_strength = _first(
                facts,
                line.position,
                "CHANGED_SEASONAL_STRENGTH",
            )
            changed_day = _first(
                facts,
                line.position,
                "CHANGED_DAY_RELATION",
            )
            changed_supported = _is_strong(changed_strength) or _day_supports(
                changed_day
            )
            changed_void = _first(facts, line.position, "CHANGED_VOID")
            if changed_void is not None:
                changed_true_void = (
                    line.changed.element
                    is _true_void_element(context.month_branch)
                )
                changed_void_status = "nominal_only_transformation"
                result.append(
                    make_fact(
                        "ZSBY-029-VOID",
                        id=f"fact-changed-void-effect-l{line.position}",
                        type="CHANGED_VOID_EFFECT",
                        line=line.position,
                        value=changed_void_status,
                        evidence={
                            "nominal_fact_id": changed_void.id,
                            "strong": _is_strong(changed_strength),
                            "day_support": _day_supports(changed_day),
                            "true_void": changed_true_void,
                        },
                        source_id="029_旬空章:p0005",
                        layer=FactLayer.EFFECTIVE,
                    )
                )

            changed_break = _first(
                facts,
                line.position,
                "CHANGED_MONTH_BREAK",
            )
            if changed_break is not None:
                result.append(
                    make_fact(
                        "ZSBY-034-MONTH-BREAK",
                        id=f"fact-changed-month-break-effect-l{line.position}",
                        type="CHANGED_MONTH_BREAK_EFFECT",
                        line=line.position,
                        value=(
                            "conditional_supported"
                            if changed_supported
                            else "effective_transformation"
                        ),
                        evidence={
                            "nominal_fact_id": changed_break.id,
                            "strong": _is_strong(changed_strength),
                            "day_support": _day_supports(changed_day),
                        },
                        source_id="034_月破章:p0004",
                        layer=FactLayer.EFFECTIVE,
                    )
                )

            for index, stage_fact in enumerate(
                _line_facts(facts, line.position, "CHANGED_LIFE_STAGE"),
                start=1,
            ):
                stage = str(stage_fact.value)
                stage_supported = (
                    supported
                    if stage_fact.evidence.get("basis")
                    == "original_line_element"
                    else changed_supported
                )
                if stage in {"墓", "绝"}:
                    stage_status = (
                        "overridden_by_support"
                        if stage_supported
                        else "effective_adverse"
                    )
                elif stage in {"长生", "帝旺"}:
                    stage_status = (
                        "effective_support"
                        if stage_supported
                        else "conditional"
                    )
                else:
                    stage_status = "conditional"
                result.append(
                    make_fact(
                        "ZSBY-030-LIFE-STAGE",
                        id=(
                            f"fact-changed-life-stage-effect-{stage}-"
                            f"l{line.position}-{index}"
                        ),
                        type="CHANGED_LIFE_STAGE_EFFECT",
                        line=line.position,
                        value=stage_status,
                        evidence={
                            "stage": stage,
                            "stage_fact_id": stage_fact.id,
                            "basis": stage_fact.evidence.get("basis"),
                            "supported": stage_supported,
                        },
                        source_ids=(
                            "030_生旺墓绝章:p0004",
                            "030_生旺墓绝章:p0005",
                            "030_生旺墓绝章:p0006",
                        ),
                        layer=FactLayer.EFFECTIVE,
                    )
                )
    return result


def _hidden_effects(
    context: RuleContext,
    facts: tuple[RuleFact, ...],
) -> list[RuleFact]:
    result: list[RuleFact] = []
    month_element = BRANCH_ELEMENT[context.month_branch]
    day_element = BRANCH_ELEMENT[context.day_branch]
    for flying in context.lines:
        hidden = flying.hidden_spirit
        if hidden is None:
            continue
        hidden_strength = _first(
            facts,
            flying.position,
            "HIDDEN_SEASONAL_STRENGTH",
        )
        flying_strength = _first(
            facts,
            flying.position,
            "SEASONAL_STRENGTH",
        )
        useful_conditions: list[str] = []
        useless_conditions: list[str] = []

        if generates(month_element, hidden.element) or generates(
            day_element,
            hidden.element,
        ):
            useful_conditions.append("day_or_month_generates_hidden")
        if day_element is hidden.element:
            useful_conditions.append("day_supports_hidden")
        if _is_strong(hidden_strength):
            useful_conditions.append("hidden_is_strong")
        if generates(flying.element, hidden.element):
            useful_conditions.append("flying_generates_hidden")
        moving_generators = [
            line.position
            for line in context.lines
            if line.is_moving and generates(line.element, hidden.element)
        ]
        if moving_generators:
            useful_conditions.append("moving_line_generates_hidden")
        hidden_has_direct_support = (
            "day_or_month_generates_hidden" in useful_conditions
            or "day_supports_hidden" in useful_conditions
            or "flying_generates_hidden" in useful_conditions
            or bool(moving_generators)
        )

        flying_freed_by_calendar = (
            CLASH[context.month_branch] == flying.branch
            or CLASH[context.day_branch] == flying.branch
            or overcomes(month_element, flying.element)
            or overcomes(day_element, flying.element)
        )
        flying_freed_by_moving = [
            line.position
            for line in context.lines
            if line.is_moving
            and (
                CLASH[line.branch] == flying.branch
                or overcomes(line.element, flying.element)
            )
        ]
        if flying_freed_by_calendar or flying_freed_by_moving:
            useful_conditions.append("calendar_or_moving_frees_flying")

        flying_weak = (
            not _is_strong(flying_strength)
            or _first(facts, flying.position, "旬空") is not None
            or _first(facts, flying.position, "MONTH_BREAK") is not None
            or any(
                fact.value in {"墓", "绝"}
                for fact in _line_facts(facts, flying.position, "LIFE_STAGE")
            )
        )
        if flying_weak:
            useful_conditions.append("flying_is_weak_void_broken_tomb_or_extinct")

        hidden_weak = not _is_strong(hidden_strength)
        hidden_without_qi = hidden_weak and not hidden_has_direct_support
        if hidden_without_qi:
            useless_conditions.append("hidden_is_weak_without_support")
        if (
            CLASH[context.month_branch] == hidden.branch
            or CLASH[context.day_branch] == hidden.branch
            or overcomes(month_element, hidden.element)
            or overcomes(day_element, hidden.element)
        ):
            useless_conditions.append("calendar_clashes_or_overcomes_hidden")
        if _is_strong(flying_strength) and overcomes(
            flying.element,
            hidden.element,
        ):
            useless_conditions.append("strong_flying_overcomes_hidden")
        if any(
            branch in {TOMB[hidden.element], EXTINCTION[hidden.element]}
            for branch in (
                context.month_branch,
                context.day_branch,
                flying.branch,
            )
        ):
            useless_conditions.append("hidden_tomb_or_extinction")
        hidden_void_or_break = (
            _first(facts, flying.position, "HIDDEN_VOID") is not None
            or _first(facts, flying.position, "HIDDEN_MONTH_BREAK") is not None
        )
        if hidden_without_qi and hidden_void_or_break:
            useless_conditions.append("weak_hidden_is_void_or_broken")

        if useful_conditions and useless_conditions:
            status = "conflict"
        elif useful_conditions:
            status = "useful"
        elif useless_conditions:
            status = "useless"
        else:
            status = "unresolved"
        result.append(
            make_fact(
                "ZSBY-035-HIDDEN-EFFECT",
                id=f"fact-hidden-effect-l{flying.position}",
                type="HIDDEN_SPIRIT_EFFECT",
                line=flying.position,
                value=status,
                evidence={
                    "hidden_branch": hidden.branch,
                    "hidden_element": hidden.element.value,
                    "hidden_relative": hidden.relative.value,
                    "flying_branch": flying.branch,
                    "useful_conditions": useful_conditions,
                    "useless_conditions": useless_conditions,
                    "moving_generator_lines": moving_generators,
                    "flying_freed_by_moving_lines": flying_freed_by_moving,
                    "hidden_has_direct_support": hidden_has_direct_support,
                },
                source_ids=(
                    "035_飞伏神章:p0010",
                    "035_飞伏神章:p0014",
                ),
            )
        )
    return result


def _pattern_effects(
    context: RuleContext,
    useful: UsefulGodSelection,
    facts: tuple[RuleFact, ...],
) -> list[RuleFact]:
    result: list[RuleFact] = []
    useful_candidates = [
        candidate
        for candidate in useful.candidates
        if candidate.line is not None and candidate.element is not None
    ]
    world = next((line for line in context.lines if line.is_world), None)
    if world is not None:
        for harmony in (
            fact
            for fact in facts
            if fact.type in {"THREE_HARMONY", "THREE_HARMONY_PENDING"}
        ):
            harmony_element = Element(str(harmony.value))
            branches = list(harmony.evidence.get("branches", []))
            if world.branch in branches:
                world_relation = "world_in_group"
            elif generates(harmony_element, world.element):
                world_relation = "generates_world"
            elif overcomes(harmony_element, world.element):
                world_relation = "overcomes_world"
            else:
                world_relation = relation_between(
                    harmony_element,
                    world.element,
                )
            for candidate in useful_candidates:
                assert candidate.element is not None
                if candidate.branch in branches:
                    relation = (
                        "useful_in_group_detained"
                        if any(
                            term in context.question
                            for term in (
                                "出行",
                                "行人",
                                "回来",
                                "归来",
                                "回家",
                                "何时回",
                                "何时归",
                                "回否",
                                "归否",
                                "返",
                            )
                        )
                        else "useful_in_group_context"
                    )
                elif generates(harmony_element, candidate.element):
                    relation = "generates_useful"
                elif overcomes(harmony_element, candidate.element):
                    relation = "overcomes_useful"
                else:
                    relation = relation_between(
                        harmony_element,
                        candidate.element,
                    )
                suffix = (
                    ""
                    if len(useful_candidates) == 1
                    else f"-l{candidate.line}"
                )
                result.append(
                    make_fact(
                        "ZSBY-021-THREE-HARMONY",
                        id=(
                            f"fact-three-harmony-effect-"
                            f"{harmony_element.value}{suffix}"
                        ),
                        type="THREE_HARMONY_EFFECT",
                        related_lines=harmony.related_lines,
                        value=relation,
                        evidence={
                            "harmony_fact_id": harmony.id,
                            "harmony_status": harmony.evidence.get("status"),
                            "world_line": world.position,
                            "world_branch": world.branch,
                            "world_element": world.element.value,
                            "world_relation": world_relation,
                            "useful_line": candidate.line,
                            "useful_branch": candidate.branch,
                            "useful_element": candidate.element.value,
                            "useful_role": candidate.role,
                        },
                        source_id="021_三合章:p0009",
                        layer=FactLayer.EFFECTIVE,
                    )
                )
            if not useful_candidates or any(
                candidate.line != world.position
                for candidate in useful_candidates
            ):
                result.append(
                    make_fact(
                        "ZSBY-021-THREE-HARMONY",
                        id=(
                            f"fact-three-harmony-world-effect-"
                            f"{harmony_element.value}"
                        ),
                        type="THREE_HARMONY_WORLD_EFFECT",
                        related_lines=harmony.related_lines,
                        value=world_relation,
                        evidence={
                            "harmony_fact_id": harmony.id,
                            "harmony_status": harmony.evidence.get("status"),
                            "world_line": world.position,
                            "world_branch": world.branch,
                            "world_element": world.element.value,
                            "world_relation": world_relation,
                        },
                        source_id="021_三合章:p0009",
                        layer=FactLayer.EFFECTIVE,
                    )
                )

    hexagram_change = next(
        (
            fact
            for fact in facts
            if fact.type == "HEXAGRAM_CHANGE_RELATION"
        ),
        None,
    )
    if hexagram_change is not None:
        effect = {
            "变来克我": "adverse_overrides_useful_strength",
            "变来生我": "favorable",
            "我去克彼": "neutral_outward_control",
            "我去生彼": "conditional_outward_generation",
            "比和": "neutral",
        }[str(hexagram_change.value)]
        result.append(
            make_fact(
                "ZSBY-027-HEXAGRAM-CHANGE",
                id="fact-hexagram-change-effect",
                type="HEXAGRAM_CHANGE_EFFECT",
                value=effect,
                evidence={"relation_fact_id": hexagram_change.id},
                source_id="027_卦变生克墓绝章:p0001",
                layer=FactLayer.EFFECTIVE,
            )
        )

    if not useful_candidates:
        return result

    reverse = next((fact for fact in facts if fact.type == "REVERSE_CHANT"), None)
    repeated = next(
        (fact for fact in facts if fact.type == "REPEATED_CHANT"),
        None,
    )
    for candidate in useful_candidates:
        assert candidate.line is not None
        strength_type = (
            "HIDDEN_SEASONAL_STRENGTH"
            if candidate.role == "hidden"
            else "CHANGED_SEASONAL_STRENGTH"
            if candidate.role == "changed"
            else "SEASONAL_STRENGTH"
        )
        selected_strength = _first(facts, candidate.line, strength_type)
        strong = _is_strong(selected_strength)
        return_harm = (
            candidate.role not in {"changed", "hidden"}
            and bool(
                _line_facts(
                    facts,
                    candidate.line,
                    "RETURN_OVERCOME",
                    "RETURN_CLASH",
                )
            )
        )
        suffix = (
            ""
            if len(useful_candidates) == 1
            else f"-l{candidate.line}"
        )
        if reverse is not None:
            status = (
                "adverse_return_harm"
                if return_harm
                else "conditional_success"
                if strong
                else "conditional_reversal"
            )
            result.append(
                make_fact(
                    "ZSBY-028-REVERSE-CHANT",
                    id=f"fact-reverse-chant-effect{suffix}",
                    type="REVERSE_CHANT_EFFECT",
                    line=candidate.line,
                    value=status,
                    evidence={
                        "pattern_fact_id": reverse.id,
                        "useful_role": candidate.role,
                        "useful_strong": strong,
                        "return_harm": return_harm,
                    },
                    source_id="028_反伏章:p0008",
                    layer=FactLayer.EFFECTIVE,
                )
            )
        if repeated is not None:
            result.append(
                make_fact(
                    "ZSBY-028-REPEATED-CHANT",
                    id=f"fact-repeated-chant-effect{suffix}",
                    type="REPEATED_CHANT_EFFECT",
                    line=candidate.line,
                    value=(
                        "conditional_release_when_clashed"
                        if strong
                        else "adverse_stagnation"
                    ),
                    evidence={
                        "pattern_fact_id": repeated.id,
                        "useful_role": candidate.role,
                        "useful_strong": strong,
                    },
                    source_id="028_反伏章:p0017",
                    layer=FactLayer.EFFECTIVE,
                )
            )
    return result


def _role_effects(
    context: RuleContext,
    facts: tuple[RuleFact, ...],
) -> list[RuleFact]:
    result: list[RuleFact] = []
    near_event = any(
        word in context.question
        for word in ("今日", "今天", "明日", "近日", "几时", "何时")
    )
    roles_by_line: dict[int, str] = {}
    useful_actor_by_line: dict[int, str] = {}
    for fact in facts:
        if fact.line is None:
            continue
        role = {
            "USEFUL_GOD": "useful",
            "YUAN_GOD": "origin",
            "TABOO_GOD": "taboo",
            "ENEMY_GOD": "enemy",
        }.get(fact.type)
        if role is not None:
            if fact.type == "USEFUL_GOD":
                roles_by_line[fact.line] = role
                useful_actor_by_line[fact.line] = str(
                    fact.evidence.get("role", "visible")
                )
            elif roles_by_line.get(fact.line) != "useful":
                roles_by_line[fact.line] = role

    for fact in facts:
        if fact.line is None or fact.type not in {
            "DARK_MOVEMENT",
            "MOVING_DAY_CLASH",
        }:
            continue
        role = roles_by_line.get(fact.line)
        strength = _first(facts, fact.line, "SEASONAL_STRENGTH")
        day = _first(facts, fact.line, "DAY_RELATION")
        line = next(
            line for line in context.lines if line.position == fact.line
        )
        moving_support = _moving_supports(
            context,
            target_line=fact.line,
            target_element=line.element,
        )
        if fact.type == "DARK_MOVEMENT":
            value = {
                "useful": "activated_favorable",
                "origin": "activated_favorable",
                "taboo": "activated_adverse",
                "enemy": "activated_adverse",
            }.get(role, "activated_context")
            rule_id = "ZSBY-025-DARK-MOVEMENT"
            effect_type = "DARK_MOVEMENT_EFFECT"
            source_id = "025_暗动章:p0001"
        else:
            remains_active = (
                _is_strong(strength)
                or _day_supports(day)
                or bool(moving_support)
            )
            value = (
                "not_scattered"
                if remains_active
                else "conditional_possible_scatter"
            )
            rule_id = "ZSBY-026-MOVING-DAY-CLASH"
            effect_type = "MOVING_DAY_CLASH_EFFECT"
            source_id = "026_动散章:p0001"
        result.append(
            make_fact(
                rule_id,
                id=f"fact-{fact.type.lower().replace('_', '-')}-effect-l{fact.line}",
                type=effect_type,
                line=fact.line,
                value=value,
                evidence={
                    "structural_fact_id": fact.id,
                    "role": role,
                    "strong": _is_strong(strength),
                    "day_support": _day_supports(day),
                    "moving_support_lines": moving_support,
                },
                source_id=source_id,
                layer=FactLayer.EFFECTIVE,
            )
        )

    for fact in facts:
        if fact.type != "CHANGED_TO_OFFICIAL" or fact.line is None:
            continue
        role = roles_by_line.get(fact.line)
        return_generation = _first(facts, fact.line, "RETURN_GENERATE")
        if role == "useful" and useful_actor_by_line.get(fact.line) == "changed":
            value = "context_only"
        elif role in {"useful", "origin"} and return_generation is None:
            value = "adverse_changed_to_official"
        elif role in {"useful", "origin"}:
            value = "conflict_with_return_generation"
        else:
            value = "context_only"
        result.append(
            make_fact(
                "ZSBY-031-CHANGED-OMEN",
                id=f"fact-changed-to-official-effect-l{fact.line}",
                type="CHANGED_TO_OFFICIAL_EFFECT",
                line=fact.line,
                value=value,
                evidence={
                    "structural_fact_id": fact.id,
                    "role": role,
                    "return_generation_fact_id": (
                        return_generation.id
                        if return_generation is not None
                        else None
                    ),
                },
                source_ids=(
                    "031_各门类题头总注章:p0003",
                    "031_各门类题头总注章:p0004",
                ),
                layer=FactLayer.EFFECTIVE,
            )
        )

    for fact in facts:
        if fact.type not in {"ADVANCE", "RETREAT"} or fact.line is None:
            continue
        role = roles_by_line.get(fact.line)
        if role is None:
            continue
        strength = _first(facts, fact.line, "SEASONAL_STRENGTH")
        strong = _is_strong(strength)
        if near_event and strong:
            direction = "conditional_near_event"
        elif fact.type == "ADVANCE":
            direction = (
                "favorable"
                if role in {"useful", "origin"}
                else "adverse"
            )
        else:
            direction = (
                "adverse"
                if role in {"useful", "origin"}
                else "favorable"
            )
        rule_id = "ZSBY-036-ADVANCE" if fact.type == "ADVANCE" else "ZSBY-036-RETREAT"
        result.append(
            make_fact(
                rule_id,
                id=f"fact-{fact.type.lower()}-effect-l{fact.line}",
                type=f"{fact.type}_EFFECT",
                line=fact.line,
                value=direction,
                evidence={
                    "structural_fact_id": fact.id,
                    "role": role,
                    "near_event": near_event,
                    "strong": strong,
                },
                source_id=(
                    "036_进神退神章:p0009"
                    if fact.type == "ADVANCE"
                    else "036_进神退神章:p0011"
                ),
                layer=FactLayer.EFFECTIVE,
            )
        )
    return result


def _ghost_tomb_effect(
    context: RuleContext,
    useful: UsefulGodSelection,
    facts: tuple[RuleFact, ...],
) -> list[RuleFact]:
    if context.perspective is None:
        return []

    targets: list[UsefulGodCandidate]
    if context.perspective is QuestionPerspective.SELF:
        world = next((line for line in context.lines if line.is_world), None)
        if world is None:
            return []
        targets = [
            UsefulGodCandidate(
                role="world",
                line=world.position,
                relative=world.relative,
                branch=world.branch,
                element=world.element,
                reasons=("自占依《随鬼入墓章》看世爻",),
            )
        ]
    else:
        targets = [
            candidate
            for candidate in useful.candidates
            if candidate.line is not None and candidate.element is not None
        ]
    if not targets:
        return []

    result: list[RuleFact] = []
    for candidate in targets:
        assert candidate.line is not None
        assert candidate.element is not None
        target_line = next(
            line for line in context.lines if line.position == candidate.line
        )
        tomb_branch = TOMB[candidate.element]
        modes: list[str] = []
        if context.day_branch == tomb_branch:
            modes.append("day_tomb")
        if (
            candidate.role not in {"changed", "hidden"}
            and target_line.changed is not None
            and target_line.changed.branch == tomb_branch
        ):
            modes.append("changed_tomb")
        moving_tomb_lines = [
            line.position
            for line in context.lines
            if line.is_moving and line.branch == tomb_branch
        ]
        if moving_tomb_lines:
            modes.append("moving_tomb")
        if not modes:
            continue

        strength_type = (
            "HIDDEN_SEASONAL_STRENGTH"
            if candidate.role == "hidden"
            else "CHANGED_SEASONAL_STRENGTH"
            if candidate.role == "changed"
            else "SEASONAL_STRENGTH"
        )
        strength = _first(facts, candidate.line, strength_type)
        strong = _is_strong(strength)
        day_type = (
            "HIDDEN_DAY_RELATION"
            if candidate.role == "hidden"
            else "CHANGED_DAY_RELATION"
            if candidate.role == "changed"
            else "DAY_RELATION"
        )
        day_fact = _first(facts, candidate.line, day_type)
        moving_support = _moving_supports(
            context,
            target_line=candidate.line,
            target_element=candidate.element,
        )
        supported = strong or _day_supports(day_fact) or bool(moving_support)
        harming_sources: list[str] = []
        if overcomes(BRANCH_ELEMENT[context.month_branch], candidate.element):
            harming_sources.append("month_overcomes_target")
        if day_fact is not None and day_fact.value == "日辰克爻":
            harming_sources.append("day_overcomes_target")
        moving_harm = [
            line.position
            for line in context.lines
            if line.position != candidate.line
            and line.is_moving
            and overcomes(line.element, candidate.element)
        ]
        if moving_harm:
            harming_sources.append("moving_line_overcomes_target")
        if (
            candidate.role not in {"changed", "hidden"}
            and _first(facts, candidate.line, "RETURN_OVERCOME") is not None
        ):
            harming_sources.append("return_overcomes_target")
        if candidate.role == "hidden" and overcomes(
            target_line.element,
            candidate.element,
        ):
            harming_sources.append("flying_overcomes_hidden")
        weak = strength is not None and strength.value == "休囚"
        harmed = bool(harming_sources)
        tomb_opened = (
            CLASH[context.month_branch] == tomb_branch
            or CLASH[context.day_branch] == tomb_branch
            or any(
                line.is_moving and CLASH[line.branch] == tomb_branch
                for line in context.lines
            )
        )
        status = (
            "adverse_real_tomb"
            if weak and harmed and not tomb_opened
            else "conditional_opened_or_supported"
        )
        suffix = "" if len(targets) == 1 else f"-l{candidate.line}"
        result.append(
            make_fact(
                "ZSBY-037-GHOST-TOMB",
                id=f"fact-ghost-tomb{suffix}",
                type="GHOST_TOMB",
                line=candidate.line,
                related_lines=tuple(moving_tomb_lines),
                value=status,
                evidence={
                    "perspective": context.perspective.value,
                    "target_role": candidate.role,
                    "target_branch": candidate.branch,
                    "target_element": candidate.element.value,
                    "modes": modes,
                    "tomb_branch": tomb_branch,
                    "target_strong": strong,
                    "target_weak": weak,
                    "target_harmed": harmed,
                    "harming_sources": harming_sources,
                    "moving_harm_lines": moving_harm,
                    "supported": supported,
                    "moving_support_lines": moving_support,
                    "tomb_opened": tomb_opened,
                },
                source_id="037_随鬼入墓章:p0004",
            )
        )
    return result


def effective_facts(
    context: RuleContext,
    useful: UsefulGodSelection,
    facts: tuple[RuleFact, ...],
) -> list[RuleFact]:
    result = _base_effects(context, facts)
    result.extend(_hidden_effects(context, facts))
    enriched = facts + tuple(result)
    result.extend(_pattern_effects(context, useful, enriched))
    enriched = facts + tuple(result)
    result.extend(_role_effects(context, enriched))
    enriched = facts + tuple(result)
    result.extend(_ghost_tomb_effect(context, useful, enriched))
    return result
