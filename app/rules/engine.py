from __future__ import annotations

from app.rules.god_roles import god_role_facts
from app.rules.interactions import interaction_facts
from app.rules.models import (
    RuleAnalysis,
    RuleContext,
    UsefulGodChoice,
    UsefulGodSelection,
)
from app.rules.patterns import pattern_facts
from app.rules.strength import strength_facts
from app.rules.timing import timing_candidates
from app.rules.useful_god import select_useful_god


class RuleEngine:
    """Produce auditable facts without turning them into free-text outcomes."""

    def analyze(
        self,
        context: RuleContext,
        useful_god_choice: UsefulGodChoice | None = None,
    ) -> RuleAnalysis:
        facts = (
            strength_facts(context)
            + interaction_facts(context)
            + pattern_facts(context)
        )
        if useful_god_choice is None:
            useful = UsefulGodSelection(
                status="unresolved",
                target=context.question,
                useful_relative=None,
                rationale=("完整断卦时由模型根据所占之事判定用神",),
            )
        else:
            useful = select_useful_god(
                context,
                tuple(facts),
                useful_god_choice,
            )
            facts.extend(god_role_facts(context, useful))
        facts.sort(key=lambda fact: fact.id)
        fact_tuple = tuple(facts)
        timing = (
            tuple(timing_candidates(context, useful, fact_tuple))
            if useful_god_choice is not None
            else ()
        )
        implemented = tuple(sorted({fact.type for fact in fact_tuple}))
        return RuleAnalysis(
            useful_god=useful,
            facts=fact_tuple,
            timing_candidates=timing,
            implemented_rule_types=implemented,
            unimplemented_rules=(
                "六害（原书明确“全无应验”，不作为吉凶规则）",
                "随鬼入墓的语义适用条件",
                "复杂飞伏神有用/无用权衡",
                "多卦合参",
                "门类专属应期的绝对日期换算",
            ),
        )
