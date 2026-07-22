from __future__ import annotations

from itertools import combinations

from app.rules.elements import (
    ADVANCE_PAIRS,
    CLASH,
    COMBINE,
    EXTINCTION,
    GROWTH,
    HARM,
    PROSPERITY,
    RETREAT_PAIRS,
    TOMB,
    is_punishment,
    relation_between,
)
from app.rules.models import Relative, RuleContext, RuleFact
from app.rules.registry import make_fact


def interaction_facts(context: RuleContext) -> list[RuleFact]:
    facts: list[RuleFact] = []

    for first, second in combinations(context.lines, 2):
        positions = tuple(sorted((first.position, second.position)))
        suffix = f"l{positions[0]}-l{positions[1]}"
        facts.append(
            make_fact(
                "ZSBY-014-LINE-ELEMENT-RELATION",
                id=f"fact-line-element-relation-{suffix}",
                type="LINE_ELEMENT_RELATION",
                related_lines=positions,
                value=relation_between(first.element, second.element),
                evidence={
                    "first_line": first.position,
                    "first_element": first.element.value,
                    "first_moving": first.is_moving,
                    "second_line": second.position,
                    "second_element": second.element.value,
                    "second_moving": second.is_moving,
                },
                source_id=(
                    "014_动静生克章:p0004"
                    if first.is_moving or second.is_moving
                    else "014_动静生克章:p0001"
                ),
            )
        )
        if CLASH[first.branch] == second.branch:
            facts.append(
                make_fact(
                    "ZSBY-022-CLASH",
                    id=f"fact-branch-clash-pair-{suffix}",
                    type="BRANCH_CLASH_PAIR",
                    related_lines=positions,
                    value=True,
                    evidence={
                        "branches": [first.branch, second.branch],
                        "active": first.is_moving or second.is_moving,
                    },
                    source_id="022_六冲章:p0001",
                )
            )
        if (
            CLASH[first.branch] == second.branch
            and (first.is_moving or second.is_moving)
        ):
            facts.append(
                make_fact(
                    "ZSBY-022-CLASH",
                    id=f"fact-line-clash-{suffix}",
                    type="LINE_CLASH",
                    related_lines=positions,
                    value=True,
                    evidence={"branches": [first.branch, second.branch]},
                    source_id="022_六冲章:p0005",
                )
            )
        if COMBINE[first.branch] == second.branch:
            facts.append(
                make_fact(
                    "ZSBY-020-COMBINE",
                    id=f"fact-branch-combine-pair-{suffix}",
                    type="BRANCH_COMBINE_PAIR",
                    related_lines=positions,
                    value=True,
                    evidence={
                        "branches": [first.branch, second.branch],
                        "active": first.is_moving and second.is_moving,
                    },
                    source_id="020_六合章:p0001",
                )
            )
        if (
            COMBINE[first.branch] == second.branch
            and first.is_moving
            and second.is_moving
        ):
            facts.append(
                make_fact(
                    "ZSBY-020-COMBINE",
                    id=f"fact-line-combine-{suffix}",
                    type="LINE_COMBINE",
                    related_lines=positions,
                    value=True,
                    evidence={"branches": [first.branch, second.branch]},
                    source_id="020_六合章:p0004",
                )
            )
        if is_punishment(first.branch, second.branch):
            facts.append(
                make_fact(
                    "ZSBY-023-PUNISHMENT",
                    id=f"fact-branch-punishment-pair-{suffix}",
                    type="BRANCH_PUNISHMENT_PAIR",
                    related_lines=positions,
                    value=True,
                    evidence={
                        "branches": [first.branch, second.branch],
                        "active": first.is_moving or second.is_moving,
                    },
                    source_id="023_三刑章:p0001",
                )
            )
        if (
            is_punishment(first.branch, second.branch)
            and (first.is_moving or second.is_moving)
        ):
            facts.append(
                make_fact(
                    "ZSBY-023-PUNISHMENT",
                    id=f"fact-line-punishment-{suffix}",
                    type="LINE_PUNISHMENT",
                    related_lines=positions,
                    value=True,
                    evidence={"branches": [first.branch, second.branch]},
                    source_id="023_三刑章:p0001",
                )
            )
        if HARM[first.branch] == second.branch:
            facts.append(
                make_fact(
                    "ZSBY-024-HARM-DISCARDED",
                    id=f"fact-line-harm-{suffix}",
                    type="LINE_HARM",
                    related_lines=positions,
                    value=True,
                    evidence={
                        "branches": [first.branch, second.branch],
                        "predictive_weight": 0,
                        "discarded_by_source": True,
                    },
                    source_id="024_六害章:p0001",
                )
            )

    for line in context.lines:
        changed = line.changed
        if not line.is_moving or changed is None:
            continue
        relation = relation_between(changed.element, line.element)
        facts.append(
            make_fact(
                "ZSBY-015-CHANGED-LINE-RELATION",
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
                source_id="015_动变生克冲合章:p0001",
            )
        )
        transformed_stages = {
            "长生": GROWTH[line.element],
            "帝旺": PROSPERITY[line.element],
            "墓": TOMB[line.element],
            "绝": EXTINCTION[line.element],
        }
        transformed_stage = next(
            (
                name
                for name, branch in transformed_stages.items()
                if branch == changed.branch
            ),
            None,
        )
        if transformed_stage is not None:
            facts.append(
                make_fact(
                    "ZSBY-030-LIFE-STAGE",
                    id=f"fact-change-to-life-stage-{transformed_stage}-l{line.position}",
                    type="CHANGED_LIFE_STAGE",
                    line=line.position,
                    value=transformed_stage,
                    evidence={
                        "actor": "changed",
                        "basis": "original_line_element",
                        "original_element": line.element.value,
                        "changed_branch": changed.branch,
                    },
                    source_id="030_生旺墓绝章:p0004",
                )
            )
        if changed.relative is Relative.OFFICIAL:
            facts.append(
                make_fact(
                    "ZSBY-031-CHANGED-OMEN",
                    id=f"fact-changed-to-official-l{line.position}",
                    type="CHANGED_TO_OFFICIAL",
                    line=line.position,
                    value=True,
                    evidence={
                        "original_relative": line.relative.value,
                        "changed_relative": changed.relative.value,
                        "changed_branch": changed.branch,
                    },
                    source_id="031_各门类题头总注章:p0004",
                )
            )
        if relation == "生":
            facts.append(
                make_fact(
                    "ZSBY-015-CHANGED-LINE-RELATION",
                    id=f"fact-return-generate-l{line.position}",
                    type="RETURN_GENERATE",
                    line=line.position,
                    value=True,
                    evidence={
                        "changed_element": changed.element.value,
                        "original_element": line.element.value,
                    },
                    source_id="015_动变生克冲合章:p0003",
                )
            )
        elif relation == "克":
            facts.append(
                make_fact(
                    "ZSBY-015-CHANGED-LINE-RELATION",
                    id=f"fact-return-overcome-l{line.position}",
                    type="RETURN_OVERCOME",
                    line=line.position,
                    value=True,
                    evidence={
                        "changed_element": changed.element.value,
                        "original_element": line.element.value,
                    },
                    source_id="015_动变生克冲合章:p0003",
                )
            )
        if CLASH[line.branch] == changed.branch:
            facts.append(
                make_fact(
                    "ZSBY-015-CHANGED-LINE-RELATION",
                    id=f"fact-return-clash-l{line.position}",
                    type="RETURN_CLASH",
                    line=line.position,
                    value=True,
                    evidence={"original_branch": line.branch, "changed_branch": changed.branch},
                    source_id="015_动变生克冲合章:p0001",
                )
            )
        if COMBINE[line.branch] == changed.branch:
            facts.append(
                make_fact(
                    "ZSBY-015-CHANGED-LINE-RELATION",
                    id=f"fact-return-combine-l{line.position}",
                    type="RETURN_COMBINE",
                    line=line.position,
                    value=True,
                    evidence={"original_branch": line.branch, "changed_branch": changed.branch},
                    source_id="015_动变生克冲合章:p0001",
                )
            )
        pair = (line.branch, changed.branch)
        if pair in ADVANCE_PAIRS:
            facts.append(
                make_fact(
                    "ZSBY-036-ADVANCE",
                    id=f"fact-advance-l{line.position}",
                    type="ADVANCE",
                    line=line.position,
                    value=True,
                    evidence={"original_branch": line.branch, "changed_branch": changed.branch},
                    source_id="036_进神退神章:p0002",
                )
            )
        elif pair in RETREAT_PAIRS:
            facts.append(
                make_fact(
                    "ZSBY-036-RETREAT",
                    id=f"fact-retreat-l{line.position}",
                    type="RETREAT",
                    line=line.position,
                    value=True,
                    evidence={"original_branch": line.branch, "changed_branch": changed.branch},
                    source_id="036_进神退神章:p0003",
                )
            )

    return facts
