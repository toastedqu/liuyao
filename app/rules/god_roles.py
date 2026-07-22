from __future__ import annotations

from app.rules.elements import generates, overcomes
from app.rules.models import (
    RuleContext,
    RuleFact,
    UsefulGodSelection,
)
from app.rules.registry import get_rule, make_fact


def god_role_facts(
    context: RuleContext,
    useful: UsefulGodSelection,
) -> list[RuleFact]:
    facts: list[RuleFact] = []
    if useful.useful_element is None:
        return facts
    mapping_sources = get_rule("ZSBY-008-USEFUL-MAPPING").source_ids
    mapping_source = next(
        (
            source_id
            for source_id in useful.source_ids
            if source_id in mapping_sources
        ),
        None,
    )
    if mapping_source is None:
        raise ValueError("用神选择缺少已注册的用神映射出处")

    candidates_by_line = {
        candidate.line: candidate
        for candidate in useful.candidates
        if candidate.line is not None
    }
    if not candidates_by_line and useful.status == "selected":
        calendar_source = next(
            (
                source_id
                for source_id in useful.source_ids
                if source_id.startswith("035_")
                and source_id in mapping_sources
            ),
            mapping_source,
        )
        facts.append(
            make_fact(
                "ZSBY-008-USEFUL-MAPPING",
                id="fact-useful-god-calendar",
                type="USEFUL_GOD",
                value=True,
                evidence={
                    "role": "calendar",
                    "relative": useful.useful_relative.value
                    if useful.useful_relative
                    else None,
                    "element": useful.useful_element.value,
                },
                source_id=calendar_source,
            )
        )

    for line in context.lines:
        candidate = candidates_by_line.get(line.position)
        if candidate is not None:
            facts.append(
                make_fact(
                    "ZSBY-008-USEFUL-MAPPING",
                    id=f"fact-useful-god-l{line.position}",
                    type="USEFUL_GOD",
                    line=line.position,
                    value=True,
                    evidence={
                        "role": candidate.role,
                        "relative": candidate.relative.value
                        if candidate.relative
                        else None,
                        "branch": candidate.branch,
                        "element": candidate.element.value
                        if candidate.element
                        else None,
                        "selected": line.position == useful.selected_line,
                    },
                    source_id=mapping_source,
                )
            )
        if useful.yuan_element is line.element:
            facts.append(
                make_fact(
                    "ZSBY-009-GOD-ROLES",
                    id=f"fact-yuan-god-l{line.position}",
                    type="YUAN_GOD",
                    line=line.position,
                    value=True,
                    evidence={
                        "line_element": line.element.value,
                        "useful_element": useful.useful_element.value,
                        "moving": line.is_moving,
                    },
                    source_id="009_用神、元神、忌神、仇神章:p0001",
                )
            )
        if useful.taboo_element is line.element:
            facts.append(
                make_fact(
                    "ZSBY-009-GOD-ROLES",
                    id=f"fact-taboo-god-l{line.position}",
                    type="TABOO_GOD",
                    line=line.position,
                    value=True,
                    evidence={
                        "line_element": line.element.value,
                        "useful_element": useful.useful_element.value,
                        "moving": line.is_moving,
                    },
                    source_id="009_用神、元神、忌神、仇神章:p0001",
                )
            )
        if useful.enemy_element is line.element:
            facts.append(
                make_fact(
                    "ZSBY-009-GOD-ROLES",
                    id=f"fact-enemy-god-l{line.position}",
                    type="ENEMY_GOD",
                    line=line.position,
                    value=True,
                    evidence={
                        "line_element": line.element.value,
                        "yuan_element": useful.yuan_element.value
                        if useful.yuan_element
                        else None,
                        "taboo_element": useful.taboo_element.value
                        if useful.taboo_element
                        else None,
                        "moving": line.is_moving,
                    },
                    source_id="009_用神、元神、忌神、仇神章:p0001",
                )
            )

        if line.is_moving and line.position != useful.selected_line:
            if generates(line.element, useful.useful_element):
                facts.append(
                    make_fact(
                        "ZSBY-014-LINE-ELEMENT-RELATION",
                        id=f"fact-moving-generates-useful-l{line.position}",
                        type="MOVING_GENERATES_USEFUL",
                        line=line.position,
                        related_lines=(useful.selected_line,)
                        if useful.selected_line
                        else (),
                        value=True,
                        evidence={
                            "moving_element": line.element.value,
                            "useful_element": useful.useful_element.value,
                        },
                        source_id="014_动静生克章:p0004",
                    )
                )
            elif overcomes(line.element, useful.useful_element):
                facts.append(
                    make_fact(
                        "ZSBY-014-LINE-ELEMENT-RELATION",
                        id=f"fact-moving-overcomes-useful-l{line.position}",
                        type="MOVING_OVERCOMES_USEFUL",
                        line=line.position,
                        related_lines=(useful.selected_line,)
                        if useful.selected_line
                        else (),
                        value=True,
                        evidence={
                            "moving_element": line.element.value,
                            "useful_element": useful.useful_element.value,
                        },
                        source_id="014_动静生克章:p0004",
                    )
                )

        spirit = line.hidden_spirit
        if spirit is None:
            continue
        if generates(line.element, spirit.element):
            relationship = "飞来生伏"
        elif overcomes(line.element, spirit.element):
            relationship = "飞来克伏"
        elif generates(spirit.element, line.element):
            relationship = "伏去生飞"
        elif overcomes(spirit.element, line.element):
            relationship = "伏来克飞"
        else:
            relationship = "飞伏比和"
        facts.append(
            make_fact(
                "ZSBY-035-HIDDEN-RELATION",
                id=f"fact-flying-hidden-relation-l{line.position}",
                type="FLYING_HIDDEN_RELATION",
                line=line.position,
                value=relationship,
                evidence={
                    "flying_branch": line.branch,
                    "flying_element": line.element.value,
                    "hidden_branch": spirit.branch,
                    "hidden_element": spirit.element.value,
                    "hidden_relative": spirit.relative.value,
                },
                source_id="035_飞伏神章:p0004",
            )
        )

    if len(useful.candidates) > 1:
        facts.append(
            make_fact(
                "ZSBY-039-DOUBLE-PRESENT",
                id="fact-useful-god-multiple",
                type="USEFUL_GOD_MULTIPLE",
                related_lines=tuple(
                    candidate.line
                    for candidate in useful.candidates
                    if candidate.line is not None
                ),
                value=len(useful.candidates),
                evidence={
                    "candidate_lines": [
                        candidate.line for candidate in useful.candidates
                    ],
                    "candidate_reasons": [
                        list(candidate.reasons) for candidate in useful.candidates
                    ],
                    "selected_line": useful.selected_line,
                    "status": useful.status,
                },
                source_id="039_两现章:p0002",
            )
        )
    return facts
