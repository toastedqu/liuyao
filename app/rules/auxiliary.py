from __future__ import annotations

from app.rules.elements import LU_SHEN, TAIYI_NOBLE, TIAN_XI, YI_MA
from app.rules.models import RuleContext, RuleFact
from app.rules.registry import make_fact


_STAR_TYPES = (
    ("STAR_NOBLE", "太乙贵人", "040_星煞章:p0001"),
    ("STAR_LU", "禄神", "040_星煞章:p0003"),
    ("STAR_HORSE", "驿马", "040_星煞章:p0005"),
    ("STAR_HAPPINESS", "天喜", "040_星煞章:p0007"),
)


def auxiliary_facts(context: RuleContext) -> list[RuleFact]:
    facts: list[RuleFact] = []
    if context.year_branch is not None:
        facts.append(
            make_fact(
                "ZSBY-031-YEAR-COMMAND",
                id="fact-year-command",
                type="YEAR_COMMAND",
                value=context.year_branch,
                evidence={"scope": "当年", "predictive_weight": 0},
                source_id="031_各门类题头总注章:p0005",
            )
        )

    for line in context.lines:
        if line.spirit is not None:
            facts.append(
                make_fact(
                    "ZSBY-019-SIX-GOD",
                    id=f"fact-six-god-l{line.position}",
                    type="SIX_GOD",
                    line=line.position,
                    value=line.spirit,
                    evidence={
                        "spirit": line.spirit,
                        "predictive_role": "附和",
                    },
                    source_id="019_六神章:p0003",
                )
            )

        actors = [("primary", line.branch)]
        if line.changed is not None:
            actors.append(("changed", line.changed.branch))
        if line.hidden_spirit is not None:
            actors.append(("hidden", line.hidden_spirit.branch))
        for actor, branch in actors:
            matches = {
                "STAR_NOBLE": branch in TAIYI_NOBLE[context.day_stem],
                "STAR_LU": branch == LU_SHEN[context.day_stem],
                "STAR_HORSE": branch == YI_MA[context.day_branch],
                "STAR_HAPPINESS": branch == TIAN_XI[context.month_branch],
            }
            for fact_type, name, source_id in _STAR_TYPES:
                if not matches[fact_type]:
                    continue
                suffix = (
                    f"l{line.position}"
                    if actor == "primary"
                    else f"{actor}-l{line.position}"
                )
                facts.append(
                    make_fact(
                        "ZSBY-040-STAR",
                        id=f"fact-{fact_type.lower().replace('_', '-')}-{suffix}",
                        type=fact_type,
                        line=line.position,
                        value=name,
                        evidence={
                            "actor": actor,
                            "branch": branch,
                            "star": name,
                        },
                        source_id=source_id,
                    )
                )
    return facts
