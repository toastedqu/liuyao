from __future__ import annotations

from app.rules.elements import generates, overcomes
from app.rules.models import (
    RuleContext,
    RuleFact,
    UsefulGodSelection,
)


def god_role_facts(
    context: RuleContext,
    useful: UsefulGodSelection,
) -> list[RuleFact]:
    facts: list[RuleFact] = []
    if useful.useful_element is None:
        return facts

    selected_candidate = (
        useful.candidates[0]
        if useful.status == "selected" and useful.candidates
        else None
    )
    if selected_candidate is None and useful.status == "selected":
        source = next(
            (
                source_id
                for source_id in useful.source_ids
                if source_id.startswith("035_")
            ),
            useful.source_ids[0],
        )
        facts.append(
            RuleFact(
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
                rule_source=source,
            )
        )

    for line in context.lines:
        if selected_candidate and line.position == selected_candidate.line:
            facts.append(
                RuleFact(
                    id=f"fact-useful-god-l{line.position}",
                    type="USEFUL_GOD",
                    line=line.position,
                    value=True,
                    evidence={
                        "role": selected_candidate.role,
                        "relative": selected_candidate.relative.value
                        if selected_candidate.relative
                        else None,
                        "branch": selected_candidate.branch,
                        "element": selected_candidate.element.value
                        if selected_candidate.element
                        else None,
                    },
                    rule_source=useful.source_ids[0],
                )
            )
        if useful.yuan_element is line.element:
            facts.append(
                RuleFact(
                    id=f"fact-yuan-god-l{line.position}",
                    type="YUAN_GOD",
                    line=line.position,
                    value=True,
                    evidence={
                        "line_element": line.element.value,
                        "useful_element": useful.useful_element.value,
                        "moving": line.is_moving,
                    },
                    rule_source="009_用神、元神、忌神、仇神章:p0001",
                )
            )
        if useful.taboo_element is line.element:
            facts.append(
                RuleFact(
                    id=f"fact-taboo-god-l{line.position}",
                    type="TABOO_GOD",
                    line=line.position,
                    value=True,
                    evidence={
                        "line_element": line.element.value,
                        "useful_element": useful.useful_element.value,
                        "moving": line.is_moving,
                    },
                    rule_source="009_用神、元神、忌神、仇神章:p0001",
                )
            )
        if useful.enemy_element is line.element:
            facts.append(
                RuleFact(
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
                    rule_source="009_用神、元神、忌神、仇神章:p0001",
                )
            )

        if line.is_moving and line.position != useful.selected_line:
            if generates(line.element, useful.useful_element):
                facts.append(
                    RuleFact(
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
                        rule_source="014_动静生克章:p0001",
                    )
                )
            elif overcomes(line.element, useful.useful_element):
                facts.append(
                    RuleFact(
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
                        rule_source="014_动静生克章:p0001",
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
            RuleFact(
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
                rule_source="035_飞伏神章:p0001",
            )
        )

    if len(useful.candidates) > 1:
        facts.append(
            RuleFact(
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
                    "scores": [candidate.score for candidate in useful.candidates],
                },
                rule_source="039_两现章:p0001",
            )
        )
    return facts
