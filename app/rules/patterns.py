from __future__ import annotations

from app.rules.elements import CLASH, THREE_HARMONIES
from app.rules.models import RuleContext, RuleFact


def pattern_facts(context: RuleContext) -> list[RuleFact]:
    facts: list[RuleFact] = []

    flags = (
        ("PRIMARY_SIX_CLASH", context.primary_is_six_clash, "022_六冲章:p0001"),
        ("PRIMARY_SIX_HARMONY", context.primary_is_six_harmony, "020_六合章:p0001"),
        ("CHANGED_SIX_CLASH", context.changed_is_six_clash, "022_六冲章:p0001"),
        ("CHANGED_SIX_HARMONY", context.changed_is_six_harmony, "020_六合章:p0001"),
        (
            "WANDERING_SOUL",
            context.primary_is_wandering_soul,
            "033_归魂游魂章:p0001",
        ),
        (
            "RETURNING_SOUL",
            context.primary_is_returning_soul,
            "033_归魂游魂章:p0002",
        ),
    )
    for fact_type, enabled, source in flags:
        if enabled:
            facts.append(
                RuleFact(
                    id=f"fact-{fact_type.lower().replace('_', '-')}",
                    type=fact_type,
                    value=True,
                    evidence={
                        "primary_hexagram": context.primary_hexagram,
                        "changed_hexagram": context.changed_hexagram,
                    },
                    rule_source=source,
                )
            )

    moving_positions = tuple(line.position for line in context.lines if line.is_moving)
    if len(moving_positions) == 1:
        facts.append(
            RuleFact(
                id=f"fact-single-moving-l{moving_positions[0]}",
                type="SINGLE_MOVING",
                line=moving_positions[0],
                value=True,
                evidence={"moving_positions": list(moving_positions)},
                rule_source="038_独发章:p0001",
            )
        )

    branch_to_lines: dict[str, list[int]] = {}
    moving_branches: set[str] = set()
    for line in context.lines:
        branch_to_lines.setdefault(line.branch, []).append(line.position)
        if line.is_moving:
            moving_branches.add(line.branch)
        if line.is_moving and line.changed:
            branch_to_lines.setdefault(line.changed.branch, []).append(line.position)
            moving_branches.add(line.changed.branch)

    for trio, element in THREE_HARMONIES.items():
        present = [branch for branch in trio if branch in branch_to_lines]
        if len(present) != 3:
            continue
        active_count = sum(branch in moving_branches for branch in trio)
        if active_count < 2:
            continue
        related = tuple(
            sorted({position for branch in trio for position in branch_to_lines[branch]})
        )
        facts.append(
            RuleFact(
                id=f"fact-three-harmony-{element.value}",
                type="THREE_HARMONY",
                related_lines=related,
                value=element.value,
                evidence={
                    "branches": list(trio),
                    "active_branch_count": active_count,
                },
                rule_source="021_三合章:p0001",
            )
        )

    primary_inner = tuple(line.branch for line in context.lines[:3])
    primary_outer = tuple(line.branch for line in context.lines[3:])
    changed_inner = tuple(
        line.changed.branch if line.changed else line.branch for line in context.lines[:3]
    )
    changed_outer = tuple(
        line.changed.branch if line.changed else line.branch for line in context.lines[3:]
    )
    inner_reverses = all(CLASH[a] == b for a, b in zip(primary_inner, changed_inner))
    outer_reverses = all(CLASH[a] == b for a, b in zip(primary_outer, changed_outer))
    inner_repeats = primary_inner == changed_inner and any(
        line.is_moving for line in context.lines[:3]
    )
    outer_repeats = primary_outer == changed_outer and any(
        line.is_moving for line in context.lines[3:]
    )
    if inner_reverses or outer_reverses:
        facts.append(
            RuleFact(
                id="fact-reverse-chant",
                type="REVERSE_CHANT",
                value=True,
                evidence={"inner": inner_reverses, "outer": outer_reverses},
                rule_source="028_反伏章:p0001",
            )
        )
    if inner_repeats or outer_repeats:
        facts.append(
            RuleFact(
                id="fact-repeated-chant",
                type="REPEATED_CHANT",
                value=True,
                evidence={"inner": inner_repeats, "outer": outer_repeats},
                rule_source="028_反伏章:p0003",
            )
        )
    return facts

