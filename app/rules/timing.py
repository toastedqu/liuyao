from __future__ import annotations

from app.rules.elements import (
    BRANCH_ELEMENT,
    CLASH,
    COMBINE,
    GENERATES,
    TOMB,
    overcomes,
)
from app.rules.models import (
    RuleContext,
    RuleFact,
    TimingCandidate,
    UsefulGodSelection,
)


def timing_candidates(
    context: RuleContext,
    useful: UsefulGodSelection,
    facts: tuple[RuleFact, ...],
) -> list[TimingCandidate]:
    two_present = [
        TimingCandidate(
            id=f"timing-two-present-l{candidate.line}",
            trigger="用神两现候选分别逢值、逢冲",
            branches=(
                candidate.branch,
                CLASH[candidate.branch],
            )
            if candidate.branch is not None
            else (),
            time_unit_hint=_scope(context.question),
            confidence_limit=(
                "主用爻依古法旺动不破不空不伤确定；此候选仍保留，"
                "因为《两现章》另有空破爻填实应验的反例"
            ),
            source_ids=(
                "039_两现章:p0002",
                "032_各门类应期总注章:p0001",
            ),
        )
        for candidate in useful.candidates
        if len(useful.candidates) > 1
        and candidate.line is not None
        and candidate.branch is not None
    ]
    resolved_candidates = [
        candidate
        for candidate in useful.candidates
        if candidate.line is not None and candidate.element is not None
    ]
    if len(resolved_candidates) > 1:
        combined = list(two_present)
        for candidate in resolved_candidates:
            candidate_useful = useful.model_copy(
                update={
                    "status": "selected",
                    "candidates": (candidate,),
                    "selected_line": candidate.line,
                    "useful_element": candidate.element,
                }
            )
            combined.extend(
                _selected_timing_candidates(
                    context,
                    candidate_useful,
                    facts,
                )
            )
        return list({candidate.id: candidate for candidate in combined}.values())
    return [
        *two_present,
        *_selected_timing_candidates(context, useful, facts),
    ]


def _selected_timing_candidates(
    context: RuleContext,
    useful: UsefulGodSelection,
    facts: tuple[RuleFact, ...],
) -> list[TimingCandidate]:
    if useful.selected_line is None:
        return []
    line = next(
        (item for item in context.lines if item.position == useful.selected_line),
        None,
    )
    if line is None:
        return []
    selected_candidate = useful.candidates[0] if useful.candidates else None
    is_hidden = selected_candidate is not None and selected_candidate.role == "hidden"
    is_changed = selected_candidate is not None and selected_candidate.role == "changed"
    actor_branch = (
        selected_candidate.branch
        if (is_hidden or is_changed) and selected_candidate.branch is not None
        else line.branch
    )
    actor_element = (
        selected_candidate.element
        if (is_hidden or is_changed) and selected_candidate.element is not None
        else line.element
    )
    actor_is_moving = line.is_moving and not is_hidden

    by_type = {
        fact.type: fact
        for fact in facts
        if fact.line == line.position
    }
    candidates: list[TimingCandidate] = []
    scope = _scope(context.question)

    if actor_is_moving:
        candidates.append(
            TimingCandidate(
                id=f"timing-moving-value-l{line.position}",
                trigger="动爻逢值、逢合",
                branches=(actor_branch, COMBINE[actor_branch]),
                time_unit_hint=scope,
                confidence_limit="仅为候选；须结合事情远近及其他制化条件",
                fact_ids=(f"fact-changed-relation-l{line.position}",)
                if line.changed
                else (),
                source_ids=("032_各门类应期总注章:p0002",),
            )
        )
    else:
        candidates.append(
            TimingCandidate(
                id=f"timing-static-value-l{line.position}",
                trigger="静爻逢值、逢冲",
                branches=(actor_branch, CLASH[actor_branch]),
                time_unit_hint=scope,
                confidence_limit="仅为候选；须结合旺衰与所占事项",
                source_ids=("032_各门类应期总注章:p0001",),
            )
        )

    void = by_type.get(
        "HIDDEN_VOID" if is_hidden else "CHANGED_VOID" if is_changed else "旬空"
    )
    if void:
        candidates.append(
            TimingCandidate(
                id=f"timing-void-fill-l{line.position}",
                trigger="旬空填实、冲空",
                branches=(actor_branch, CLASH[actor_branch]),
                time_unit_hint=scope,
                confidence_limit="旺、动、有生扶者方可据此候用；真空不得强定",
                fact_ids=(void.id,),
                source_ids=(
                    "029_旬空章:p0001",
                    "032_各门类应期总注章:p0008",
                ),
            )
        )

    month_break = by_type.get(
        "HIDDEN_MONTH_BREAK"
        if is_hidden
        else "CHANGED_MONTH_BREAK"
        if is_changed
        else "MONTH_BREAK"
    )
    if month_break:
        candidates.append(
            TimingCandidate(
                id=f"timing-month-break-l{line.position}",
                trigger="月破填实、逢合",
                branches=(actor_branch, COMBINE[actor_branch]),
                time_unit_hint=scope,
                confidence_limit="动爻与静爻、近事与远事作用不同，不据此承诺唯一时间",
                fact_ids=(month_break.id,),
                source_ids=(
                    "034_月破章:p0001",
                    "032_各门类应期总注章:p0007",
                ),
            )
        )

    if not is_hidden and line.changed is not None:
        changed_void = by_type.get("CHANGED_VOID")
        if changed_void is not None:
            candidates.append(
                TimingCandidate(
                    id=f"timing-changed-void-fill-l{line.position}",
                    trigger="变爻出空或逢冲",
                    branches=(
                        line.changed.branch,
                        CLASH[line.changed.branch],
                    ),
                    time_unit_hint=scope,
                    confidence_limit="动而化空不作到底空，只列填实与冲实候选",
                    fact_ids=(changed_void.id,),
                    source_ids=("029_旬空章:p0005",),
                )
            )
        changed_break = by_type.get("CHANGED_MONTH_BREAK")
        if changed_break is not None:
            candidates.append(
                TimingCandidate(
                    id=f"timing-changed-break-fill-l{line.position}",
                    trigger="变爻出月或逢合填实",
                    branches=(
                        line.changed.branch,
                        COMBINE[line.changed.branch],
                    ),
                    time_unit_hint=scope,
                    confidence_limit="化月破只列出月、逢合的填实条件，不指定绝对日期",
                    fact_ids=(changed_break.id,),
                    source_ids=("034_月破章:p0004",),
                )
            )

    life_stage = by_type.get(
        "HIDDEN_LIFE_STAGE"
        if is_hidden
        else "CHANGED_LIFE_STAGE"
        if is_changed
        else "LIFE_STAGE"
    )
    if life_stage and life_stage.value == "墓":
        tomb_branch = TOMB[actor_element]
        candidates.append(
            TimingCandidate(
                id=f"timing-open-tomb-l{line.position}",
                trigger="入墓冲开",
                branches=(CLASH[tomb_branch],),
                time_unit_hint=scope,
                confidence_limit="须先确认确为有效入墓，而非旺相受生时论生不论墓",
                fact_ids=(life_stage.id,),
                source_ids=("032_各门类应期总注章:p0005",),
            )
        )

    if not is_hidden:
        for combine_type in ("MONTH_COMBINE", "DAY_COMBINE", "RETURN_COMBINE"):
            combine_fact = by_type.get(combine_type)
            if combine_fact:
                candidates.append(
                    TimingCandidate(
                        id=f"timing-open-combine-{combine_type.lower()}-l{line.position}",
                        trigger="六合待冲开",
                        branches=(CLASH[actor_branch], CLASH[COMBINE[actor_branch]]),
                        time_unit_hint=scope,
                        confidence_limit="吉神合住与凶神合住含义相反，只列冲开候选",
                        fact_ids=(combine_fact.id,),
                        source_ids=("032_各门类应期总注章:p0006",),
                    )
                )

    strength = by_type.get(
        "HIDDEN_SEASONAL_STRENGTH"
        if is_hidden
        else "CHANGED_SEASONAL_STRENGTH"
        if is_changed
        else "SEASONAL_STRENGTH"
    )
    if (
        strength
        and strength.value in {"月建", "旺"}
        and (
            context.day_branch == actor_branch
            or BRANCH_ELEMENT[context.day_branch] is actor_element
        )
    ):
        candidates.append(
            TimingCandidate(
                id=f"timing-too-strong-l{line.position}",
                trigger="太旺待墓、逢冲",
                branches=(TOMB[actor_element], CLASH[actor_branch]),
                time_unit_hint=scope,
                confidence_limit="仅当整体确属太旺时适用；旺而有制者不可机械套用",
                fact_ids=(strength.id,),
                source_ids=("032_各门类应期总注章:p0003",),
            )
        )
    if strength and strength.value == "休囚":
        source_element = next(
            element for element, generated in GENERATES.items() if generated is actor_element
        )
        branches = tuple(
            branch
            for branch, branch_element in _branch_elements().items()
            if branch_element is source_element or branch_element is actor_element
        )
        candidates.append(
            TimingCandidate(
                id=f"timing-weak-recovery-l{line.position}",
                trigger="衰绝待生旺",
                branches=branches,
                time_unit_hint=scope,
                confidence_limit="只给生扶、当令地支范围；未结合具体历表，不输出日期",
                fact_ids=(strength.id,),
                source_ids=("032_各门类应期总注章:p0004",),
            )
        )

    taboo_lines = [
        item
        for item in context.lines
        if useful.taboo_element is not None
        and item.element is useful.taboo_element
        and item.is_moving
    ]
    for taboo_line in taboo_lines:
        controlling = tuple(
            branch
            for branch, element in BRANCH_ELEMENT.items()
            if overcomes(element, taboo_line.element)
        )
        candidates.append(
            TimingCandidate(
                id=f"timing-control-taboo-l{taboo_line.position}",
                trigger="用神受克，待克神受制",
                branches=tuple(dict.fromkeys((CLASH[taboo_line.branch],) + controlling)),
                time_unit_hint=scope,
                confidence_limit="仅在大象可用而受此忌神克制时成立",
                fact_ids=(
                    f"fact-taboo-god-l{taboo_line.position}",
                    f"fact-moving-overcomes-useful-l{taboo_line.position}",
                ),
                source_ids=("032_各门类应期总注章:p0009",),
            )
        )

    advance = by_type.get("ADVANCE")
    if advance and line.changed and not is_hidden:
        candidates.append(
            TimingCandidate(
                id=f"timing-advance-l{line.position}",
                trigger="进神逢值、逢合",
                branches=(line.changed.branch, COMBINE[line.changed.branch]),
                time_unit_hint=scope,
                confidence_limit="进神为福为祸取决于该爻角色，本候选不判吉凶",
                fact_ids=(advance.id,),
                source_ids=("032_各门类应期总注章:p0012",),
            )
        )
    retreat = by_type.get("RETREAT")
    if retreat and line.changed and not is_hidden:
        candidates.append(
            TimingCandidate(
                id=f"timing-retreat-l{line.position}",
                trigger="退神逢值、逢冲",
                branches=(line.changed.branch, CLASH[line.changed.branch]),
                time_unit_hint=scope,
                confidence_limit="退神为福为祸取决于该爻角色，本候选不判吉凶",
                fact_ids=(retreat.id,),
                source_ids=("032_各门类应期总注章:p0013",),
            )
        )

    repeated = next(
        (
            fact
            for fact in facts
            if fact.type == "REPEATED_CHANT_EFFECT"
            and fact.line == line.position
        ),
        None,
    )
    if repeated is not None:
        candidates.append(
            TimingCandidate(
                id=f"timing-open-repeated-chant-l{line.position}",
                trigger="伏吟待冲开",
                branches=(CLASH[actor_branch],),
                time_unit_hint=scope,
                confidence_limit="用神旺相则冲开可伸，休囚则冲开仍主忧滞",
                fact_ids=(repeated.id,),
                source_ids=("028_反伏章:p0017",),
            )
        )

    return candidates


def _scope(question: str) -> str:
    if any(word in question for word in ("今日", "今天", "明日", "几时", "何时", "近日")):
        return "时/日"
    if any(word in question for word in ("今年", "明年", "终身", "长期", "将来", "何年")):
        return "月/年"
    return "依问题远近"


def _branch_elements():
    return BRANCH_ELEMENT
