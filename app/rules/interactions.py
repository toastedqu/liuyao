from __future__ import annotations

from itertools import combinations

from app.rules.elements import (
    ADVANCE_PAIRS,
    CLASH,
    COMBINE,
    RETREAT_PAIRS,
    is_punishment,
    relation_between,
)
from app.rules.models import RuleContext, RuleFact


def interaction_facts(context: RuleContext) -> list[RuleFact]:
    facts: list[RuleFact] = []

    for first, second in combinations(context.lines, 2):
        if not (first.is_moving or second.is_moving):
            continue
        positions = tuple(sorted((first.position, second.position)))
        suffix = f"l{positions[0]}-l{positions[1]}"
        if CLASH[first.branch] == second.branch:
            facts.append(
                RuleFact(
                    id=f"fact-line-clash-{suffix}",
                    type="LINE_CLASH",
                    related_lines=positions,
                    value=True,
                    evidence={"branches": [first.branch, second.branch]},
                    rule_source="022_六冲章:p0001",
                )
            )
        if COMBINE[first.branch] == second.branch and first.is_moving and second.is_moving:
            facts.append(
                RuleFact(
                    id=f"fact-line-combine-{suffix}",
                    type="LINE_COMBINE",
                    related_lines=positions,
                    value=True,
                    evidence={"branches": [first.branch, second.branch]},
                    rule_source="020_六合章:p0001",
                )
            )
        if is_punishment(first.branch, second.branch):
            facts.append(
                RuleFact(
                    id=f"fact-line-punishment-{suffix}",
                    type="LINE_PUNISHMENT",
                    related_lines=positions,
                    value=True,
                    evidence={"branches": [first.branch, second.branch]},
                    rule_source="023_三刑章:p0001",
                )
            )

    for line in context.lines:
        changed = line.changed
        if not line.is_moving or changed is None:
            continue
        relation = relation_between(changed.element, line.element)
        facts.append(
            RuleFact(
                id=f"fact-changed-relation-l{line.position}",
                type="CHANGED_ELEMENT_RELATION",
                line=line.position,
                value=relation,
                evidence={
                    "original_branch": line.branch,
                    "original_element": line.element.value,
                    "changed_branch": changed.branch,
                    "changed_element": changed.element.value,
                },
                rule_source="015_动变生克冲合章:p0001",
            )
        )
        if relation == "生":
            facts.append(
                RuleFact(
                    id=f"fact-return-generate-l{line.position}",
                    type="RETURN_GENERATE",
                    line=line.position,
                    value=True,
                    evidence={
                        "changed_element": changed.element.value,
                        "original_element": line.element.value,
                    },
                    rule_source="015_动变生克冲合章:p0001",
                )
            )
        elif relation == "克":
            facts.append(
                RuleFact(
                    id=f"fact-return-overcome-l{line.position}",
                    type="RETURN_OVERCOME",
                    line=line.position,
                    value=True,
                    evidence={
                        "changed_element": changed.element.value,
                        "original_element": line.element.value,
                    },
                    rule_source="015_动变生克冲合章:p0001",
                )
            )
        if CLASH[line.branch] == changed.branch:
            facts.append(
                RuleFact(
                    id=f"fact-return-clash-l{line.position}",
                    type="RETURN_CLASH",
                    line=line.position,
                    value=True,
                    evidence={"original_branch": line.branch, "changed_branch": changed.branch},
                    rule_source="022_六冲章:p0002",
                )
            )
        if COMBINE[line.branch] == changed.branch:
            facts.append(
                RuleFact(
                    id=f"fact-return-combine-l{line.position}",
                    type="RETURN_COMBINE",
                    line=line.position,
                    value=True,
                    evidence={"original_branch": line.branch, "changed_branch": changed.branch},
                    rule_source="020_六合章:p0002",
                )
            )
        pair = (line.branch, changed.branch)
        if pair in ADVANCE_PAIRS:
            facts.append(
                RuleFact(
                    id=f"fact-advance-l{line.position}",
                    type="ADVANCE",
                    line=line.position,
                    value=True,
                    evidence={"original_branch": line.branch, "changed_branch": changed.branch},
                    rule_source="036_进神退神章:p0001",
                )
            )
        elif pair in RETREAT_PAIRS:
            facts.append(
                RuleFact(
                    id=f"fact-retreat-l{line.position}",
                    type="RETREAT",
                    line=line.position,
                    value=True,
                    evidence={"original_branch": line.branch, "changed_branch": changed.branch},
                    rule_source="036_进神退神章:p0001",
                )
            )

    return facts
