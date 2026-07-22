from __future__ import annotations

from collections import defaultdict

from app.rules.elements import (
    BRANCH_ELEMENT,
    generates,
    overcoming_element_for,
    overcomes,
    source_element_for,
)
from app.rules.models import (
    OutcomeAnalysis,
    OutcomeEvidence,
    OutcomeEvidenceDirection,
    OutcomeEvidenceWeight,
    OutcomeGuardrail,
    RuleContext,
    RuleFact,
    UsefulGodSelection,
)


_STRONG_LEVELS = {"月建", "旺", "相", "余气"}
_VOID_RESISTANT_LEVELS = {"月建", "旺"}
_SEVERE_INFLUENCE_BLOCKERS = {
    "RETURN_OVERCOME",
}
_DELAYING_INFLUENCE_FACTS = {
    "旬空",
    "MONTH_BREAK",
    "RETURN_CLASH",
}


def build_outcome_analysis(
    context: RuleContext,
    useful: UsefulGodSelection,
    facts: tuple[RuleFact, ...],
) -> OutcomeAnalysis:
    candidates = [
        candidate
        for candidate in useful.candidates
        if candidate.line is not None and candidate.element is not None
    ]
    if len(candidates) <= 1:
        return _build_selected_outcome_analysis(context, useful, facts)

    candidate_results: list[tuple[object, OutcomeAnalysis]] = []
    for candidate in candidates:
        assert candidate.element is not None
        yuan = source_element_for(candidate.element)
        candidate_useful = useful.model_copy(
            update={
                "status": "selected",
                "candidates": (candidate,),
                "selected_line": candidate.line,
                "useful_element": candidate.element,
                "yuan_element": yuan,
                "taboo_element": overcoming_element_for(candidate.element),
                "enemy_element": overcoming_element_for(yuan),
            }
        )
        candidate_results.append(
            (
                candidate,
                _build_selected_outcome_analysis(
                    context,
                    candidate_useful,
                    facts,
                ),
            )
        )

    evidence: list[OutcomeEvidence] = []
    limitations = [
        "用神两现时依《两现章》分别完成各候选裁决；古法排序只标记默认主爻，"
        "旬空、月破候选仍可在填实时应验。",
    ]
    guardrails = set()
    for candidate, analysis in candidate_results:
        guardrails.add(analysis.guardrail)
        label = f"第{candidate.line}爻{candidate.role}候选"
        evidence.extend(
            item.model_copy(
                update={
                    "id": f"candidate-l{candidate.line}-{item.id}",
                    "description": f"{label}：{item.description}",
                }
            )
            for item in analysis.evidence
        )
        limitations.extend(f"{label}：{item}" for item in analysis.limitations)

    if guardrails == {OutcomeGuardrail.FAVORABLE_ONLY}:
        guardrail = OutcomeGuardrail.FAVORABLE_ONLY
    elif guardrails == {OutcomeGuardrail.ADVERSE_ONLY}:
        guardrail = OutcomeGuardrail.ADVERSE_ONLY
    elif (
        OutcomeGuardrail.MIXED in guardrails
        or {
            OutcomeGuardrail.FAVORABLE_ONLY,
            OutcomeGuardrail.ADVERSE_ONLY,
        }.issubset(guardrails)
    ):
        guardrail = OutcomeGuardrail.MIXED
    else:
        guardrail = OutcomeGuardrail.ABSTAIN
        limitations.append(
            "各候选不能形成同一确定方向，且本次没有可供合参的前卦；不得只凭古法排序强断。"
        )
    return OutcomeAnalysis(
        guardrail=guardrail,
        evidence=tuple(evidence),
        limitations=tuple(dict.fromkeys(limitations)),
    )


def _build_selected_outcome_analysis(
    context: RuleContext,
    useful: UsefulGodSelection,
    facts: tuple[RuleFact, ...],
) -> OutcomeAnalysis:
    """Build a conservative, auditable evidence gate for the final outlook.

    This does not calculate a fortune score. It identifies only facts that
    directly concern the selected useful god or an active generator/attacker,
    and abstains whenever the original text requires contextual balancing.
    """

    if useful.status != "selected" or useful.selected_line is None:
        return OutcomeAnalysis(
            guardrail=OutcomeGuardrail.ABSTAIN,
            limitations=("用神未唯一定位，裁决层不强制吉凶方向。",),
        )

    selected_line = useful.selected_line
    selected_candidate = next(
        (
            candidate
            for candidate in useful.candidates
            if candidate.line == selected_line
        ),
        None,
    )
    facts_by_line: dict[int, list[RuleFact]] = defaultdict(list)
    for fact in facts:
        if fact.line is not None:
            facts_by_line[fact.line].append(fact)

    def facts_for(line: int, *types: str) -> list[RuleFact]:
        wanted = set(types)
        return [fact for fact in facts_by_line[line] if fact.type in wanted]

    def first(line: int, fact_type: str) -> RuleFact | None:
        return next(
            (fact for fact in facts_by_line[line] if fact.type == fact_type),
            None,
        )

    evidence: list[OutcomeEvidence] = []

    def add(
        evidence_id: str,
        direction: OutcomeEvidenceDirection,
        weight: OutcomeEvidenceWeight,
        description: str,
        evidence_facts: list[RuleFact],
        *,
        source_ids: tuple[str, ...] = (),
    ) -> None:
        fact_ids = tuple(dict.fromkeys(fact.id for fact in evidence_facts))
        if not fact_ids:
            return
        resolved_sources = tuple(
            dict.fromkeys(
                [
                    *(
                        source_id
                        for fact in evidence_facts
                        for source_id in fact.source_ids
                    ),
                    *source_ids,
                ]
            )
        )
        evidence.append(
            OutcomeEvidence(
                id=evidence_id,
                direction=direction,
                weight=weight,
                description=description,
                fact_ids=fact_ids,
                source_ids=resolved_sources,
            )
        )

    useful_fact = first(selected_line, "USEFUL_GOD")
    is_hidden = selected_candidate is not None and selected_candidate.role == "hidden"
    is_changed = selected_candidate is not None and selected_candidate.role == "changed"
    if is_hidden:
        hidden_effect = first(selected_line, "HIDDEN_SPIRIT_EFFECT")
        hidden_facts = facts_for(
            selected_line,
            "USEFUL_GOD",
            "FLYING_HIDDEN_RELATION",
            "HIDDEN_SPIRIT_EFFECT",
            "HIDDEN_SEASONAL_STRENGTH",
            "HIDDEN_DAY_RELATION",
            "HIDDEN_VOID",
            "HIDDEN_MONTH_BREAK",
        )
        add(
            "hidden-useful-god",
            OutcomeEvidenceDirection.CONTEXT,
            OutcomeEvidenceWeight.PRIMARY,
            "用神为伏神；裁决使用伏神自身地支、旺衰及六种有用、五种无用条件，不以飞神属性替代。",
            hidden_facts,
        )
        if hidden_effect is None or hidden_effect.value != "useful":
            return OutcomeAnalysis(
                guardrail=OutcomeGuardrail.ABSTAIN,
                evidence=tuple(evidence),
                limitations=("伏神有用、无用条件互见或不足，裁决层保留。",),
            )

    if useful_fact is None:
        return OutcomeAnalysis(
            guardrail=OutcomeGuardrail.ABSTAIN,
            limitations=("缺少已定位用神事实，裁决层不强制吉凶方向。",),
        )

    selected_strength = first(
        selected_line,
        "HIDDEN_SEASONAL_STRENGTH"
        if is_hidden
        else "CHANGED_SEASONAL_STRENGTH"
        if is_changed
        else "SEASONAL_STRENGTH",
    )
    selected_day = first(
        selected_line,
        "HIDDEN_DAY_RELATION"
        if is_hidden
        else "CHANGED_DAY_RELATION"
        if is_changed
        else "DAY_RELATION",
    )
    selected_break = first(
        selected_line,
        "HIDDEN_MONTH_BREAK"
        if is_hidden
        else "CHANGED_MONTH_BREAK"
        if is_changed
        else "MONTH_BREAK",
    )
    selected_void = first(
        selected_line,
        "HIDDEN_VOID"
        if is_hidden
        else "CHANGED_VOID"
        if is_changed
        else "旬空",
    )
    selected_line_context = next(
        line for line in context.lines if line.position == selected_line
    )
    selected_is_moving = selected_line_context.is_moving and not is_hidden
    lines_by_position = {line.position: line for line in context.lines}
    strength_level = str(selected_strength.value) if selected_strength else None
    day_relation = str(selected_day.value) if selected_day else None
    selected_return_support = (
        []
        if is_hidden or is_changed
        else facts_for(
            selected_line,
            "RETURN_GENERATE",
            "ADVANCE_EFFECT",
        )
    )
    unrooted = bool(
        selected_break
        and strength_level == "休囚"
        and day_relation == "日辰克爻"
        and not selected_is_moving
        and not selected_return_support
    )

    if selected_strength is not None:
        if strength_level == "月建":
            add(
                "useful-at-month-command",
                OutcomeEvidenceDirection.FAVORABLE,
                OutcomeEvidenceWeight.PRIMARY,
                "用神临月建，为直接有力主证。",
                [selected_strength],
            )
        elif strength_level in _STRONG_LEVELS:
            add(
                "useful-seasonally-supported",
                OutcomeEvidenceDirection.FAVORABLE,
                OutcomeEvidenceWeight.SUPPORTING,
                f"用神得月令之{strength_level}，作为有利辅证。",
                [selected_strength],
            )
        elif strength_level == "休囚":
            add(
                "useful-seasonally-weak",
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.SUPPORTING,
                "用神休囚，为不利辅证；不能脱离日辰、动爻和根气单独定凶。",
                [selected_strength],
            )

    if selected_day is not None:
        if day_relation in {"日辰生爻", "比扶"}:
            add(
                "day-supports-useful",
                OutcomeEvidenceDirection.FAVORABLE,
                OutcomeEvidenceWeight.PRIMARY,
                f"日辰对用神为{day_relation}，是直接有利主证。",
                [selected_day],
            )
        elif day_relation == "日辰克爻":
            add(
                "day-overcomes-useful",
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.PRIMARY,
                "日辰克用神，是直接不利主证，但仍须与月令和动爻生扶合看。",
                [selected_day],
            )

    if unrooted:
        add(
            "useful-unrooted",
            OutcomeEvidenceDirection.ADVERSE,
            OutcomeEvidenceWeight.PRIMARY,
            "用神同时休囚、月破并受日克，符合无根门槛；元神有力亦不能机械改判为吉。",
            [
                fact
                for fact in (selected_strength, selected_break, selected_day)
                if fact is not None
            ],
            source_ids=(
                "010_元神、忌神、衰旺章:p0017",
                "010_元神、忌神、衰旺章:p0019",
            ),
        )

    generator_lines: dict[int, list[RuleFact]] = defaultdict(list)
    attacker_lines: dict[int, list[RuleFact]] = defaultdict(list)
    for fact in facts:
        if fact.line is None:
            continue
        if fact.type == "MOVING_GENERATES_USEFUL":
            generator_lines[fact.line].append(fact)
        elif fact.type == "MOVING_OVERCOMES_USEFUL":
            attacker_lines[fact.line].append(fact)

    for line in context.lines:
        dark = first(line.position, "DARK_MOVEMENT")
        if dark is None:
            continue
        yuan = first(line.position, "YUAN_GOD")
        taboo = first(line.position, "TABOO_GOD")
        if yuan is not None:
            generator_lines[line.position].extend((yuan, dark))
        if taboo is not None:
            attacker_lines[line.position].extend((taboo, dark))

    def blockers(line: int) -> list[RuleFact]:
        blocked = facts_for(line, *_SEVERE_INFLUENCE_BLOCKERS)
        blocked.extend(
            fact
            for fact in facts_for(line, "ADVANCE_EFFECT", "RETREAT_EFFECT")
            if fact.value in {"adverse", "conditional_near_event"}
        )
        blocked.extend(
            fact
            for fact in facts_for(line, "MOVING_DAY_CLASH_EFFECT")
            if fact.value == "conditional_possible_scatter"
        )
        actor_strength = first(line, "SEASONAL_STRENGTH")
        actor_day = first(line, "DAY_RELATION")
        actor_is_weak = (
            actor_strength is not None
            and str(actor_strength.value) == "休囚"
        )
        actor = lines_by_position[line]
        if actor_is_weak:
            weak_damage = []
            if actor_day is not None and actor_day.value == "日辰克爻":
                weak_damage.append(actor_day)
            if overcomes(BRANCH_ELEMENT[context.month_branch], actor.element):
                weak_damage.append(actor_strength)
            weak_damage.extend(facts_for(line, "旬空", "MONTH_BREAK"))
            blocked.extend(weak_damage)
        for fact in facts_for(
            line,
            "MONTH_COMBINE",
            "DAY_COMBINE",
            "RETURN_COMBINE",
        ):
            if fact.type in {"MONTH_COMBINE", "DAY_COMBINE"} and (
                fact.evidence.get("effect")
                not in {"合绊", "言克不言合"}
            ):
                continue
            blocked.append(fact)
        blocked.extend(
            fact
            for fact in facts_for(
                line,
                "LIFE_STAGE_EFFECT",
                "DYNAMIC_LIFE_STAGE_EFFECT",
                "CHANGED_LIFE_STAGE_EFFECT",
            )
            if fact.value == "effective_adverse"
        )
        return list({fact.id: fact for fact in blocked}.values())

    viable_generators = {
        line
        for line in generator_lines
        if not unrooted and not blockers(line)
    }
    simultaneous_relief = bool(viable_generators and attacker_lines)

    effective_generators: set[int] = set()
    for line, influence_facts in sorted(generator_lines.items()):
        severe = blockers(line)
        unique_facts = list(
            {fact.id: fact for fact in [*influence_facts, *severe]}.values()
        )
        if unrooted:
            add(
                f"generator-cannot-root-l{line}",
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.PRIMARY,
                f"第{line}爻虽生用神，但用神无根，不能把生扶直接计为成事主证。",
                unique_facts,
                source_ids=("010_元神、忌神、衰旺章:p0017",),
            )
        elif severe:
            add(
                f"generator-constrained-l{line}",
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.PRIMARY,
                f"第{line}爻生用神但自身受回头克、退、墓绝或合绊，须先处理其有力条件。",
                unique_facts,
                source_ids=("010_元神、忌神、衰旺章:p0012",),
            )
        else:
            effective_generators.add(line)
            add(
                f"active-generator-l{line}",
                OutcomeEvidenceDirection.FAVORABLE,
                OutcomeEvidenceWeight.PRIMARY,
                f"第{line}爻为发动或暗动的元神，直接生扶用神。",
                list({fact.id: fact for fact in influence_facts}.values()),
                source_ids=(
                    "010_元神、忌神、衰旺章:p0002",
                    "014_动静生克章:p0004",
                ),
            )
        delaying = facts_for(line, *_DELAYING_INFLUENCE_FACTS)
        if delaying:
            add(
                f"generator-timing-condition-l{line}",
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.SUPPORTING,
                f"第{line}爻的生扶另受空、破、冲等时间条件限制，不能当作即时结果。",
                delaying,
            )

    for line, influence_facts in sorted(attacker_lines.items()):
        severe = blockers(line)
        unique_facts = list(
            {fact.id: fact for fact in [*influence_facts, *severe]}.values()
        )
        if simultaneous_relief:
            add(
                f"attacker-diverted-l{line}",
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.PRIMARY,
                f"第{line}爻虽克用神，但元神与忌神同动，须先按贪生忘克审查，不得直接计凶。",
                unique_facts,
                source_ids=(
                    "010_元神、忌神、衰旺章:p0005",
                    "010_元神、忌神、衰旺章:p0016",
                ),
            )
        elif severe:
            add(
                f"attacker-constrained-l{line}",
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.PRIMARY,
                f"第{line}爻虽克用神，但自身受回头克、退、墓绝或合绊，不能直接计凶。",
                unique_facts,
                source_ids=("010_元神、忌神、衰旺章:p0016",),
            )
        else:
            add(
                f"active-attacker-l{line}",
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.PRIMARY,
                f"第{line}爻为发动或暗动的忌神，直接克害用神。",
                list({fact.id: fact for fact in influence_facts}.values()),
                source_ids=(
                    "010_元神、忌神、衰旺章:p0013",
                    "014_动静生克章:p0004",
                ),
            )
        delaying = facts_for(line, *_DELAYING_INFLUENCE_FACTS)
        if delaying:
            add(
                f"attacker-timing-condition-l{line}",
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.SUPPORTING,
                f"第{line}爻的克害另受空、破、冲等时间条件限制，不能当作即时结果。",
                delaying,
            )

    candidate_actor = (
        "hidden"
        if is_hidden
        else "changed"
        if is_changed
        else "primary"
    )
    selected_star_facts = [
        fact
        for fact in facts_for(
            selected_line,
            "STAR_NOBLE",
            "STAR_LU",
            "STAR_HORSE",
            "STAR_HAPPINESS",
        )
        if fact.evidence.get("actor") == candidate_actor
    ]
    star_supported = (
        not unrooted
        and (
            strength_level in _STRONG_LEVELS
            or day_relation in {"日辰生爻", "比扶"}
            or bool(effective_generators)
        )
    )
    if star_supported:
        for star in selected_star_facts:
            add(
                f"useful-{star.type.lower().replace('_', '-')}",
                OutcomeEvidenceDirection.FAVORABLE,
                OutcomeEvidenceWeight.SUPPORTING,
                f"用神旺而临{star.value}，依《星煞章》只作有利辅证，不独操祸福。",
                [star],
                source_ids=("040_星煞章:p0009",),
            )
        for happiness in (
            fact
            for fact in facts
            if fact.type == "STAR_HAPPINESS"
            and fact.line is not None
            and fact.line != selected_line
            and fact.evidence.get("actor") == "primary"
        ):
            actor = lines_by_position[happiness.line]
            break_fact = first(happiness.line, "MONTH_BREAK")
            generator = first(happiness.line, "MOVING_GENERATES_USEFUL")
            if (
                actor.is_moving
                and break_fact is not None
                and generator is not None
                and generates(actor.element, useful.useful_element)
            ):
                add(
                    f"moving-happiness-support-l{happiness.line}",
                    OutcomeEvidenceDirection.FAVORABLE,
                    OutcomeEvidenceWeight.SUPPORTING,
                    "天喜虽临月破而发动生扶旺相用神，依原文仍以喜论。",
                    [happiness, break_fact, generator],
                    source_ids=("040_星煞章:p0008",),
                )

    if not any(line.is_moving for line in context.lines) and not any(
        first(line.position, "DARK_MOVEMENT") for line in context.lines
    ):
        if strength_level == "休囚":
            for line in context.lines:
                actor_strength = first(line.position, "SEASONAL_STRENGTH")
                if actor_strength is None or str(actor_strength.value) not in _STRONG_LEVELS:
                    continue
                if facts_for(line.position, "旬空", "MONTH_BREAK"):
                    continue
                yuan = first(line.position, "YUAN_GOD")
                taboo = first(line.position, "TABOO_GOD")
                if yuan is not None:
                    if not unrooted:
                        add(
                            f"quiet-strong-generator-l{line.position}",
                            OutcomeEvidenceDirection.FAVORABLE,
                            OutcomeEvidenceWeight.SUPPORTING,
                            f"六爻全静时，第{line.position}爻元神旺相，可生休囚用神。",
                            [yuan, actor_strength],
                            source_ids=("014_动静生克章:p0001",),
                        )
                if taboo is not None:
                    add(
                        f"quiet-strong-attacker-l{line.position}",
                        OutcomeEvidenceDirection.ADVERSE,
                        OutcomeEvidenceWeight.SUPPORTING,
                        f"六爻全静时，第{line.position}爻忌神旺相，可克休囚用神。",
                        [taboo, actor_strength],
                        source_ids=("014_动静生克章:p0001",),
                    )

    if selected_break is not None:
        break_effect = first(
            selected_line,
            "CHANGED_MONTH_BREAK_EFFECT"
            if is_changed
            else "MONTH_BREAK_EFFECT",
        )
        break_status = str(break_effect.value) if break_effect is not None else None
        if break_status != "inactive_static" and (
            selected_is_moving
            or day_relation in {"日辰生爻", "比扶"}
            or effective_generators
            or is_hidden
        ):
            add(
                "useful-month-break-conditional",
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.PRIMARY,
                "用神月破但有发动、日扶或动爻生助，只表示当下受阻与待实破，不得自动定凶。",
                [
                    fact
                    for fact in (selected_break, break_effect)
                    if fact is not None
                ],
                source_ids=("034_月破章:p0004",),
            )
        else:
            add(
                "useful-static-month-break",
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.PRIMARY,
                "用神静而月破，且无日辰或动爻生助，是直接不利主证。",
                [selected_break],
                source_ids=("034_月破章:p0004",),
            )

    if selected_void is not None:
        void_effect = first(
            selected_line,
            "CHANGED_VOID_EFFECT" if is_changed else "VOID_EFFECT",
        )
        void_status = str(void_effect.value) if void_effect is not None else None
        supported_void = void_status in {
            "nominal_only_moving",
            "nominal_only_supported",
            "nominal_only_transformation",
        } or (
            is_hidden
            and (
                strength_level in _VOID_RESISTANT_LEVELS
                or day_relation in {"日辰生爻", "比扶"}
            )
        )
        if supported_void:
            add(
                "useful-void-conditional",
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.PRIMARY,
                "用神虽名义旬空，但得动、旺或生扶，原书不作真空；只保留应期条件。",
                [
                    fact
                    for fact in (selected_void, void_effect)
                    if fact is not None
                ],
                source_ids=("029_旬空章:p0005",),
            )
        else:
            add(
                "useful-true-void",
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.PRIMARY,
                "用神休囚、静而旬空且无生扶，构成直接不利主证。",
                [selected_void],
                source_ids=("029_旬空章:p0005",),
            )

    direct_changes = (
        (
            "RETURN_GENERATE",
            OutcomeEvidenceDirection.FAVORABLE,
            "用神动化回头生，是直接有利主证。",
        ),
        (
            "RETURN_OVERCOME",
            OutcomeEvidenceDirection.ADVERSE,
            "用神动化回头克，是直接不利主证。",
        ),
    )
    if not is_changed:
        for fact_type, direction, description in direct_changes:
            matching = facts_for(selected_line, fact_type)
            add(
                f"useful-{fact_type.lower().replace('_', '-')}",
                direction,
                OutcomeEvidenceWeight.PRIMARY,
                description,
                matching,
            )

    for effect in facts_for(selected_line, "ADVANCE_EFFECT", "RETREAT_EFFECT"):
        direction = {
            "favorable": OutcomeEvidenceDirection.FAVORABLE,
            "adverse": OutcomeEvidenceDirection.ADVERSE,
            "conditional_near_event": OutcomeEvidenceDirection.CONDITIONAL,
        }.get(str(effect.value), OutcomeEvidenceDirection.CONDITIONAL)
        add(
            f"useful-{effect.type.lower().replace('_', '-')}",
            direction,
            (
                OutcomeEvidenceWeight.PRIMARY
                if direction
                in {
                    OutcomeEvidenceDirection.FAVORABLE,
                    OutcomeEvidenceDirection.ADVERSE,
                }
                else OutcomeEvidenceWeight.SUPPORTING
            ),
            "进退神已按该爻的用、元、忌、仇角色及事情远近求值，不以进退名称机械定吉凶。",
            [effect],
        )

    transformed_effect_directions = {
        "true_empty": OutcomeEvidenceDirection.ADVERSE,
        "effective_transformation": OutcomeEvidenceDirection.ADVERSE,
        "effective_adverse": OutcomeEvidenceDirection.ADVERSE,
        "nominal_only_supported": OutcomeEvidenceDirection.CONDITIONAL,
        "nominal_only_transformation": OutcomeEvidenceDirection.CONDITIONAL,
        "conditional_supported": OutcomeEvidenceDirection.CONDITIONAL,
        "overridden_by_support": OutcomeEvidenceDirection.CONTEXT,
        "effective_support": OutcomeEvidenceDirection.FAVORABLE,
        "conditional": OutcomeEvidenceDirection.CONDITIONAL,
    }
    if is_changed:
        transformed_effects = [
            effect
            for effect in facts_for(
                selected_line,
                "CHANGED_VOID_EFFECT",
                "CHANGED_MONTH_BREAK_EFFECT",
                "CHANGED_LIFE_STAGE_EFFECT",
            )
            if effect.evidence.get("basis") != "original_line_element"
        ]
    elif is_hidden:
        transformed_effects = []
    else:
        transformed_effects = facts_for(
            selected_line,
            "CHANGED_VOID_EFFECT",
            "CHANGED_MONTH_BREAK_EFFECT",
            "LIFE_STAGE_EFFECT",
            "DYNAMIC_LIFE_STAGE_EFFECT",
            "CHANGED_LIFE_STAGE_EFFECT",
        )
    for effect in transformed_effects:
        direction = transformed_effect_directions.get(
            str(effect.value),
            OutcomeEvidenceDirection.CONDITIONAL,
        )
        add(
            f"useful-{effect.id.removeprefix('fact-')}",
            direction,
            (
                OutcomeEvidenceWeight.PRIMARY
                if direction
                in {
                    OutcomeEvidenceDirection.FAVORABLE,
                    OutcomeEvidenceDirection.ADVERSE,
                }
                else OutcomeEvidenceWeight.SUPPORTING
            ),
            "用神之变爻空、破、墓绝或生旺已按变爻自身旺衰与日辰支持求值。",
            [effect],
        )

    for effect in facts_for(selected_line, "CHANGED_TO_OFFICIAL_EFFECT"):
        direction = {
            "adverse_changed_to_official": OutcomeEvidenceDirection.ADVERSE,
            "conflict_with_return_generation": OutcomeEvidenceDirection.CONDITIONAL,
            "context_only": OutcomeEvidenceDirection.CONTEXT,
        }[str(effect.value)]
        add(
            f"useful-{effect.id.removeprefix('fact-')}",
            direction,
            (
                OutcomeEvidenceWeight.PRIMARY
                if direction == OutcomeEvidenceDirection.ADVERSE
                else OutcomeEvidenceWeight.SUPPORTING
            ),
            "化鬼已按该爻是否为用神或元神、以及是否同时回头生求值。",
            [effect],
        )

    selected_interactions = (
        []
        if is_hidden or is_changed
        else facts_for(
            selected_line,
            "DAY_BREAK",
            "MONTH_COMBINE",
            "DAY_COMBINE",
            "RETURN_COMBINE",
            "RETURN_CLASH",
        )
    )
    for fact in selected_interactions:
        if fact.type == "DAY_BREAK":
            direction = OutcomeEvidenceDirection.ADVERSE
            weight = OutcomeEvidenceWeight.PRIMARY
            description = "用神休囚静爻被日冲成日破，是不利主证。"
        elif (
            fact.type in {"MONTH_COMBINE", "DAY_COMBINE"}
            and fact.evidence.get("effect") == "言克不言合"
        ):
            direction = OutcomeEvidenceDirection.ADVERSE
            weight = OutcomeEvidenceWeight.PRIMARY
            description = "用神与日月虽成六合，但无他处生扶且合中受克，依原文言克不言合。"
        elif (
            fact.type in {"MONTH_COMBINE", "DAY_COMBINE"}
            and context.category in {"诉讼", "词讼"}
        ):
            direction = OutcomeEvidenceDirection.ADVERSE
            weight = OutcomeEvidenceWeight.PRIMARY
            description = "讼狱之占逢合主冤仇难解、事体缠绵，作为不利主证。"
        elif (
            fact.type in {"MONTH_COMBINE", "DAY_COMBINE"}
            and context.category == "胎产"
        ):
            direction = OutcomeEvidenceDirection.CONDITIONAL
            weight = OutcomeEvidenceWeight.SUPPORTING
            description = "胎产之占逢合，孕则安而产则难；问题未细分时只作条件证据。"
        elif fact.type in {"MONTH_COMBINE", "DAY_COMBINE"} and (
            fact.evidence.get("effect") == "合起"
        ):
            direction = OutcomeEvidenceDirection.FAVORABLE
            weight = OutcomeEvidenceWeight.SUPPORTING
            description = "静用神得合起，作为有利辅证。"
        else:
            direction = OutcomeEvidenceDirection.CONDITIONAL
            weight = OutcomeEvidenceWeight.SUPPORTING
            description = "用神受冲合牵制，属于先后与应期条件，不能单独定吉凶。"
        add(
            f"useful-{fact.type.lower().replace('_', '-')}",
            direction,
            weight,
            description,
            [fact],
        )

    primary_harmony = next(
        (fact for fact in facts if fact.type == "PRIMARY_SIX_HARMONY"),
        None,
    )
    if primary_harmony is not None:
        if context.category in {"诉讼", "词讼"}:
            direction = OutcomeEvidenceDirection.ADVERSE
            weight = OutcomeEvidenceWeight.PRIMARY
            description = "讼狱占得六合，依原文主冤仇难解、事体缠绵。"
        elif context.category == "胎产":
            direction = OutcomeEvidenceDirection.CONDITIONAL
            weight = OutcomeEvidenceWeight.SUPPORTING
            description = "胎产逢六合，孕安而产难，未细分所问时保留条件。"
        elif strength_level in _STRONG_LEVELS or day_relation in {
            "日辰生爻",
            "比扶",
        }:
            direction = OutcomeEvidenceDirection.FAVORABLE
            weight = OutcomeEvidenceWeight.SUPPORTING
            description = "用神有力而卦逢六合，作为和合有利辅证。"
        else:
            direction = OutcomeEvidenceDirection.CONTEXT
            weight = OutcomeEvidenceWeight.SUPPORTING
            description = "卦逢六合但用神未见有力，只记录和合背景，不独断吉。"
        add(
            "primary-six-harmony",
            direction,
            weight,
            description,
            [primary_harmony],
            source_ids=("020_六合章:p0022",),
        )

    clash_to_harmony = next(
        (fact for fact in facts if fact.type == "CLASH_TO_HARMONY"),
        None,
    )
    if clash_to_harmony is not None:
        if context.category in {"诉讼", "词讼"}:
            direction = OutcomeEvidenceDirection.ADVERSE
            description = "六冲变六合本主先难后成，但讼狱逢合为难解，依门类例外作不利。"
            sources = (
                "020_六合章:p0019",
                "020_六合章:p0022",
            )
        elif context.category == "胎产":
            direction = OutcomeEvidenceDirection.CONDITIONAL
            description = "六冲变六合遇胎产须区分孕与产，只作条件证据。"
            sources = (
                "020_六合章:p0019",
                "020_六合章:p0022",
            )
        else:
            direction = OutcomeEvidenceDirection.FAVORABLE
            description = "主卦六冲而变六合，依原文不看用神旺衰，主散而复聚、先否后泰。"
            sources = ("020_六合章:p0019",)
        add(
            "clash-to-harmony",
            direction,
            (
                OutcomeEvidenceWeight.SUPPORTING
                if direction == OutcomeEvidenceDirection.CONDITIONAL
                else OutcomeEvidenceWeight.PRIMARY
            ),
            description,
            [clash_to_harmony],
            source_ids=sources,
        )

    activation_directions = {
        "activated_favorable": OutcomeEvidenceDirection.FAVORABLE,
        "activated_adverse": OutcomeEvidenceDirection.ADVERSE,
        "activated_context": OutcomeEvidenceDirection.CONTEXT,
        "not_scattered": OutcomeEvidenceDirection.CONTEXT,
        "conditional_possible_scatter": OutcomeEvidenceDirection.CONDITIONAL,
    }
    for effect in (
        []
        if is_changed
        else facts_for(
            selected_line,
            "DARK_MOVEMENT_EFFECT",
            "MOVING_DAY_CLASH_EFFECT",
        )
    ):
        direction = activation_directions[str(effect.value)]
        add(
            f"useful-{effect.id.removeprefix('fact-')}",
            direction,
            (
                OutcomeEvidenceWeight.PRIMARY
                if direction
                in {
                    OutcomeEvidenceDirection.FAVORABLE,
                    OutcomeEvidenceDirection.ADVERSE,
                }
                else OutcomeEvidenceWeight.SUPPORTING
            ),
            "日冲的作用已按爻之旺衰和用、元、忌、仇角色求值，不把暗动或动散名称机械定吉凶。",
            [effect],
        )

    effect_specs = {
        "HEXAGRAM_CHANGE_EFFECT": {
            "favorable": (
                OutcomeEvidenceDirection.FAVORABLE,
                OutcomeEvidenceWeight.PRIMARY,
            ),
            "adverse_overrides_useful_strength": (
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.PRIMARY,
            ),
            "neutral_outward_control": (
                OutcomeEvidenceDirection.CONTEXT,
                OutcomeEvidenceWeight.SUPPORTING,
            ),
            "conditional_outward_generation": (
                OutcomeEvidenceDirection.CONTEXT,
                OutcomeEvidenceWeight.SUPPORTING,
            ),
            "neutral": (
                OutcomeEvidenceDirection.CONTEXT,
                OutcomeEvidenceWeight.SUPPORTING,
            ),
        },
        "THREE_HARMONY_EFFECT": {
            "generates_useful": (
                OutcomeEvidenceDirection.FAVORABLE,
                OutcomeEvidenceWeight.PRIMARY,
            ),
            "useful_in_group_detained": (
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.PRIMARY,
            ),
            "useful_in_group_context": (
                OutcomeEvidenceDirection.CONTEXT,
                OutcomeEvidenceWeight.SUPPORTING,
            ),
            "overcomes_useful": (
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.PRIMARY,
            ),
            "generates_world": (
                OutcomeEvidenceDirection.FAVORABLE,
                OutcomeEvidenceWeight.PRIMARY,
            ),
            "world_in_group": (
                OutcomeEvidenceDirection.FAVORABLE,
                OutcomeEvidenceWeight.SUPPORTING,
            ),
            "overcomes_world": (
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.PRIMARY,
            ),
        },
        "THREE_HARMONY_WORLD_EFFECT": {
            "generates_world": (
                OutcomeEvidenceDirection.FAVORABLE,
                OutcomeEvidenceWeight.PRIMARY,
            ),
            "world_in_group": (
                OutcomeEvidenceDirection.FAVORABLE,
                OutcomeEvidenceWeight.SUPPORTING,
            ),
            "overcomes_world": (
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.PRIMARY,
            ),
        },
        "REVERSE_CHANT_EFFECT": {
            "adverse_return_harm": (
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.PRIMARY,
            ),
            "conditional_success": (
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.SUPPORTING,
            ),
            "conditional_reversal": (
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.SUPPORTING,
            ),
        },
        "REPEATED_CHANT_EFFECT": {
            "conditional_release_when_clashed": (
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.SUPPORTING,
            ),
            "adverse_stagnation": (
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.SUPPORTING,
            ),
        },
        "GHOST_TOMB": {
            "adverse_real_tomb": (
                OutcomeEvidenceDirection.ADVERSE,
                OutcomeEvidenceWeight.PRIMARY,
            ),
            "conditional_opened_or_supported": (
                OutcomeEvidenceDirection.CONDITIONAL,
                OutcomeEvidenceWeight.SUPPORTING,
            ),
        },
    }
    for effect_type, values in effect_specs.items():
        for effect in (
            fact for fact in facts if fact.type == effect_type
        ):
            if effect_type in {
                "THREE_HARMONY_EFFECT",
                "THREE_HARMONY_WORLD_EFFECT",
            } and (
                effect.evidence.get("harmony_status") != "formed"
            ):
                continue
            if (
                effect_type == "THREE_HARMONY_EFFECT"
                and effect.evidence.get("useful_line") not in {
                    None,
                    selected_line,
                }
            ):
                continue
            if (
                effect_type in {
                    "REVERSE_CHANT_EFFECT",
                    "REPEATED_CHANT_EFFECT",
                }
                and effect.line not in {None, selected_line}
            ):
                continue
            if (
                effect_type == "GHOST_TOMB"
                and effect.evidence.get("perspective") == "proxy"
                and effect.line != selected_line
            ):
                continue
            direction, weight = values.get(
                str(effect.value),
                (
                    OutcomeEvidenceDirection.CONTEXT,
                    OutcomeEvidenceWeight.SUPPORTING,
                ),
            )
            if (
                unrooted
                and effect_type
                in {
                    "THREE_HARMONY_EFFECT",
                    "THREE_HARMONY_WORLD_EFFECT",
                }
                and direction == OutcomeEvidenceDirection.FAVORABLE
            ):
                direction = OutcomeEvidenceDirection.CONTEXT
                weight = OutcomeEvidenceWeight.SUPPORTING
            add(
                f"effective-{effect.id.removeprefix('fact-')}",
                direction,
                weight,
                "该结论来自原文注册规则在本卦前提下的显式效力求值。",
                [effect],
            )

    facts_by_id = {fact.id: fact for fact in facts}
    directional_snapshot = [
        item
        for item in evidence
        if item.direction
        in {
            OutcomeEvidenceDirection.FAVORABLE,
            OutcomeEvidenceDirection.ADVERSE,
        }
    ]
    for six_god in (
        fact
        for fact in facts
        if fact.type == "SIX_GOD" and fact.line is not None
    ):
        line_evidence = [
            item
            for item in directional_snapshot
            if any(
                facts_by_id.get(fact_id) is not None
                and facts_by_id[fact_id].line == six_god.line
                for fact_id in item.fact_ids
            )
        ]
        directions = {item.direction for item in line_evidence}
        spirit = str(six_god.value)
        if (
            spirit == "青龙"
            and OutcomeEvidenceDirection.FAVORABLE in directions
        ):
            direction = OutcomeEvidenceDirection.FAVORABLE
            description = "青龙临已有利之爻，只附和并加强既有吉象，不独立造吉。"
        elif spirit in {"白虎", "螣蛇"} and (
            OutcomeEvidenceDirection.ADVERSE in directions
        ):
            direction = OutcomeEvidenceDirection.ADVERSE
            description = f"{spirit}临已不利之爻，只附和并加强既有凶象，不独立造凶。"
        elif spirit in {"玄武", "朱雀"} and six_god.line == selected_line:
            direction = OutcomeEvidenceDirection.CONTEXT
            description = (
                "玄武仅提示盗贼隐昧事象，不独立定吉凶。"
                if spirit == "玄武"
                else "朱雀仅提示口舌是非事象，不独立定吉凶。"
            )
        else:
            continue
        supporting_facts = [
            facts_by_id[fact_id]
            for item in line_evidence
            for fact_id in item.fact_ids
            if fact_id in facts_by_id
        ]
        add(
            f"six-god-{spirit}-l{six_god.line}",
            direction,
            OutcomeEvidenceWeight.SUPPORTING,
            description,
            [six_god, *supporting_facts],
            source_ids=(
                "019_六神章:p0002",
                "019_六神章:p0003",
            ),
        )

    directional = {
        item.direction
        for item in evidence
        if item.direction
        in {
            OutcomeEvidenceDirection.FAVORABLE,
            OutcomeEvidenceDirection.ADVERSE,
        }
    }
    if len(directional) > 1:
        facts_by_id = {fact.id: fact for fact in facts}
        balancing_facts = [
            facts_by_id[fact_id]
            for item in evidence
            if item.direction in directional
            for fact_id in item.fact_ids
            if fact_id in facts_by_id
        ]
        add(
            "generation-control-balance",
            OutcomeEvidenceDirection.CONTEXT,
            OutcomeEvidenceWeight.PRIMARY,
            "本卦生克两见，须按用神有根、元忌有力无力及克少生多分主次，不作票数相加。",
            list({fact.id: fact for fact in balancing_facts}.values()),
            source_ids=("013_克处逢生章:p0001",),
        )
    primary_directional = {
        item.direction
        for item in evidence
        if item.weight == OutcomeEvidenceWeight.PRIMARY
        and item.direction
        in {
            OutcomeEvidenceDirection.FAVORABLE,
            OutcomeEvidenceDirection.ADVERSE,
        }
    }
    has_conditions = any(
        item.direction == OutcomeEvidenceDirection.CONDITIONAL
        for item in evidence
    )
    if unrooted and directional == {OutcomeEvidenceDirection.ADVERSE}:
        guardrail = OutcomeGuardrail.ADVERSE_ONLY
    elif len(directional) > 1:
        guardrail = OutcomeGuardrail.MIXED
    elif (
        directional == {OutcomeEvidenceDirection.FAVORABLE}
        and primary_directional
        and not has_conditions
    ):
        guardrail = OutcomeGuardrail.FAVORABLE_ONLY
    elif (
        directional == {OutcomeEvidenceDirection.ADVERSE}
        and primary_directional
        and not has_conditions
    ):
        guardrail = OutcomeGuardrail.ADVERSE_ONLY
    else:
        guardrail = OutcomeGuardrail.ABSTAIN

    limitations = []
    if guardrail == OutcomeGuardrail.MIXED:
        limitations.append("正反证据并见，须依有根、动静、有力无力与克少生多分主次。")
    if has_conditions:
        limitations.append("存在空、破、冲、合或元忌效力条件，裁决层不作机械加减分。")
    return OutcomeAnalysis(
        guardrail=guardrail,
        evidence=tuple(evidence),
        limitations=tuple(limitations),
    )
