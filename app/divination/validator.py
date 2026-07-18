"""Fact-and-citation validator for LLM断卦 output (implementation_plan.md §12).

This module never calls a model. It takes the already-parsed
:class:`app.llm.schemas.DivinationConclusion` returned by an
``app.llm.base.LLMProvider`` plus the :class:`app.llm.context.DivinationRequestContext`
that was sent to it, and checks:

1. every ``fact_id`` exists in this turn's chart facts;
2. every citation's ``source_id`` exists in this turn's retrieved sources;
3. every citation's ``quote`` is a verbatim substring of that source's text;
4. every selected timing candidate id exists in this turn's timing candidates
   (and ``insufficient_evidence`` is not combined with a non-empty selection);
5. every ``line_assertion`` (a claim that some line is 空/破/动/静/旺/衰/生/克)
   is backed by a fact_id whose recorded line/property/value actually agrees;
6. no forbidden term (other schools, modern idioms, etc.) appears in any
   free-text field.
7. the concrete question synthesis is backed by current-chart facts;
8. every case comparison names a provided example and links that example's
   exact text and outcome to current-chart facts;
9. ``不确定`` is reserved for an explicit unresolved conflict between
   favorable and adverse evidence, not used as a generic safe fallback.

``ValidationResult.issues`` carries everything a caller (``app.divination.service``,
not part of this task) needs to build exactly one correction round via
``app.llm.prompts.build_correction_messages`` -- this module only describes
the errors, it does not build prompts or call the model itself.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from app.llm.context import DivinationRequestContext, FactContext, SourceContext
from app.llm.prompts import FORBIDDEN_TERMS
from app.llm.schemas import (
    DivinationConclusion,
    Judgement,
    LineProperty,
    TimingSelection,
    UsefulGodDecision,
)


_LINE_NAMES = {"初": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "上": 6}
_LINE_REFERENCE_RE = re.compile(
    r"(?:(?:第(?P<ordinal>[一二三四五六1-6]))|(?P<named>[初一二三四五上1-5]))爻"
)
_PROPERTY_TERMS: dict[LineProperty, tuple[str, ...]] = {
    LineProperty.KONG: ("旬空", "空亡", "临空", "值空", "落空"),
    LineProperty.PO: ("月破", "日破", "临破", "值破"),
    LineProperty.DONG: ("动爻", "发动", "暗动"),
    LineProperty.JING: ("静爻", "安静", "不动"),
    LineProperty.WANG: ("旺相", "临月建", "临日建", "得令"),
    LineProperty.SHUAI: ("休囚", "衰弱", "无气"),
    LineProperty.SHENG: ("回头生", "生扶", "相生"),
    LineProperty.KE: ("回头克", "克制", "克害", "受克"),
}
_BRANCH_TIME_RE = re.compile(r"([子丑寅卯辰巳午未申酉戌亥])(?:日|月|年|时)")
_ABSOLUTE_DATE_RE = re.compile(
    r"(?:\d{4}年(?:\d{1,2}月)?(?:\d{1,2}日)?|\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2})"
)
_RELATIVE_NAMES = ("父母", "兄弟", "官鬼", "妻财", "子孙")


def _line_number(match: re.Match[str]) -> int:
    token = match.group("ordinal") or match.group("named")
    return int(token) if token.isdigit() else _LINE_NAMES[token]


class ValidationIssue(BaseModel):
    """One concrete, machine-readable validation failure."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(description="稳定的错误代码，例如 unknown_fact_id、fact_conflict")
    path: str = Field(description="出问题的字段路径，例如 overall.judgements[0].fact_ids[1]")
    message: str = Field(description="供人阅读、也可直接用于构造模型纠正提示的中文说明")
    details: dict = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Aggregate outcome of validating one ``DivinationConclusion``."""

    model_config = ConfigDict(frozen=True)

    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    def correction_messages(self) -> list[str]:
        """The Chinese error descriptions to feed into one correction round."""
        return [issue.message for issue in self.issues]

    def format_for_correction(self) -> str:
        """Render all issues as a numbered Chinese bullet list."""
        lines = [f"{i}. [{issue.code}] {issue.path}：{issue.message}" for i, issue in enumerate(self.issues, start=1)]
        return "\n".join(lines)


def validate_divination_conclusion(
    conclusion: DivinationConclusion,
    context: DivinationRequestContext,
    *,
    forbidden_terms: Iterable[str] | None = None,
) -> ValidationResult:
    """Validate ``conclusion`` against everything available in ``context``."""
    facts_by_id: dict[str, FactContext] = {fact.id: fact for fact in context.facts}
    source_ids = {source.source_id for source in context.sources}
    candidate_ids = {candidate.candidate_id for candidate in context.timing_candidates}
    terms = tuple(forbidden_terms) if forbidden_terms is not None else tuple(FORBIDDEN_TERMS)

    issues: list[ValidationIssue] = []

    for path, judgement in conclusion.iter_judgements():
        _check_judgement_evidence(path, judgement, issues)
        _check_fact_ids(path, judgement, facts_by_id, issues)
        _check_citations(path, judgement, source_ids, context, issues)
        _check_line_assertions(path, judgement, facts_by_id, issues)
        _check_prose_line_claims(path, judgement, issues)
        _check_timing_claims(
            f"{path}.statement",
            judgement.statement,
            conclusion.timing,
            context,
            issues,
        )
        _check_forbidden_terms(f"{path}.statement", judgement.statement, terms, issues)

    _check_question_application(conclusion, facts_by_id, issues)
    _check_case_analysis(conclusion, context, facts_by_id, issues)
    _check_useful_god(conclusion, context, issues)
    unstructured_texts = [
        ("overall.summary", conclusion.overall.summary),
        ("question_application.focus", conclusion.question_application.focus),
        ("useful_god.useful_god", conclusion.useful_god.useful_god),
    ]
    for pi, pattern in enumerate(conclusion.special_patterns.patterns):
        unstructured_texts.append(
            (f"special_patterns.patterns[{pi}].name", pattern.name)
        )
    for ri, item in enumerate(conclusion.risks.items):
        unstructured_texts.append((f"risks.items[{ri}].description", item.description))
    for path, text in unstructured_texts:
        _check_timing_claims(path, text, conclusion.timing, context, issues)
        _check_unstructured_line_claims(path, text, issues)
        _check_forbidden_terms(path, text, terms, issues)

    _check_timing_selection(conclusion.timing, candidate_ids, issues)

    return ValidationResult(valid=not issues, issues=issues)


def validate_useful_god_decision(
    decision: UsefulGodDecision,
    sources: list[SourceContext],
    *,
    forbidden_terms: Iterable[str] | None = None,
) -> ValidationResult:
    """Validate the first-stage model decision's citations and terminology."""
    sources_by_id = {source.source_id: source for source in sources}
    terms = tuple(forbidden_terms) if forbidden_terms is not None else tuple(FORBIDDEN_TERMS)
    issues: list[ValidationIssue] = []

    for index, citation in enumerate(decision.citations):
        source = sources_by_id.get(citation.source_id)
        if source is None:
            issues.append(
                ValidationIssue(
                    code="unknown_source_id",
                    path=f"citations[{index}].source_id",
                    message=(
                        f"用神判定引用了未提供的原文出处「{citation.source_id}」；"
                        "只能引用本轮给出的用神原文。"
                    ),
                    details={"source_id": citation.source_id},
                )
            )
            continue
        if citation.quote.strip() not in source.text:
            issues.append(
                ValidationIssue(
                    code="citation_quote_mismatch",
                    path=f"citations[{index}].quote",
                    message=(
                        f"用神判定引用「{citation.source_id}」的文字「{citation.quote}」"
                        "与知识库原文不完全一致，必须逐字摘录。"
                    ),
                    details={
                        "source_id": citation.source_id,
                        "quote": citation.quote,
                    },
                )
            )

    _check_forbidden_terms("target", decision.target, terms, issues)
    _check_forbidden_terms("rationale", decision.rationale, terms, issues)
    return ValidationResult(valid=not issues, issues=issues)


def _judgement_fact_ids(judgement: Judgement) -> set[str]:
    return set(judgement.fact_ids) | {
        assertion.fact_id
        for assertion in judgement.line_assertions
        if assertion.fact_id is not None
    }


def _check_question_application(
    conclusion: DivinationConclusion,
    facts_by_id: dict[str, FactContext],
    issues: list[ValidationIssue],
) -> None:
    synthesis = conclusion.question_application.synthesis
    if not (_judgement_fact_ids(synthesis) & facts_by_id.keys()):
        issues.append(
            ValidationIssue(
                code="question_synthesis_missing_current_fact",
                path="question_application.synthesis",
                message=(
                    "对用户具体问题的综合判断没有引用任何本卦事实；"
                    "synthesis 必须把至少一个本次排盘 fact_id 落实到所占之事，"
                    "不能只复述理论原文。"
                ),
            )
        )

    if conclusion.overall.outlook != "不确定":
        return

    favorable_ids = set().union(
        *(
            _judgement_fact_ids(judgement) & facts_by_id.keys()
            for judgement in conclusion.question_application.favorable
        ),
        set(),
    )
    adverse_ids = set().union(
        *(
            _judgement_fact_ids(judgement) & facts_by_id.keys()
            for judgement in conclusion.question_application.adverse
        ),
        set(),
    )
    synthesis_ids = _judgement_fact_ids(synthesis) & facts_by_id.keys()
    has_two_sided_conflict = (
        bool(favorable_ids - adverse_ids)
        and bool(adverse_ids - favorable_ids)
        and bool(synthesis_ids & favorable_ids)
        and bool(synthesis_ids & adverse_ids)
    )
    if not has_two_sided_conflict:
        issues.append(
            ValidationIssue(
                code="uncertain_without_explicit_conflict",
                path="overall.outlook",
                message=(
                    "总体结论选择了“不确定”，但有利与不利部分没有分别引用不同的"
                    "本卦事实，或 synthesis 没有同时综合两侧事实。"
                    "没有完全相同的原文或卦例不能作为不确定的理由；若证据已有方向，"
                    "请改判吉、凶或平，只有无法分出主次的直接冲突才可保留不确定。"
                ),
            )
        )


def _check_case_analysis(
    conclusion: DivinationConclusion,
    context: DivinationRequestContext,
    facts_by_id: dict[str, FactContext],
    issues: list[ValidationIssue],
) -> None:
    examples_by_id = {example.example_id: example for example in context.examples}
    comparisons = conclusion.case_analysis.comparisons
    if examples_by_id and not comparisons:
        issues.append(
            ValidationIssue(
                code="case_comparison_required",
                path="case_analysis.comparisons",
                message=(
                    "本轮提供了一个候选卦例，但输出没有进行实例比照；"
                    "请说明该例与本卦的相似点、差异和对本问的可迁移结论。"
                ),
            )
        )

    seen: set[str] = set()
    for index, comparison in enumerate(comparisons):
        path = f"case_analysis.comparisons[{index}]"
        if comparison.example_id in seen:
            issues.append(
                ValidationIssue(
                    code="duplicate_case_comparison",
                    path=f"{path}.example_id",
                    message=f"卦例「{comparison.example_id}」被重复比较，请保留一次。",
                )
            )
        seen.add(comparison.example_id)

        example = examples_by_id.get(comparison.example_id)
        if example is None:
            issues.append(
                ValidationIssue(
                    code="unknown_example_id",
                    path=f"{path}.example_id",
                    message=(
                        f"实例比照引用了未提供的卦例「{comparison.example_id}」；"
                        "只能使用本轮候选卦例。"
                    ),
                    details={"example_id": comparison.example_id},
                )
            )
            continue

        example_source_ids = {
            source.source_id
            for source in (example.question, example.chart, example.judgement)
            if source is not None
        }
        for field, judgement in (
            ("similarities", comparison.similarities),
            ("differences", comparison.differences),
            ("application", comparison.application),
        ):
            cited_ids = {citation.source_id for citation in judgement.citations}
            if not (cited_ids & example_source_ids):
                issues.append(
                    ValidationIssue(
                        code="case_comparison_missing_case_citation",
                        path=f"{path}.{field}.citations",
                        message=(
                            f"卦例「{comparison.example_id}」的{field}没有引用该实例的"
                            "原占问、卦盘或原断语，不能证明正在比较这个实例。"
                        ),
                    )
                )
            if not (_judgement_fact_ids(judgement) & facts_by_id.keys()):
                issues.append(
                    ValidationIssue(
                        code="case_comparison_missing_current_fact",
                        path=f"{path}.{field}.fact_ids",
                        message=(
                            f"卦例「{comparison.example_id}」的{field}没有引用本卦 fact_id；"
                            "实例只能在本卦事实支持下类比，不能直接套用原例结论。"
                        ),
                    )
                )

        application_citations = {
            citation.source_id for citation in comparison.application.citations
        }
        if example.judgement.source_id not in application_citations:
            issues.append(
                ValidationIssue(
                    code="case_application_missing_outcome",
                    path=f"{path}.application.citations",
                    message=(
                        f"卦例「{comparison.example_id}」的迁移判断没有引用其原断语"
                        f"「{example.judgement.source_id}」；必须先说明原例如何断，"
                        "再结合本卦事实决定哪些结论可迁移。"
                    ),
                )
            )


def _check_useful_god(
    conclusion: DivinationConclusion,
    context: DivinationRequestContext,
    issues: list[ValidationIssue],
) -> None:
    expected_relative: str | None = None
    expected_line: int | None = None
    expected_mode: str | None = None
    try:
        expected = json.loads(context.useful_god)
    except (json.JSONDecodeError, TypeError):
        expected_relative = context.useful_god
    else:
        if isinstance(expected, dict):
            relative = expected.get("useful_relative")
            line = expected.get("selected_line")
            mode = expected.get("selection_mode")
            expected_relative = relative if isinstance(relative, str) else None
            expected_line = line if isinstance(line, int) else None
            expected_mode = mode if mode in {"world", "relative"} else None
        elif isinstance(expected, str):
            expected_relative = expected

    if expected_mode != "world" and expected_relative not in _RELATIVE_NAMES:
        return

    actual = conclusion.useful_god.useful_god
    mentioned = {relative for relative in _RELATIVE_NAMES if relative in actual}
    if expected_mode == "world":
        conflict = "世爻" not in actual
        if mentioned:
            conflict = (
                conflict
                or expected_relative not in mentioned
                or bool(mentioned - {expected_relative})
            )
    else:
        conflict = expected_relative not in mentioned or bool(
            mentioned - {expected_relative}
        )
    line_matches = list(_LINE_REFERENCE_RE.finditer(actual))
    if line_matches:
        claimed_lines = {_line_number(match) for match in line_matches}
        conflict = conflict or expected_line is None or claimed_lines != {expected_line}
    if conflict:
        issues.append(
            ValidationIssue(
                code="useful_god_conflict",
                path="useful_god.useful_god",
                message=(
                    f"断卦输出的用神「{actual}」与前置模型判定并由代码定位的用神"
                    f"「{'世爻' if expected_mode == 'world' else expected_relative}"
                    f"{f'（第{expected_line}爻）' if expected_line else ''}」不一致；"
                    "断卦阶段不得重新选择或改写用神。"
                ),
                details={
                    "expected_mode": expected_mode,
                    "expected_relative": expected_relative,
                    "expected_line": expected_line,
                    "actual": actual,
                },
            )
        )


def _check_judgement_evidence(
    path: str,
    judgement: Judgement,
    issues: list[ValidationIssue],
) -> None:
    assertion_fact_ids = {
        assertion.fact_id
        for assertion in judgement.line_assertions
        if assertion.fact_id is not None
    }
    if judgement.fact_ids or judgement.citations or assertion_fact_ids:
        return
    issues.append(
        ValidationIssue(
            code="judgement_missing_evidence",
            path=path,
            message=(
                f"判断「{judgement.statement}」没有引用任何 fact_id 或 source_id；"
                "每条判断必须引用本次排盘事实或检索到的《增删卜易》原文。"
            ),
        )
    )


def _check_fact_ids(
    path: str,
    judgement: Judgement,
    facts_by_id: dict[str, FactContext],
    issues: list[ValidationIssue],
) -> None:
    for i, fact_id in enumerate(judgement.fact_ids):
        if fact_id not in facts_by_id:
            issues.append(
                ValidationIssue(
                    code="unknown_fact_id",
                    path=f"{path}.fact_ids[{i}]",
                    message=(
                        f"判断「{judgement.statement}」引用了不存在的事实ID「{fact_id}」，"
                        "请仅引用本次排盘提供的事实ID，或删除该引用。"
                    ),
                    details={"fact_id": fact_id},
                )
            )


def _check_citations(
    path: str,
    judgement: Judgement,
    source_ids: set[str],
    context: DivinationRequestContext,
    issues: list[ValidationIssue],
) -> None:
    sources_by_id = {source.source_id: source for source in context.sources}
    for i, citation in enumerate(judgement.citations):
        if citation.source_id not in source_ids:
            issues.append(
                ValidationIssue(
                    code="unknown_source_id",
                    path=f"{path}.citations[{i}].source_id",
                    message=(
                        f"判断「{judgement.statement}」引用了不存在的原文出处「{citation.source_id}」，"
                        "请仅引用本次检索到的原文段落，不得编造章节或引用ID。"
                    ),
                    details={"source_id": citation.source_id},
                )
            )
            continue
        source_text = sources_by_id[citation.source_id].text
        if citation.quote.strip() not in source_text:
            issues.append(
                ValidationIssue(
                    code="citation_quote_mismatch",
                    path=f"{path}.citations[{i}].quote",
                    message=(
                        f"判断「{judgement.statement}」引用「{citation.source_id}」的文字"
                        f"「{citation.quote}」与知识库原文不完全一致，必须逐字摘录原文，"
                        f"不得转述、增删或概括。原文为：{source_text}"
                    ),
                    details={"source_id": citation.source_id, "quote": citation.quote},
                )
            )


def _check_line_assertions(
    path: str,
    judgement: Judgement,
    facts_by_id: dict[str, FactContext],
    issues: list[ValidationIssue],
) -> None:
    for i, assertion in enumerate(judgement.line_assertions):
        assertion_path = f"{path}.line_assertions[{i}]"
        if assertion.fact_id is None:
            issues.append(
                ValidationIssue(
                    code="line_assertion_missing_fact",
                    path=assertion_path,
                    message=(
                        f"判断「{judgement.statement}」声称第{assertion.line}爻"
                        f"{'具有' if assertion.asserted else '不具有'}「{assertion.property.value}」，"
                        "但未引用任何事实ID；六爻的空、破、动、旺、衰、生克等属性必须依据"
                        "本次排盘事实，不得凭空声称。"
                    ),
                    details={"line": assertion.line, "property": assertion.property.value},
                )
            )
            continue

        fact = facts_by_id.get(assertion.fact_id)
        if fact is None:
            issues.append(
                ValidationIssue(
                    code="unknown_fact_id",
                    path=f"{assertion_path}.fact_id",
                    message=(
                        f"判断「{judgement.statement}」引用了不存在的事实ID「{assertion.fact_id}」"
                        f"来支撑第{assertion.line}爻的属性声明。"
                    ),
                    details={"fact_id": assertion.fact_id},
                )
            )
            continue

        if fact.line is None:
            issues.append(
                ValidationIssue(
                    code="line_assertion_fact_has_no_line",
                    path=f"{assertion_path}.fact_id",
                    message=(
                        f"判断「{judgement.statement}」声称第{assertion.line}爻的属性，"
                        f"但事实「{assertion.fact_id}」不对应任何具体爻位，不能支撑该声明。"
                    ),
                    details={"fact_id": assertion.fact_id, "claimed_line": assertion.line},
                )
            )
        elif fact.line != assertion.line:
            issues.append(
                ValidationIssue(
                    code="line_assertion_line_mismatch",
                    path=f"{assertion_path}.line",
                    message=(
                        f"判断「{judgement.statement}」声称第{assertion.line}爻的属性，"
                        f"但引用的事实「{assertion.fact_id}」实际对应第{fact.line}爻，请核对爻位。"
                    ),
                    details={"fact_id": assertion.fact_id, "claimed_line": assertion.line, "fact_line": fact.line},
                )
            )

        if fact.property is None:
            issues.append(
                ValidationIssue(
                    code="line_assertion_fact_has_no_property",
                    path=f"{assertion_path}.fact_id",
                    message=(
                        f"判断「{judgement.statement}」声称第{assertion.line}爻具有"
                        f"「{assertion.property.value}」，但事实「{assertion.fact_id}」"
                        "没有该规范化属性，不能用来支撑此声明。"
                    ),
                    details={"fact_id": assertion.fact_id},
                )
            )
        elif fact.property != assertion.property:
            issues.append(
                ValidationIssue(
                    code="line_assertion_property_mismatch",
                    path=f"{assertion_path}.property",
                    message=(
                        f"判断「{judgement.statement}」声称第{assertion.line}爻具有"
                        f"「{assertion.property.value}」，但事实「{assertion.fact_id}」记录的属性为"
                        f"「{fact.property.value}」，两者不一致。"
                    ),
                    details={
                        "fact_id": assertion.fact_id,
                        "claimed": assertion.property.value,
                        "actual": fact.property.value,
                    },
                )
            )

        if fact.value is not None and bool(fact.value) != assertion.asserted:
            issues.append(
                ValidationIssue(
                    code="fact_conflict",
                    path=f"{assertion_path}.asserted",
                    message=(
                        f"判断「{judgement.statement}」声称第{assertion.line}爻"
                        f"{'具有' if assertion.asserted else '不具有'}「{assertion.property.value}」，"
                        f"但排盘事实「{assertion.fact_id}」显示结果为{'是' if fact.value else '否'}，"
                        "与断语矛盾，请依据实际排盘事实重新表述。"
                    ),
                    details={
                        "fact_id": assertion.fact_id,
                        "claimed": assertion.asserted,
                        "actual": bool(fact.value),
                    },
                )
            )


def _check_prose_line_claims(
    path: str,
    judgement: Judgement,
    issues: list[ValidationIssue],
) -> None:
    assertions = {
        (assertion.line, assertion.property)
        for assertion in judgement.line_assertions
    }
    matches = list(_LINE_REFERENCE_RE.finditer(judgement.statement))
    for match in matches:
        line = _line_number(match)
        start = max(0, match.start() - 12)
        end = min(len(judgement.statement), match.end() + 12)
        nearby = judgement.statement[start:end]
        for property_, terms in _PROPERTY_TERMS.items():
            if not any(term in nearby for term in terms):
                continue
            if (line, property_) in assertions:
                continue
            issues.append(
                ValidationIssue(
                    code="prose_line_claim_missing_assertion",
                    path=f"{path}.statement",
                    message=(
                        f"判断「{judgement.statement}」在正文中声称第{line}爻具有"
                        f"「{property_.value}」相关属性，但未在 line_assertions 中"
                        "提供对应爻位、属性和事实ID，无法核对该说法。"
                    ),
                    details={"line": line, "property": property_.value},
                )
            )


def _check_unstructured_line_claims(
    path: str,
    text: str,
    issues: list[ValidationIssue],
) -> None:
    for match in _LINE_REFERENCE_RE.finditer(text):
        line = _line_number(match)
        start = max(0, match.start() - 12)
        end = min(len(text), match.end() + 12)
        nearby = text[start:end]
        for property_, terms in _PROPERTY_TERMS.items():
            if not any(term in nearby for term in terms):
                continue
            issues.append(
                ValidationIssue(
                    code="line_claim_outside_judgement",
                    path=path,
                    message=(
                        f"字段「{text}」声称第{line}爻具有「{property_.value}」相关属性，"
                        "但该字段不能提供 line_assertions；请把此说法移入判断并引用对应事实ID。"
                    ),
                    details={"line": line, "property": property_.value},
                )
            )


def _check_timing_claims(
    path: str,
    text: str,
    timing: TimingSelection,
    context: DivinationRequestContext,
    issues: list[ValidationIssue],
) -> None:
    if _ABSOLUTE_DATE_RE.search(text):
        issues.append(
            ValidationIssue(
                code="unauthorized_absolute_timing",
                path=path,
                message=(
                    f"文本「{text}」输出了代码候选未提供的绝对日期；"
                    "应期只能从系统生成的候选中选择，不能自行换算日期。"
                ),
            )
        )

    candidates = {
        candidate.candidate_id: candidate
        for candidate in context.timing_candidates
    }
    selected_descriptions = "；".join(
        candidates[candidate_id].description
        for candidate_id in timing.candidate_ids
        if candidate_id in candidates
    )
    for branch in _BRANCH_TIME_RE.findall(text):
        if branch in selected_descriptions:
            continue
        issues.append(
            ValidationIssue(
                code="unauthorized_timing_claim",
                path=path,
                message=(
                    f"文本「{text}」声称以「{branch}」为应期，但选中的代码候选"
                    "不包含该地支；只能陈述所选候选实际提供的应期。"
                ),
                details={"branch": branch},
            )
        )


def _check_forbidden_terms(
    path: str,
    text: str,
    terms: tuple[str, ...],
    issues: list[ValidationIssue],
) -> None:
    if not text:
        return
    for term in terms:
        if term and term in text:
            issues.append(
                ValidationIssue(
                    code="forbidden_term",
                    path=path,
                    message=(
                        f"文本「{text}」中出现了不属于《增删卜易》的术语「{term}」，"
                        "请删除该内容或改用书中原有说法。"
                    ),
                    details={"term": term},
                )
            )


def _check_timing_selection(
    timing: TimingSelection,
    candidate_ids: set[str],
    issues: list[ValidationIssue],
) -> None:
    for i, candidate_id in enumerate(timing.candidate_ids):
        if candidate_id not in candidate_ids:
            issues.append(
                ValidationIssue(
                    code="unknown_timing_candidate",
                    path=f"timing.candidate_ids[{i}]",
                    message=(
                        f"应期选择引用了不存在的候选ID「{candidate_id}」，只能从系统提供的应期候选"
                        "中选择，不得自行编造新的应期。"
                    ),
                    details={"candidate_id": candidate_id},
                )
            )

    if timing.insufficient_evidence and timing.candidate_ids:
        issues.append(
            ValidationIssue(
                code="timing_evidence_conflict",
                path="timing.candidate_ids",
                message=(
                    "已标注 insufficient_evidence=true（证据不足），但仍选择了应期候选，"
                    "两者矛盾；证据不足时不得输出确定应期，candidate_ids 必须为空。"
                ),
                details={"candidate_ids": list(timing.candidate_ids)},
            )
        )
