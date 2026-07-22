from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.api.schemas import (
    CaseEvidenceOutput,
    Category,
    ChartRequest,
    ChartResponse,
    DivinationRequest,
    DivinationResponse,
    InputSummary,
    SourceOutput,
)
from app.calendar.service import build_calendar_context
from app.chart import Chart, build_chart
from app.config import Settings
from app.fact_display import fact_result_for_display
from app.fact_types import fact_type_label
from app.divination.validator import (
    ValidationResult,
    validate_divination_conclusion,
)
from app.divination.useful_god import build_useful_god_choice
from app.knowledge.models import ParagraphRecord
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.retrieval import Retriever, ScoredExample
from app.llm.base import LLMProvider
from app.llm.context import (
    DecisionEvidenceContext,
    DivinationRequestContext,
    ExampleContext,
    FactContext,
    SourceContext,
    TimingCandidateContext,
)
from app.llm.factory import get_llm_provider
from app.llm.prompts import (
    build_correction_messages,
    build_messages,
    build_question_category_messages,
)
from app.llm.schemas import (
    DivinationConclusion,
    LineProperty,
    QuestionCategory,
)
from app.rules import (
    ChangedLineContext,
    LineContext,
    RuleAnalysis,
    RuleContext,
    RuleEngine,
)
from app.rules.models import (
    Element as RuleElement,
    HiddenSpiritContext,
    QuestionPerspective,
    Relative as RuleRelative,
    RuleFact,
    UsefulGodSelection,
)


CORPUS_CATEGORY = {
    "诉讼": "词讼",
    "行人": "出行",
    "学业": "功名",
}
FACT_TO_RULE_TAG: dict[str, str] = {
    "USEFUL_GOD": "USEFUL_GOD",
    "YUAN_GOD": "ORIGIN_GOD",
    "TABOO_GOD": "TABOO_GOD",
    "ENEMY_GOD": "RIVAL_GOD",
    "旬空": "EMPTY_TOMB",
    "CHANGED_VOID": "EMPTY_TOMB",
    "HIDDEN_VOID": "EMPTY_TOMB",
    "VOID_EFFECT": "EMPTY_TOMB",
    "CHANGED_VOID_EFFECT": "EMPTY_TOMB",
    "MONTH_BREAK": "MONTH_BREAK",
    "CHANGED_MONTH_BREAK": "MONTH_BREAK",
    "HIDDEN_MONTH_BREAK": "MONTH_BREAK",
    "MONTH_BREAK_EFFECT": "MONTH_BREAK",
    "CHANGED_MONTH_BREAK_EFFECT": "MONTH_BREAK",
    "SEASONAL_STRENGTH": "SEASONAL_STRENGTH",
    "CHANGED_SEASONAL_STRENGTH": "SEASONAL_STRENGTH",
    "HIDDEN_SEASONAL_STRENGTH": "SEASONAL_STRENGTH",
    "DARK_MOVEMENT": "HIDDEN_MOTION",
    "MOVING_DAY_CLASH": "MOVING_DISSIPATE",
    "RETURN_GENERATE": "RETURN_GENERATION",
    "RETURN_OVERCOME": "RETURN_CONTROL",
    "THREE_HARMONY": "THREE_COMBINE",
    "THREE_HARMONY_PENDING": "THREE_COMBINE",
    "THREE_HARMONY_EFFECT": "THREE_COMBINE",
    "THREE_HARMONY_WORLD_EFFECT": "THREE_COMBINE",
    "LINE_COMBINE": "SIX_COMBINE",
    "MONTH_COMBINE": "SIX_COMBINE",
    "DAY_COMBINE": "SIX_COMBINE",
    "RETURN_COMBINE": "SIX_COMBINE",
    "LINE_CLASH": "SIX_CLASH",
    "PRIMARY_SIX_CLASH": "SIX_CLASH",
    "CHANGED_SIX_CLASH": "SIX_CLASH",
    "LINE_PUNISHMENT": "THREE_PUNISH",
    "ADVANCE": "ADVANCING_SPIRIT",
    "ADVANCE_EFFECT": "ADVANCING_SPIRIT",
    "RETREAT": "RETREATING_SPIRIT",
    "RETREAT_EFFECT": "RETREATING_SPIRIT",
    "FLYING_HIDDEN_RELATION": "HIDDEN_SPIRIT",
    "HIDDEN_SPIRIT_EFFECT": "HIDDEN_SPIRIT",
    "REVERSE_CHANT": "REVERSE_ECHO",
    "REPEATED_CHANT": "REPEATED_ECHO",
    "SINGLE_MOVING": "SOLE_MOVING",
    "USEFUL_GOD_MULTIPLE": "DOUBLE_PRESENT",
    "WANDERING_SOUL": "WANDERING_RETURNING_SOUL",
    "RETURNING_SOUL": "WANDERING_RETURNING_SOUL",
    "LIFE_STAGE": "GRAVE_ABSOLUTE",
    "CHANGED_LIFE_STAGE": "GRAVE_ABSOLUTE",
    "HIDDEN_LIFE_STAGE": "GRAVE_ABSOLUTE",
    "DYNAMIC_LIFE_STAGE": "GRAVE_ABSOLUTE",
    "LIFE_STAGE_EFFECT": "GRAVE_ABSOLUTE",
    "CHANGED_LIFE_STAGE_EFFECT": "GRAVE_ABSOLUTE",
    "DYNAMIC_LIFE_STAGE_EFFECT": "GRAVE_ABSOLUTE",
    "GHOST_TOMB": "GHOST_TOMB",
}


class KnowledgeBaseUnavailable(RuntimeError):
    pass


class UsefulGodResolutionRequired(RuntimeError):
    def __init__(self, rationale: tuple[str, ...]):
        super().__init__(
            "所选用神无法在当前卦盘中定位；请核对所选用神类别，"
            "仍不能确定时应依《增删卜易》再占，不作强断"
        )
        self.rationale = rationale


class DivinationValidationError(RuntimeError):
    def __init__(self, first: ValidationResult, second: ValidationResult):
        super().__init__("模型纠正一次后仍未通过事实与引用校验")
        self.first = first
        self.second = second


@dataclass(frozen=True)
class DeterministicResult:
    request: ChartRequest
    calendar: Any
    chart: Chart
    rules: RuleAnalysis
    category: Category | None = None
    perspective: str | None = None


@dataclass(frozen=True)
class RetrievedKnowledge:
    sources: tuple[ParagraphRecord, ...]
    examples: tuple[ScoredExample, ...]


class DivinationService:
    def __init__(
        self,
        *,
        settings: Settings,
        repo_root: Path,
        provider: LLMProvider | None = None,
        rule_engine: RuleEngine | None = None,
    ):
        self._settings = settings
        self._repo_root = repo_root
        self._provider = provider
        self._rule_engine = rule_engine or RuleEngine()

    def compute(self, request: ChartRequest) -> DeterministicResult:
        calendar = build_calendar_context(
            request.calendar.year,
            request.calendar.month,
            request.calendar.day,
            request.calendar.hour,
            timezone=request.calendar.timezone,
            zi_hour_boundary=self._settings.ZI_HOUR_DAY_BOUNDARY,
        )
        chart = build_chart(
            request.lines,
            six_spirits=calendar.six_spirits_by_line,
        )
        rules = self._rule_engine.analyze(
            self._rule_context(request, calendar, chart)
        )
        return DeterministicResult(
            request=request,
            calendar=calendar,
            chart=chart,
            rules=rules,
        )

    def chart_response(self, request: ChartRequest) -> ChartResponse:
        result = self.compute(request)
        return self._chart_response(result)

    async def divine(self, request: DivinationRequest) -> DivinationResponse:
        result = self.compute(request)
        provider = self._get_provider()
        classification = await self._classify_question(request.question, provider)
        choice = build_useful_god_choice(
            question=request.question,
            useful_god=request.useful_god,
        )
        rules = self._rule_engine.analyze(
            self._rule_context(
                request,
                result.calendar,
                result.chart,
                category=classification.category,
                perspective=classification.perspective,
            ),
            choice,
        )
        result = replace(
            result,
            category=Category(classification.category),
            perspective=classification.perspective,
            rules=rules,
        )
        if result.rules.useful_god.status == "unresolved":
            raise UsefulGodResolutionRequired(result.rules.useful_god.rationale)

        knowledge = self._retrieve_knowledge(result)
        llm_context = self._llm_context(result, knowledge)
        messages = build_messages(llm_context, DivinationConclusion)
        conclusion = await provider.generate_structured(messages, DivinationConclusion)
        first_validation = validate_divination_conclusion(conclusion, llm_context)
        if not first_validation.valid:
            correction = build_correction_messages(
                messages,
                conclusion.model_dump_json(),
                first_validation.correction_messages(),
            )
            conclusion = await provider.generate_structured(correction, DivinationConclusion)
            second_validation = validate_divination_conclusion(conclusion, llm_context)
            if not second_validation.valid:
                raise DivinationValidationError(first_validation, second_validation)

        base = self._chart_response(result)
        source_outputs = self._source_outputs(knowledge.sources)
        return DivinationResponse(
            **base.model_dump(),
            interpretation=conclusion,
            case_evidence=self._case_evidence_outputs(
                knowledge.examples,
                source_outputs,
            ),
            sources=source_outputs,
        )

    async def _classify_question(
        self,
        question: str,
        provider: LLMProvider,
    ) -> QuestionCategory:
        messages = build_question_category_messages(question)
        return await provider.generate_structured(messages, QuestionCategory)

    def get_source(self, source_id: str) -> SourceOutput | None:
        self._require_knowledge_db()
        with KnowledgeRepository.open(self._settings.KNOWLEDGE_DB_PATH) as repository:
            paragraph = repository.get_paragraph(source_id)
            if paragraph is None:
                return None
            paragraph = repository.resolve_source(source_id, self._repo_root)
            return self._source_output(paragraph, repository=repository)

    def _get_provider(self) -> LLMProvider:
        if self._provider is not None:
            return self._provider
        environment = {
            key: str(value)
            for key, value in self._settings.model_dump().items()
            if value is not None
        }
        self._provider = get_llm_provider(
            self._settings.LLM_PROVIDER,
            env=environment,
        )
        return self._provider

    def _require_knowledge_db(self) -> None:
        path = self._settings.KNOWLEDGE_DB_PATH
        if not path.is_file():
            raise KnowledgeBaseUnavailable(
                f"知识库不存在：{path}；请先运行 python scripts/build_knowledge_base.py"
            )

    def _retrieve_knowledge(self, result: DeterministicResult) -> RetrievedKnowledge:
        self._require_knowledge_db()
        category = result.category
        assert category is not None
        corpus_category = CORPUS_CATEGORY.get(category.value, category.value)
        rule_tags = sorted(
            {
                FACT_TO_RULE_TAG[fact.type]
                for fact in result.rules.facts
                if fact.type in FACT_TO_RULE_TAG
            }
        )

        with KnowledgeRepository.open(self._settings.KNOWLEDGE_DB_PATH) as repository:
            retriever = Retriever(repository)
            retrieved = retriever.retrieve(
                category=corpus_category,
                fact_tags=rule_tags,
                hexagram_name=result.chart.primary.name,
                changed_hexagram_name=result.chart.changed.name,
                keywords=result.request.question,
                example_query=result.request.question,
                useful_relative=(
                    result.rules.useful_god.useful_relative.value
                    if result.rules.useful_god.useful_relative is not None
                    else None
                ),
                example_limit=6,
                fts_limit=8,
            )
            mandatory_ids = {
                source_id
                for fact in result.rules.facts
                for source_id in fact.source_ids
            } | set(result.rules.useful_god.source_ids)
            for evidence in result.rules.outcome_analysis.evidence:
                mandatory_ids.update(evidence.source_ids)
            for candidate in result.rules.timing_candidates:
                mandatory_ids.update(candidate.source_ids)

            ordered: list[ParagraphRecord] = []
            seen: set[str] = set()

            def add(paragraph: ParagraphRecord | None) -> None:
                if (
                    paragraph is None
                    or paragraph.source_id in seen
                    or paragraph.is_editorial
                ):
                    return
                seen.add(paragraph.source_id)
                ordered.append(paragraph)

            missing_ids = []
            editorial_ids = []
            for source_id in sorted(mandatory_ids):
                paragraph = repository.get_paragraph(source_id)
                if paragraph is None:
                    missing_ids.append(source_id)
                elif paragraph.is_editorial:
                    editorial_ids.append(source_id)
                else:
                    add(paragraph)
            if missing_ids or editorial_ids:
                details = []
                if missing_ids:
                    details.append(f"不存在：{', '.join(missing_ids)}")
                if editorial_ids:
                    details.append(f"仅为编辑按语：{', '.join(editorial_ids)}")
                raise KnowledgeBaseUnavailable(
                    "确定性规则引用无法作为模型依据（" + "；".join(details) + "）"
                )
            stage_limits = {"fixed_pick": 0, "category": 12, "fact_tag": 0, "fts": 6}
            stage_counts = {stage: 0 for stage in stage_limits}
            for item in retrieved.paragraphs:
                if len(ordered) >= 36:
                    break
                if stage_counts.get(item.stage, 0) >= stage_limits.get(item.stage, 0):
                    continue
                before = len(ordered)
                add(item.paragraph)
                if len(ordered) > before:
                    stage_counts[item.stage] += 1
            examples: list[ScoredExample] = []
            for scored in retrieved.examples:
                judgement = (
                    repository.get_paragraph(scored.example.judgement_id)
                    if scored.example.judgement_id
                    else None
                )
                if judgement is None or judgement.is_editorial:
                    continue
                for source_id in (
                    scored.example.question_id,
                    scored.example.chart_id,
                    scored.example.judgement_id,
                ):
                    if source_id:
                        add(repository.get_paragraph(source_id))
                examples.append(scored)
                if len(examples) == 3:
                    break
            return RetrievedKnowledge(
                sources=tuple(ordered),
                examples=tuple(examples),
            )

    def _llm_context(
        self,
        result: DeterministicResult,
        knowledge: RetrievedKnowledge,
    ) -> DivinationRequestContext:
        category = result.category
        assert category is not None
        required_rule_fact_ids = {
            fact_id
            for evidence in result.rules.outcome_analysis.evidence
            for fact_id in evidence.fact_ids
        } | {
            fact_id
            for candidate in result.rules.timing_candidates
            for fact_id in candidate.fact_ids
        }
        selected_candidate = (
            result.rules.useful_god.candidates[0]
            if result.rules.useful_god.candidates
            else None
        )
        hidden_is_selected = (
            selected_candidate is not None
            and selected_candidate.role == "hidden"
        )
        noisy_fact_types = {
            "LINE_ELEMENT_RELATION",
            "BRANCH_CLASH_PAIR",
            "BRANCH_COMBINE_PAIR",
            "BRANCH_PUNISHMENT_PAIR",
            "BRANCH_HARM_PAIR",
            "DYNAMIC_LIFE_STAGE",
            "DYNAMIC_LIFE_STAGE_EFFECT",
            "STAR_NOBLE",
            "STAR_LU",
            "STAR_HORSE",
            "STAR_HAPPINESS",
            "YEAR_COMMAND",
        }
        rule_facts = [
            fact
            for fact in result.rules.facts
            if fact.id in required_rule_fact_ids
            or (
                fact.type not in noisy_fact_types
                and (
                    hidden_is_selected
                    or not (
                        fact.type.startswith("HIDDEN_")
                        or fact.type == "FLYING_HIDDEN_RELATION"
                    )
                )
            )
        ]
        facts = [
            self._chart_fact_context(fact) for fact in result.chart.facts
        ] + [
            self._rule_fact_context(fact) for fact in rule_facts
        ]
        source_contexts = self._source_contexts(knowledge.sources)
        timing = [
            TimingCandidateContext(
                candidate_id=candidate.id,
                condition=candidate.trigger,
                description=(
                    f"候选地支：{'、'.join(candidate.branches)}；"
                    f"时间单位：{candidate.time_unit_hint}；"
                    f"限制：{candidate.confidence_limit}"
                ),
                source_ids=list(candidate.source_ids),
            )
            for candidate in result.rules.timing_candidates
        ]
        useful = result.rules.useful_god
        return DivinationRequestContext(
            question=result.request.question,
            category=category.value,
            perspective=result.perspective or "自占",
            chart_summary={
                "calendar": result.calendar.model_dump(mode="json"),
                "primary": result.chart.primary.model_dump(mode="json"),
                "changed": result.chart.changed.model_dump(mode="json"),
                "lines": [line.model_dump(mode="json") for line in result.chart.lines],
                "line_order": result.chart.line_order,
            },
            useful_god=self._useful_god_summary(useful),
            facts=facts,
            decision_guardrail=result.rules.outcome_analysis.guardrail.value,
            decision_evidence=[
                DecisionEvidenceContext(
                    evidence_id=evidence.id,
                    direction=evidence.direction.value,
                    weight=evidence.weight.value,
                    description=evidence.description,
                    fact_ids=list(evidence.fact_ids),
                    source_ids=list(evidence.source_ids),
                )
                for evidence in result.rules.outcome_analysis.evidence
            ],
            decision_limitations=list(result.rules.outcome_analysis.limitations),
            timing_candidates=timing,
            sources=source_contexts,
            examples=self._example_contexts(
                knowledge.examples,
                source_contexts,
            ),
        )

    def _chart_response(self, result: DeterministicResult) -> ChartResponse:
        rules = result.rules
        summary = InputSummary(
            question=result.request.question,
            category=result.category.value if result.category else None,
            perspective=result.perspective,
            calendar=result.calendar.local_moment.isoformat(),
        )
        useful_god_selected = result.category is not None
        return ChartResponse(
            input_summary=summary,
            calendar=result.calendar,
            primary_hexagram=result.chart.primary,
            changed_hexagram=result.chart.changed,
            lines=result.chart.lines,
            useful_god=rules.useful_god if useful_god_selected else None,
            outcome_analysis=(
                rules.outcome_analysis
                if useful_god_selected
                else None
            ),
            facts=tuple(
                fact.model_copy(
                    update={
                        "type": fact_type_label(fact.type),
                        "value": fact_result_for_display(fact),
                    }
                )
                for fact in result.chart.facts + rules.facts
            ),
            timing_candidates=(
                rules.timing_candidates if useful_god_selected else ()
            ),
            limitations=(
                rules.unimplemented_rules
                if useful_god_selected
                else (
                    "仅排盘接口未接收用户选择的用神，因此不判定元忌与应期",
                    *rules.unimplemented_rules,
                )
            ),
        )

    def _rule_context(
        self,
        request: ChartRequest,
        calendar: Any,
        chart: Chart,
        *,
        category: str | None = None,
        perspective: str | None = None,
    ) -> RuleContext:
        lines = []
        for line in chart.lines:
            changed = None
            if line.changed is not None:
                changed = ChangedLineContext(
                    branch=line.changed.branch,
                    element=RuleElement(line.changed.element.value),
                    relative=RuleRelative(line.changed.relative.value),
                    is_yang=line.changed.is_yang,
                )
            hidden = None
            if line.hidden_spirit is not None:
                hidden = HiddenSpiritContext(
                    stem=line.hidden_spirit.stem,
                    branch=line.hidden_spirit.branch,
                    element=RuleElement(line.hidden_spirit.element.value),
                    relative=RuleRelative(line.hidden_spirit.relative.value),
                )
            lines.append(
                LineContext(
                    position=line.position,
                    branch=line.branch,
                    element=RuleElement(line.element.value),
                    relative=RuleRelative(line.relative.value),
                    is_yang=line.is_yang,
                    is_moving=line.is_moving,
                    is_world=line.is_world,
                    is_response=line.is_response,
                    spirit=line.spirit,
                    changed=changed,
                    hidden_spirit=hidden,
                )
            )
        void = calendar.day_pillar.void_branches
        return RuleContext(
            question=request.question,
            year_branch=calendar.year_pillar.ganzhi.branch,
            month_branch=calendar.month_pillar.ganzhi.branch,
            day_stem=calendar.day_pillar.ganzhi.stem,
            day_branch=calendar.day_pillar.ganzhi.branch,
            void_branches=(void.first, void.second),
            palace_element=RuleElement(chart.primary.palace_element.value),
            changed_palace_element=RuleElement(chart.changed.palace_element.value),
            primary_hexagram=chart.primary.name,
            changed_hexagram=chart.changed.name,
            primary_is_six_clash=chart.primary.is_six_clash,
            primary_is_six_harmony=chart.primary.is_six_harmony,
            changed_is_six_clash=chart.changed.is_six_clash,
            changed_is_six_harmony=chart.changed.is_six_harmony,
            primary_is_wandering_soul=chart.primary.is_wandering_soul,
            primary_is_returning_soul=chart.primary.is_returning_soul,
            lines=tuple(lines),
            category=category,
            perspective=(
                QuestionPerspective.SELF
                if perspective == "自占"
                else QuestionPerspective.PROXY
                if perspective == "代占"
                else None
            ),
        )

    def _source_contexts(
        self,
        sources: tuple[ParagraphRecord, ...],
    ) -> list[SourceContext]:
        contexts = []
        with KnowledgeRepository.open(self._settings.KNOWLEDGE_DB_PATH) as repository:
            for paragraph in sources:
                chapter = repository.get_chapter(paragraph.chapter_id)
                contexts.append(
                    SourceContext(
                        source_id=paragraph.source_id,
                        chapter=chapter.title if chapter else paragraph.chapter_id,
                        text=paragraph.text,
                    )
                )
        return contexts

    def _example_contexts(
        self,
        examples: tuple[ScoredExample, ...],
        sources: list[SourceContext],
    ) -> list[ExampleContext]:
        sources_by_id = {source.source_id: source for source in sources}
        contexts = []
        for scored in examples:
            example = scored.example
            judgement = sources_by_id.get(example.judgement_id or "")
            if judgement is None:
                continue
            question = sources_by_id.get(example.question_id or "")
            chart = sources_by_id.get(example.chart_id or "")
            contexts.append(
                ExampleContext(
                    example_id=example.example_id,
                    chapter=judgement.chapter,
                    match_score=scored.score,
                    match_reasons=[
                        self._example_reason(reason) for reason in scored.reasons
                    ],
                    question=question,
                    chart=chart,
                    judgement=judgement,
                )
            )
        return contexts

    @staticmethod
    def _example_reason(reason: str) -> str:
        kind, _, value = reason.partition(":")
        labels = {
            "category": "同占类",
            "rule_tags": "共同规则事实",
            "hexagram": "同主卦",
            "changed_hexagram": "同变卦",
            "useful_relative": "同用神六亲",
            "question_terms": "问题文字重合",
        }
        return f"{labels.get(kind, kind)}：{value}"

    @staticmethod
    def _chart_fact_context(fact: Any) -> FactContext:
        property_ = None
        if fact.type == "MOVING":
            property_ = LineProperty.DONG
        elif fact.type == "STATIC":
            property_ = LineProperty.JING
        return FactContext(
            id=fact.id,
            type=fact_type_label(fact.type),
            description=DivinationService._fact_description(fact),
            line=fact.line,
            value=True if property_ is not None else None,
            property=property_,
            rule_source=fact.rule_source,
            source_ids=[fact.rule_source],
            data=fact.evidence,
        )

    @staticmethod
    def _rule_fact_context(fact: RuleFact) -> FactContext:
        property_: LineProperty | None = None
        value: bool | None = None
        if fact.type == "旬空":
            property_, value = LineProperty.KONG, True
        elif fact.type == "MONTH_BREAK":
            property_, value = LineProperty.PO, True
        elif fact.type == "DARK_MOVEMENT":
            property_, value = LineProperty.DONG, True
        elif fact.type == "SEASONAL_STRENGTH":
            if fact.value in {"月建", "旺", "相", "余气"}:
                property_, value = LineProperty.WANG, True
            elif fact.value == "休囚":
                property_, value = LineProperty.SHUAI, True
        elif fact.type in {"RETURN_GENERATE", "MOVING_GENERATES_USEFUL"}:
            property_, value = LineProperty.SHENG, True
        elif fact.type in {"RETURN_OVERCOME", "MOVING_OVERCOMES_USEFUL"}:
            property_, value = LineProperty.KE, True
        elif fact.type == "CHANGED_ELEMENT_RELATION" and fact.value in {"生", "克"}:
            property_ = LineProperty.SHENG if fact.value == "生" else LineProperty.KE
            value = True
        elif fact.type == "DAY_RELATION" and fact.value in {"日辰生爻", "日辰克爻"}:
            property_ = (
                LineProperty.SHENG if fact.value == "日辰生爻" else LineProperty.KE
            )
            value = True
        return FactContext(
            id=fact.id,
            type=fact_type_label(fact.type),
            layer=fact.layer.value,
            description=DivinationService._fact_description(fact),
            line=fact.line,
            related_lines=list(fact.related_lines),
            value=value,
            property=property_,
            rule_source=fact.rule_source,
            source_ids=list(fact.source_ids),
            data={
                "value": fact.value,
                **fact.evidence,
            },
        )

    @staticmethod
    def _useful_god_summary(useful: UsefulGodSelection) -> str:
        """Compact JSON view of the resolved useful god for the judgement call.

        ``rationale`` and ``source_ids`` are intentionally omitted. The
        selected candidate's role and branch remain explicit so the model
        cannot mistake a changed or hidden useful god for the visible line;
        source paragraphs are already included through ``mandatory_ids``.
        """
        selected = (
            useful.candidates[0]
            if useful.status == "selected" and useful.candidates
            else None
        )
        payload = {
            "status": useful.status,
            "target": useful.target,
            "selection_mode": useful.selection_mode,
            "useful_relative": useful.useful_relative,
            "selected_line": useful.selected_line,
            "selected_role": selected.role if selected is not None else None,
            "selected_branch": selected.branch if selected is not None else None,
            "useful_element": useful.useful_element,
            "yuan_element": useful.yuan_element,
            "taboo_element": useful.taboo_element,
            "enemy_element": useful.enemy_element,
        }
        if len(useful.candidates) > 1:
            payload["candidates"] = [
                {
                    "line": candidate.line,
                    "role": candidate.role,
                    "relative": candidate.relative,
                    "branch": candidate.branch,
                    "element": candidate.element,
                    "selected": candidate.line == useful.selected_line,
                }
                for candidate in useful.candidates
            ]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _fact_description(fact: Any) -> str:
        value = fact_result_for_display(fact)
        rendered = (
            value
            if isinstance(value, str)
            else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        )
        return f"结果={rendered}"

    def _source_outputs(
        self,
        sources: tuple[ParagraphRecord, ...],
    ) -> tuple[SourceOutput, ...]:
        with KnowledgeRepository.open(self._settings.KNOWLEDGE_DB_PATH) as repository:
            return tuple(
                self._source_output(paragraph, repository=repository)
                for paragraph in sources
            )

    def _case_evidence_outputs(
        self,
        examples: tuple[ScoredExample, ...],
        sources: tuple[SourceOutput, ...],
    ) -> tuple[CaseEvidenceOutput, ...]:
        sources_by_id = {source.source_id: source for source in sources}
        outputs = []
        for scored in examples:
            example = scored.example
            judgement = sources_by_id.get(example.judgement_id or "")
            if judgement is None:
                continue
            outputs.append(
                CaseEvidenceOutput(
                    example_id=example.example_id,
                    chapter_id=example.chapter_id,
                    chapter_title=judgement.chapter_title,
                    match_score=scored.score,
                    match_reasons=tuple(
                        self._example_reason(reason) for reason in scored.reasons
                    ),
                    question=sources_by_id.get(example.question_id or ""),
                    chart=sources_by_id.get(example.chart_id or ""),
                    judgement=judgement,
                )
            )
        return tuple(outputs)

    def _source_output(
        self,
        paragraph: ParagraphRecord,
        *,
        repository: KnowledgeRepository | None = None,
    ) -> SourceOutput:
        if repository is not None:
            chapter = repository.get_chapter(paragraph.chapter_id)
        else:
            with KnowledgeRepository.open(self._settings.KNOWLEDGE_DB_PATH) as repo:
                chapter = repo.get_chapter(paragraph.chapter_id)
        return SourceOutput(
            source_id=paragraph.source_id,
            chapter_id=paragraph.chapter_id,
            chapter_title=chapter.title if chapter else paragraph.chapter_id,
            content_type=paragraph.content_type,
            text=paragraph.text,
            is_editorial=paragraph.is_editorial,
            source_path=paragraph.source_path,
        )
