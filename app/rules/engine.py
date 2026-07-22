from __future__ import annotations

from app.rules.auxiliary import auxiliary_facts
from app.rules.god_roles import god_role_facts
from app.rules.effects import effective_facts
from app.rules.interactions import interaction_facts
from app.rules.models import (
    RuleAnalysis,
    RuleContext,
    UsefulGodChoice,
    UsefulGodSelection,
)
from app.rules.outcome import build_outcome_analysis
from app.rules.patterns import pattern_facts
from app.rules.registry import unimplemented_rule_descriptions
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
            + auxiliary_facts(context)
        )
        facts.extend(pattern_facts(context, tuple(facts)))
        if useful_god_choice is None:
            useful = UsefulGodSelection(
                status="unresolved",
                target=context.question,
                useful_relative=None,
                rationale=("完整断卦时由用户明确选择用神，再由代码定位",),
            )
        else:
            useful = select_useful_god(
                context,
                tuple(facts),
                useful_god_choice,
            )
            facts.extend(god_role_facts(context, useful))
        facts.extend(effective_facts(context, useful, tuple(facts)))
        facts.sort(key=lambda fact: fact.id)
        fact_tuple = tuple(facts)
        outcome = build_outcome_analysis(context, useful, fact_tuple)
        timing = (
            tuple(timing_candidates(context, useful, fact_tuple))
            if useful_god_choice is not None
            else ()
        )
        implemented = tuple(sorted({fact.type for fact in fact_tuple}))
        return RuleAnalysis(
            useful_god=useful,
            facts=fact_tuple,
            outcome_analysis=outcome,
            timing_candidates=timing,
            implemented_rule_types=implemented,
            unimplemented_rules=unimplemented_rule_descriptions()
            + (
                "多卦合参",
                "门类专属应期的绝对日期换算",
            ),
        )
