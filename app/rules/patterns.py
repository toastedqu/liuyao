from __future__ import annotations

from app.rules.elements import CLASH, THREE_HARMONIES, relation_between
from app.rules.models import RuleContext, RuleFact
from app.rules.registry import make_fact


def pattern_facts(
    context: RuleContext,
    prior_facts: tuple[RuleFact, ...] = (),
) -> list[RuleFact]:
    facts: list[RuleFact] = []
    has_moving = any(line.is_moving for line in context.lines)

    flags = (
        (
            "PRIMARY_SIX_CLASH",
            context.primary_is_six_clash,
            "ZSBY-022-CLASH",
            "022_六冲章:p0003",
        ),
        (
            "PRIMARY_SIX_HARMONY",
            context.primary_is_six_harmony,
            "ZSBY-020-COMBINE",
            "020_六合章:p0006",
        ),
        (
            "CHANGED_SIX_CLASH",
            has_moving and context.changed_is_six_clash,
            "ZSBY-022-CLASH",
            "022_六冲章:p0003",
        ),
        (
            "CHANGED_SIX_HARMONY",
            has_moving and context.changed_is_six_harmony,
            "ZSBY-020-COMBINE",
            "020_六合章:p0006",
        ),
        (
            "WANDERING_SOUL",
            context.primary_is_wandering_soul,
            "ZSBY-033-WANDERING-RETURNING",
            "033_归魂游魂章:p0001",
        ),
        (
            "RETURNING_SOUL",
            context.primary_is_returning_soul,
            "ZSBY-033-WANDERING-RETURNING",
            "033_归魂游魂章:p0002",
        ),
    )
    for fact_type, enabled, rule_id, source in flags:
        if enabled:
            facts.append(
                make_fact(
                    rule_id,
                    id=f"fact-{fact_type.lower().replace('_', '-')}",
                    type=fact_type,
                    value=True,
                    evidence={
                        "primary_hexagram": context.primary_hexagram,
                        "changed_hexagram": context.changed_hexagram,
                    },
                    source_id=source,
                )
            )

    if (
        has_moving
        and context.primary_is_six_clash
        and context.changed_is_six_harmony
    ):
        facts.append(
            make_fact(
                "ZSBY-020-COMBINE",
                id="fact-clash-to-harmony",
                type="CLASH_TO_HARMONY",
                value=True,
                evidence={
                    "primary_hexagram": context.primary_hexagram,
                    "changed_hexagram": context.changed_hexagram,
                    "meaning": "散而复聚、先否后泰",
                },
                source_id="020_六合章:p0019",
            )
        )

    moving_positions = tuple(line.position for line in context.lines if line.is_moving)
    if len(moving_positions) == 1:
        facts.append(
            make_fact(
                "ZSBY-038-SOLE-MOVING",
                id=f"fact-single-moving-l{moving_positions[0]}",
                type="SINGLE_MOVING",
                line=moving_positions[0],
                value=True,
                evidence={"moving_positions": list(moving_positions)},
                source_id="038_独发章:p0001",
            )
        )
    if len(moving_positions) == 5:
        static_position = next(
            line.position for line in context.lines if not line.is_moving
        )
        facts.append(
            make_fact(
                "ZSBY-038-SOLE-MOVING",
                id=f"fact-single-static-l{static_position}",
                type="SINGLE_STATIC",
                line=static_position,
                value=True,
                evidence={"moving_positions": list(moving_positions)},
                source_id="038_独发章:p0001",
            )
        )

    dark_lines = {
        fact.line
        for fact in prior_facts
        if fact.type == "DARK_MOVEMENT" and fact.line is not None
    }
    branch_sources: dict[str, list[dict[str, object]]] = {}
    lines_by_position = {line.position: line for line in context.lines}
    for line in context.lines:
        branch_sources.setdefault(line.branch, []).append(
            {
                "line": line.position,
                "actor": "primary",
                "active": line.is_moving or line.position in dark_lines,
            }
        )
        if line.is_moving and line.changed:
            branch_sources.setdefault(line.changed.branch, []).append(
                {
                    "line": line.position,
                    "actor": "changed",
                    "active": True,
                }
            )

    for trio, element in THREE_HARMONIES.items():
        primary_sources = {
            branch: [
                source
                for source in branch_sources.get(branch, [])
                if source["actor"] == "primary"
            ]
            for branch in trio
        }
        active_primary = [
            branch
            for branch, sources in primary_sources.items()
            if any(bool(source["active"]) for source in sources)
        ]
        present_primary = [
            branch for branch, sources in primary_sources.items() if sources
        ]
        formation_mode: str | None = None
        relevant_sources: list[dict[str, object]] = []
        calendar_completion: str | None = None

        if len(present_primary) == 3 and len(active_primary) == 3:
            formation_mode = "three_active_lines"
            relevant_sources = [
                source
                for branch in trio
                for source in primary_sources[branch]
                if bool(source["active"])
            ]
        elif len(present_primary) == 3 and len(active_primary) == 2:
            formation_mode = "two_active_one_static"
            relevant_sources = [
                source
                for branch in trio
                for source in primary_sources[branch]
            ]
        else:
            for scope, positions in (
                ("inner_changed", (1, 3)),
                ("outer_changed", (4, 6)),
            ):
                scoped_sources = [
                    source
                    for branch in trio
                    for source in branch_sources.get(branch, [])
                    if int(source["line"]) in positions
                    and (
                        source["actor"] == "changed"
                        or bool(source["active"])
                    )
                ]
                scoped_branches = {
                    branch
                    for branch in trio
                    if any(
                        source in scoped_sources
                        for source in branch_sources.get(branch, [])
                    )
                }
                positions_active = all(
                    lines_by_position[position].is_moving
                    or position in dark_lines
                    for position in positions
                )
                has_changed_source = any(
                    source["actor"] == "changed"
                    for source in scoped_sources
                )
                if (
                    positions_active
                    and has_changed_source
                    and scoped_branches == set(trio)
                ):
                    formation_mode = scope
                    relevant_sources = scoped_sources
                    break

        if formation_mode is None and len(active_primary) == 2:
            missing = [
                branch for branch in trio if branch not in active_primary
            ]
            calendar_completion = next(
                (
                    branch
                    for branch in missing
                    if branch in {
                        context.month_branch,
                        context.day_branch,
                    }
                ),
                None,
            )
            formation_mode = (
                "calendar_completion"
                if calendar_completion is not None
                else "virtual_pending"
            )
            relevant_sources = [
                source
                for branch in active_primary
                for source in primary_sources[branch]
                if bool(source["active"])
            ]

        if formation_mode is None:
            continue

        formed = formation_mode != "virtual_pending"
        present = list(
            dict.fromkeys(
                branch
                for branch in trio
                if any(
                    source in relevant_sources
                    for source in branch_sources.get(branch, [])
                )
            )
        )
        missing = [branch for branch in trio if branch not in present]
        active = list(active_primary)
        related = tuple(
            sorted({int(source["line"]) for source in relevant_sources})
        )
        relevant_actors = {
            (int(source["line"]), str(source["actor"]))
            for source in relevant_sources
        }
        blocker_ids: list[str] = []
        for fact in prior_facts:
            if fact.line is None:
                continue
            primary_relevant = (fact.line, "primary") in relevant_actors
            changed_relevant = (fact.line, "changed") in relevant_actors
            if primary_relevant and fact.type in {"旬空", "MONTH_BREAK"}:
                blocker_ids.append(fact.id)
            elif changed_relevant and fact.type in {
                "CHANGED_VOID",
                "CHANGED_MONTH_BREAK",
            }:
                blocker_ids.append(fact.id)
            elif primary_relevant and (
                fact.type == "LIFE_STAGE" and fact.value == "墓"
            ):
                blocker_ids.append(fact.id)
            elif changed_relevant and (
                fact.type == "CHANGED_LIFE_STAGE"
                and fact.value == "墓"
                and fact.evidence.get("actor") == "changed"
            ):
                blocker_ids.append(fact.id)
        status = (
            "blocked"
            if formed and blocker_ids
            else "formed"
            if formed
            else "virtual_pending"
        )
        fact_type = "THREE_HARMONY" if status == "formed" else "THREE_HARMONY_PENDING"
        fact_id = (
            f"fact-three-harmony-{element.value}"
            if fact_type == "THREE_HARMONY"
            else f"fact-three-harmony-pending-{element.value}"
        )
        facts.append(
            make_fact(
                "ZSBY-021-THREE-HARMONY",
                id=fact_id,
                type=fact_type,
                related_lines=related,
                value=element.value,
                evidence={
                    "branches": list(trio),
                    "present_branches": present,
                    "active_branches": active,
                    "active_branch_count": len(active),
                    "missing_branch": missing[0] if missing else None,
                    "calendar_completion": calendar_completion,
                    "formation_mode": formation_mode,
                    "status": status,
                    "blocker_fact_ids": blocker_ids,
                },
                source_id="021_三合章:p0009",
            )
        )

    if has_moving and context.changed_palace_element is not None:
        relation = relation_between(
            context.changed_palace_element,
            context.palace_element,
        )
        relation_name = {
            "生": "变来生我",
            "克": "变来克我",
            "受克": "我去克彼",
            "受生": "我去生彼",
            "比和": "比和",
        }[relation]
        facts.append(
            make_fact(
                "ZSBY-027-HEXAGRAM-CHANGE",
                id="fact-hexagram-change-relation",
                type="HEXAGRAM_CHANGE_RELATION",
                value=relation_name,
                evidence={
                    "primary_hexagram": context.primary_hexagram,
                    "primary_palace_element": context.palace_element.value,
                    "changed_hexagram": context.changed_hexagram,
                    "changed_palace_element": context.changed_palace_element.value,
                },
                source_id="027_卦变生克墓绝章:p0001",
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
            make_fact(
                "ZSBY-028-REVERSE-CHANT",
                id="fact-reverse-chant",
                type="REVERSE_CHANT",
                value=True,
                evidence={"inner": inner_reverses, "outer": outer_reverses},
                source_id="028_反伏章:p0001",
            )
        )
    if inner_repeats or outer_repeats:
        facts.append(
            make_fact(
                "ZSBY-028-REPEATED-CHANT",
                id="fact-repeated-chant",
                type="REPEATED_CHANT",
                value=True,
                evidence={"inner": inner_repeats, "outer": outer_repeats},
                source_id="028_反伏章:p0014",
            )
        )
    return facts
