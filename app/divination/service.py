from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.api.schemas import (
    Category,
    ChartResponse,
    DivinationRequest,
    DivinationResponse,
    InputSummary,
    SourceOutput,
)
from app.calendar.service import build_calendar_context
from app.chart import Chart, build_chart
from app.config import Settings
from app.divination.validator import (
    ValidationResult,
    validate_divination_conclusion,
    validate_useful_god_decision,
)
from app.knowledge.models import ParagraphRecord
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.retrieval import Retriever
from app.llm.base import LLMProvider
from app.llm.context import (
    DivinationRequestContext,
    FactContext,
    SourceContext,
    TimingCandidateContext,
)
from app.llm.factory import get_llm_provider
from app.llm.prompts import (
    build_correction_messages,
    build_messages,
    build_useful_god_selection_messages,
)
from app.llm.schemas import DivinationConclusion, LineProperty, UsefulGodDecision
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
    Relative as RuleRelative,
    RuleFact,
    UsefulGodChoice,
)


CORPUS_CATEGORY = {"诉讼": "词讼"}
USEFUL_GOD_SELECTION_SOURCE_IDS = (
    "008_用神章:p0001",
    "008_用神章:p0002",
    "008_用神章:p0003",
    "008_用神章:p0006",
    "008_用神章:p0007",
    "031_各门类题头总注章:p0010",
    "041_天时章:p0002",
    "041_天时章:p0003",
    "041_天时章:p0005",
)
FACT_TO_RULE_TAG: dict[str, str] = {
    "USEFUL_GOD": "USEFUL_GOD",
    "YUAN_GOD": "ORIGIN_GOD",
    "TABOO_GOD": "TABOO_GOD",
    "ENEMY_GOD": "RIVAL_GOD",
    "旬空": "EMPTY_TOMB",
    "MONTH_BREAK": "MONTH_BREAK",
    "SEASONAL_STRENGTH": "SEASONAL_STRENGTH",
    "DARK_MOVEMENT": "HIDDEN_MOTION",
    "MOVING_DAY_CLASH": "MOVING_DISSIPATE",
    "RETURN_GENERATE": "RETURN_GENERATION",
    "RETURN_OVERCOME": "RETURN_CONTROL",
    "THREE_HARMONY": "THREE_COMBINE",
    "LINE_COMBINE": "SIX_COMBINE",
    "MONTH_COMBINE": "SIX_COMBINE",
    "DAY_COMBINE": "SIX_COMBINE",
    "RETURN_COMBINE": "SIX_COMBINE",
    "LINE_CLASH": "SIX_CLASH",
    "PRIMARY_SIX_CLASH": "SIX_CLASH",
    "CHANGED_SIX_CLASH": "SIX_CLASH",
    "LINE_PUNISHMENT": "THREE_PUNISH",
    "ADVANCE": "ADVANCING_SPIRIT",
    "RETREAT": "RETREATING_SPIRIT",
    "FLYING_HIDDEN_RELATION": "HIDDEN_SPIRIT",
    "REVERSE_CHANT": "REVERSE_ECHO",
    "REPEATED_CHANT": "REPEATED_ECHO",
    "SINGLE_MOVING": "SOLE_MOVING",
    "USEFUL_GOD_MULTIPLE": "DOUBLE_PRESENT",
    "WANDERING_SOUL": "WANDERING_RETURNING_SOUL",
    "RETURNING_SOUL": "WANDERING_RETURNING_SOUL",
}


class KnowledgeBaseUnavailable(RuntimeError):
    pass


class UsefulGodResolutionRequired(RuntimeError):
    def __init__(self, rationale: tuple[str, ...]):
        super().__init__("模型已判定用神，但当前排盘无法定位对应爻位")
        self.rationale = rationale


class DivinationValidationError(RuntimeError):
    def __init__(self, first: ValidationResult, second: ValidationResult):
        super().__init__("模型纠正一次后仍未通过事实与引用校验")
        self.first = first
        self.second = second


@dataclass(frozen=True)
class DeterministicResult:
    request: DivinationRequest
    calendar: Any
    chart: Chart
    rules: RuleAnalysis
    category: Category | None = None
    useful_god_decision: UsefulGodDecision | None = None


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

    def compute(self, request: DivinationRequest) -> DeterministicResult:
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

    def chart_response(self, request: DivinationRequest) -> ChartResponse:
        result = self.compute(request)
        return self._chart_response(result)

    async def divine(self, request: DivinationRequest) -> DivinationResponse:
        result = self.compute(request)
        selection_sources = self._retrieve_useful_god_sources()
        selection_contexts = self._source_contexts(selection_sources)
        provider = self._get_provider()
        decision = await self._select_useful_god(
            request.question,
            selection_contexts,
            provider,
        )
        choice = UsefulGodChoice(
            target=decision.target,
            mode=decision.mode,
            useful_relative=(
                RuleRelative(decision.useful_relative)
                if decision.useful_relative is not None
                else None
            ),
            rationale=decision.rationale,
            source_ids=tuple(
                dict.fromkeys(citation.source_id for citation in decision.citations)
            ),
        )
        rules = self._rule_engine.analyze(
            self._rule_context(request, result.calendar, result.chart),
            choice,
        )
        result = replace(
            result,
            category=Category(decision.category),
            useful_god_decision=decision,
            rules=rules,
        )
        if result.rules.useful_god.status == "unresolved":
            raise UsefulGodResolutionRequired(result.rules.useful_god.rationale)

        sources = self._retrieve_sources(result)
        llm_context = self._llm_context(result, sources)
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
        return DivinationResponse(
            **base.model_dump(),
            interpretation=conclusion,
            sources=tuple(self._source_output(paragraph) for paragraph in sources),
        )

    async def _select_useful_god(
        self,
        question: str,
        sources: list[SourceContext],
        provider: LLMProvider,
    ) -> UsefulGodDecision:
        messages = build_useful_god_selection_messages(question, sources)
        decision = await provider.generate_structured(messages, UsefulGodDecision)
        first_validation = validate_useful_god_decision(decision, sources)
        if first_validation.valid:
            return decision

        correction = build_correction_messages(
            messages,
            decision.model_dump_json(),
            first_validation.correction_messages(),
        )
        decision = await provider.generate_structured(correction, UsefulGodDecision)
        second_validation = validate_useful_god_decision(decision, sources)
        if not second_validation.valid:
            raise DivinationValidationError(first_validation, second_validation)
        return decision

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

    def _retrieve_useful_god_sources(self) -> tuple[ParagraphRecord, ...]:
        self._require_knowledge_db()
        with KnowledgeRepository.open(self._settings.KNOWLEDGE_DB_PATH) as repository:
            paragraphs: list[ParagraphRecord] = []
            missing_ids: list[str] = []
            editorial_ids: list[str] = []
            for source_id in USEFUL_GOD_SELECTION_SOURCE_IDS:
                paragraph = repository.get_paragraph(source_id)
                if paragraph is None:
                    missing_ids.append(source_id)
                elif paragraph.is_editorial:
                    editorial_ids.append(source_id)
                else:
                    paragraphs.append(paragraph)
            if missing_ids or editorial_ids:
                details = []
                if missing_ids:
                    details.append(f"不存在：{', '.join(missing_ids)}")
                if editorial_ids:
                    details.append(f"仅为编辑按语：{', '.join(editorial_ids)}")
                raise KnowledgeBaseUnavailable(
                    "用神判定原文不可用（" + "；".join(details) + "）"
                )
            return tuple(paragraphs)

    def _retrieve_sources(self, result: DeterministicResult) -> tuple[ParagraphRecord, ...]:
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
                keywords=category.value,
                example_limit=4,
                fts_limit=8,
            )
            mandatory_ids = {
                fact.rule_source for fact in result.chart.facts
            } | {
                fact.rule_source for fact in result.rules.facts
            } | set(result.rules.useful_god.source_ids)
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
            stage_limits = {"fixed_pick": 20, "category": 18, "fact_tag": 18, "fts": 8}
            stage_counts = {stage: 0 for stage in stage_limits}
            for item in retrieved.paragraphs:
                if stage_counts.get(item.stage, 0) >= stage_limits.get(item.stage, 0):
                    continue
                before = len(ordered)
                add(item.paragraph)
                if len(ordered) > before:
                    stage_counts[item.stage] += 1
            for scored in retrieved.examples:
                for source_id in (
                    scored.example.question_id,
                    scored.example.chart_id,
                    scored.example.judgement_id,
                ):
                    if source_id:
                        add(repository.get_paragraph(source_id))
            return tuple(ordered)

    def _llm_context(
        self,
        result: DeterministicResult,
        sources: tuple[ParagraphRecord, ...],
    ) -> DivinationRequestContext:
        category = result.category
        assert category is not None
        facts = [
            self._chart_fact_context(fact) for fact in result.chart.facts
        ] + [
            self._rule_fact_context(fact) for fact in result.rules.facts
        ]
        source_contexts = self._source_contexts(sources)
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
            chart_summary={
                "calendar": result.calendar.model_dump(mode="json"),
                "primary": result.chart.primary.model_dump(mode="json"),
                "changed": result.chart.changed.model_dump(mode="json"),
                "lines": [line.model_dump(mode="json") for line in result.chart.lines],
                "line_order": result.chart.line_order,
            },
            useful_god=json.dumps(useful.model_dump(mode="json"), ensure_ascii=False),
            facts=facts,
            timing_candidates=timing,
            sources=source_contexts,
        )

    def _chart_response(self, result: DeterministicResult) -> ChartResponse:
        rules = result.rules
        summary = InputSummary(
            question=result.request.question,
            category=result.category.value if result.category else None,
            calendar=result.calendar.local_moment.isoformat(),
        )
        model_selected = result.useful_god_decision is not None
        return ChartResponse(
            input_summary=summary,
            calendar=result.calendar,
            primary_hexagram=result.chart.primary,
            changed_hexagram=result.chart.changed,
            lines=result.chart.lines,
            useful_god=rules.useful_god if model_selected else None,
            facts=result.chart.facts + rules.facts,
            timing_candidates=rules.timing_candidates if model_selected else (),
            limitations=(
                rules.unimplemented_rules
                if model_selected
                else (
                    "仅排盘接口不调用模型，因此不判定用神、元忌与应期",
                    *rules.unimplemented_rules,
                )
            ),
        )

    def _rule_context(
        self,
        request: DivinationRequest,
        calendar: Any,
        chart: Chart,
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
                    changed=changed,
                    hidden_spirit=hidden,
                )
            )
        void = calendar.day_pillar.void_branches
        return RuleContext(
            question=request.question,
            month_branch=calendar.month_pillar.ganzhi.branch,
            day_stem=calendar.day_pillar.ganzhi.stem,
            day_branch=calendar.day_pillar.ganzhi.branch,
            void_branches=(void.first, void.second),
            palace_element=RuleElement(chart.primary.palace_element.value),
            primary_hexagram=chart.primary.name,
            changed_hexagram=chart.changed.name,
            primary_is_six_clash=chart.primary.is_six_clash,
            primary_is_six_harmony=chart.primary.is_six_harmony,
            changed_is_six_clash=chart.changed.is_six_clash,
            changed_is_six_harmony=chart.changed.is_six_harmony,
            primary_is_wandering_soul=chart.primary.is_wandering_soul,
            primary_is_returning_soul=chart.primary.is_returning_soul,
            lines=tuple(lines),
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

    @staticmethod
    def _chart_fact_context(fact: Any) -> FactContext:
        property_ = None
        if fact.type == "MOVING":
            property_ = LineProperty.DONG
        elif fact.type == "STATIC":
            property_ = LineProperty.JING
        return FactContext(
            id=fact.id,
            type=fact.type,
            description=DivinationService._fact_description(fact),
            line=fact.line,
            value=True if property_ is not None else None,
            property=property_,
            rule_source=fact.rule_source,
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
            type=fact.type,
            description=DivinationService._fact_description(fact),
            line=fact.line,
            value=value,
            property=property_,
            rule_source=fact.rule_source,
            data={
                "value": fact.value,
                "related_lines": list(fact.related_lines),
                **fact.evidence,
            },
        )

    @staticmethod
    def _fact_description(fact: Any) -> str:
        value = json.dumps(fact.value, ensure_ascii=False)
        evidence = json.dumps(fact.evidence, ensure_ascii=False, sort_keys=True)
        line = f"第{fact.line}爻" if fact.line is not None else "全卦"
        return f"{line}；事实类型={fact.type}；结果={value}；参数={evidence}"

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
