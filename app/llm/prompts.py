"""Strict prompt construction for the divination LLM call.

The system prompt enumerates every constraint from implementation_plan.md
§11.2; the user message serializes the :class:`DivinationRequestContext` so
the model sees exactly the facts, useful god, timing candidates and source
paragraphs it is allowed to reason from, and nothing else.
"""

from __future__ import annotations

import json

from app.fact_display import fact_layer_label, line_name
from app.fact_types import fact_type_label
from app.llm.base import Message
from app.llm.context import (
    DecisionEvidenceContext,
    DivinationRequestContext,
    ExampleContext,
    SourceContext,
)
from app.llm.schemas import DivinationConclusion, QuestionCategory

#: Representative terms from other divination schools, modern idioms, or
#: pseudo-scientific framings that must never appear in a断卦结果. This is a
#: starting set, not an exhaustive blocklist -- callers (prompts and the
#: validator) may extend it with additional terms discovered in practice.
FORBIDDEN_TERMS: frozenset[str] = frozenset(
    {
        "紫微斗数",
        "奇门遁甲",
        "梅花易数",
        "六壬",
        "太乙神数",
        "四柱八字",
        "生辰八字",
        "塔罗牌",
        "占星术",
        "星座运势",
        "风水罗盘",
        "现代心理学",
        "概率论",
        "统计学模型",
        "人工智能预测",
        "量子力学",
    }
)


QUESTION_CATEGORY_SYSTEM_PROMPT = """\
你只负责提取用户问题的占类与问占视角，不负责排盘、选择或修改用神，也不解释任何六爻规则。你必须严格遵守以下规则：

1. category 必须从给定占类中选择一个最贴近用户核心问题的值，不得拒绝选择或输出歧义状态。
2. 恋爱、择偶、婚恋关系及夫妻关系归入“婚姻”；工作职位与考试功名归入“功名”；收入、交易与财物归入“求财”。
3. perspective 必须选择“自占”或“代占”。问自己的财运、工作、婚恋、疾病、出行等均为“自占”；明确替父母、子女、伴侣、亲友或其他人问其吉凶为“代占”。不得把“我问与某人的关系”误作替对方代占。
4. 用户已经另行选择用神；不得根据问题改选世爻、应爻或任何六亲。
5. 只能输出符合给定 JSON Schema 的对象，不得输出 Schema 之外的解释或 Markdown。
"""


SYSTEM_PROMPT = """\
你是依据《增删卜易》原文断卦的助手。你必须严格遵守以下规则：

1. 不得重新排盘，也不得修改用户选择并由代码定位的用神、任何排盘事实或应期候选，只能引用它们。
2. “本卦裁决证据”是唯一允许决定总体吉凶方向的事实集合；“规则与理论原文”只解释这些事实如何权衡；“候选卦例”仅供完成主判断后的方法参考，既不是吉凶票数，也不得改变已经依据本卦裁决证据形成的方向。不得使用《增删卜易》原文之外的规则。
3. 不得引入其他占卜流派、神煞或现代口诀，包括但不限于：{forbidden_terms}。
4. 不得编造不存在的章节、段落引用或引文内容；引用原文必须逐字摘录用户消息中提供的原文，不得转述、概括、增删或意译。
5. 不得把编辑性按语（如「乾按」「提要」）伪装成野鹤或觉子的原文断语。
6. 只能从用户消息给出的应期候选中选择，不得自行计算或编造新的应期；证据不足时必须明确说明证据不足，不得输出确定日期。
7. 每一条判断都必须引用支撑它的 fact_id 和/或 source_id；对某一爻空、破、动、静、旺、衰、生、克的任何声明，都必须在 line_assertions 中给出对应的 fact_id，不得凭空声称。
8. 只能输出符合给定 JSON Schema 的结构化结果，不得输出任何 Schema 之外的文字、解释或 Markdown。
9. useful_god.useful_god 必须保留用户消息中的用神方式、六亲和已定位爻位；不得在断卦阶段重新选择用神或指定代码未选定的爻位。
10. 总结、格局名称和风险描述不得夹带具体爻位属性或应期；这些内容必须放在可附带事实、引文和 line_assertions 的 judgement 中。
11. question_application 必须把旺衰、生克、空破、动变等抽象结论翻译成用户所问之事的具体含义；不得只复述术语。favorable 只能把标为“有利”的裁决证据解释为本问的有利因素，adverse 只能把标为“不利”的裁决证据解释为不利因素；synthesis 必须直接回答用户问题并引用裁决证据所列 fact_id，不能只引用普通排盘事实。
12. 有候选卦例时，case_analysis 必须在主判断完成后作一次参考比照，role 固定为 reference_only。similarities、differences、application 每项须连接原例和本卦事实，但 application 只能说明原例的判断方法在本卦何处适用、何处不适用，不得用原例结果支持或推翻 overall。
13. overall.outlook 必须严格服从本轮给出的“允许总体结论”：仅有利主证只能为“吉”，仅不利主证只能为“凶”，正反证据并见只能为“吉中有阻”或“凶中有救”，暂不裁决只能为“需再占”。“吉中有阻”须以有利为主且综合两侧，“凶中有救”须以不利为主且综合两侧。不得输出“平”或“不确定”，也不得因为没有完全相同的卦例改变结论集合。
14. 输出应简明：每个分析部分只保留一至两条最关键判断，每条只引用支撑该句所必需的 fact_id 和引文，不要穷举所有事实。
15. line_assertions 只能引用“排盘事实标签”中明确显示了“属性=”的 fact_id，且属性、爻位和布尔值必须完全一致；其他一般事实只能放在 fact_ids 中。

16. 不得把普通的主卦名、变卦名、六冲、六合、游魂、归魂，或元神/忌神“出现”本身当作吉凶证据；只有“本卦裁决证据”明确列出的有利、不利或条件性作用才可进入综合。空破、休囚、动爻也不能脱离有根无根、有力无力、元忌同动及生克多少机械贴标签。

如果某项细节证据不足，应把该细节列为限制；不能用自己的六爻知识弥补空白。质量控制为“暂不裁决”时只能输出“需再占”，并明确裁决层为何保留，不得伪造单向主证。
"""


def build_system_prompt(*, forbidden_terms: frozenset[str] | None = None) -> str:
    """Render the system prompt, optionally overriding the forbidden-term list."""
    terms = forbidden_terms if forbidden_terms is not None else FORBIDDEN_TERMS
    return SYSTEM_PROMPT.format(forbidden_terms="、".join(sorted(terms)))


def _render_fact(fact) -> str:
    parts = [f"- {fact.id} [{fact_type_label(fact.type)}]"]
    parts.append(f"层级={fact_layer_label(fact.layer)}")
    if fact.line is not None:
        parts.append(f"第{fact.line}爻")
    if fact.related_lines:
        parts.append(
            "相关爻位="
            + "、".join(line_name(position) for position in fact.related_lines)
        )
    if fact.property is not None:
        # fact.value is always literally True whenever property is set
        # (see DivinationService._chart_fact_context/_rule_fact_context), so
        # rendering it separately would just repeat "属性=" with no new
        # information.
        parts.append(f"属性={fact.property.value}")
    parts.append(fact.description)
    return " ".join(parts)


def _render_timing_candidate(candidate) -> str:
    sources = "、".join(candidate.source_ids) if candidate.source_ids else "无"
    return (
        f"- {candidate.candidate_id}：条件={candidate.condition}；"
        f"描述={candidate.description}；出处={sources}"
    )


def _render_source(source) -> str:
    # source_id already encodes the chapter (e.g. "008_用神章:p0001"), so a
    # separate "（章节标题）" suffix would just repeat it verbatim.
    return f"- {source.source_id}：{source.text}"


def _render_example(example: ExampleContext) -> str:
    parts = [f"### {example.example_id}（仅作方法参考）"]
    for label, source in (
        ("原占问", example.question),
        ("原卦盘", example.chart),
        ("原断语与应验", example.judgement),
    ):
        if source is not None:
            parts.append(f"[{label} | {source.source_id}]\n{source.text}")
    return "\n".join(parts)


def _render_decision_evidence(evidence: DecisionEvidenceContext) -> str:
    facts = "、".join(evidence.fact_ids)
    sources = "、".join(evidence.source_ids) or "见事实自身出处"
    return (
        f"- {evidence.evidence_id} [{evidence.direction}/{evidence.weight}] "
        f"{evidence.description}；可引用事实={facts}；规则出处={sources}"
    )


def build_question_category_user_message(
    question: str,
    response_schema: type[QuestionCategory] = QuestionCategory,
) -> str:
    """Build the first-stage request that classifies only the question category."""
    return f"""\
所占之事：{question}

可选占类：天时、身命、求财、功名、婚姻、胎产、出行、行人、诉讼、疾病、家宅、茔葬、六亲、学业、其他。
问占视角：自占、代占。

请通过 Provider 已提供的 {response_schema.__name__} 结构化输出格式返回结果，
不要输出任何额外文字。
"""


def build_question_category_messages(
    question: str,
) -> list[Message]:
    return [
        Message(role="system", content=QUESTION_CATEGORY_SYSTEM_PROMPT),
        Message(
            role="user",
            content=build_question_category_user_message(question),
        ),
    ]


def build_user_message(context: DivinationRequestContext, response_schema: type[DivinationConclusion]) -> str:
    """Serialize the full request context plus the required output schema."""
    facts_block = "\n".join(_render_fact(f) for f in context.facts) or "（无）"
    decision_block = (
        "\n".join(
            _render_decision_evidence(evidence)
            for evidence in context.decision_evidence
        )
        or "（裁决层没有足以定向的证据）"
    )
    decision_limitations = "；".join(context.decision_limitations) or "无"
    timing_block = "\n".join(_render_timing_candidate(c) for c in context.timing_candidates) or "（无可用候选，须说明证据不足）"
    example_source_ids = {
        source.source_id
        for example in context.examples
        for source in (example.question, example.chart, example.judgement)
        if source is not None
    }
    theory_sources = [
        source for source in context.sources if source.source_id not in example_source_ids
    ]
    sources_block = "\n".join(_render_source(s) for s in theory_sources) or "（无检索结果）"
    examples_block = "\n\n".join(_render_example(e) for e in context.examples) or "（无匹配卦例）"
    allowed_outlooks = {
        "仅有利主证": "吉",
        "仅不利主证": "凶",
        "正反证据并见": "吉中有阻、凶中有救",
        "暂不裁决": "需再占",
    }.get(context.decision_guardrail, "需再占")

    return f"""\
所占之事：{context.question}
模型判定占类：{context.category}
模型判定问占视角：{context.perspective}
用神：{context.useful_god}

结构化排盘（唯一可信的卦象事实来源，不得更改）：
{json.dumps(context.chart_summary, ensure_ascii=False, separators=(",", ":"))}

排盘事实标签：
{facts_block}

本卦裁决证据（唯一可决定总体方向；不得把候选卦例计入）：
质量控制={context.decision_guardrail}
允许总体结论={allowed_outlooks}
限制={decision_limitations}
{decision_block}

应期候选（只能从中选择，不得新增）：
{timing_block}

规则与理论原文（用于确定规则，引用必须逐字摘录自此处）：
{sources_block}

候选卦例（仅作主判断完成后的方法参考；不提供匹配分，不参与吉凶权重）：
{examples_block}

请先完全不依赖卦例结果，只按“本卦裁决证据”和规则原文完成 overall 与 question_application；再以 role=reference_only 完成 case_analysis，说明参考边界，不得回改主判断方向。

请通过 Provider 已提供的 {response_schema.__name__} 结构化输出格式返回结果，
不要输出任何额外文字。
"""


def build_messages(
    context: DivinationRequestContext,
    response_schema: type[DivinationConclusion],
    *,
    forbidden_terms: frozenset[str] | None = None,
) -> list[Message]:
    """Build the initial ``[system, user]`` message pair for one LLM call."""
    return [
        Message(role="system", content=build_system_prompt(forbidden_terms=forbidden_terms)),
        Message(role="user", content=build_user_message(context, response_schema)),
    ]


def build_correction_messages(
    original_messages: list[Message],
    previous_response_json: str,
    issue_descriptions: list[str],
) -> list[Message]:
    """Append one correction round to ``original_messages``.

    ``issue_descriptions`` are human-readable Chinese error descriptions
    (typically ``[issue.message for issue in validation_result.issues]`` from
    ``app.divination.validator``). The validator never calls this itself --
    it is the caller's (``app.divination.service``'s) job to feed validator
    output back into one correction round, per implementation_plan.md §12.
    """
    if not issue_descriptions:
        raise ValueError("issue_descriptions 不能为空：没有错误时不需要构造纠正提示")
    bullet_list = "\n".join(f"{i}. {desc}" for i, desc in enumerate(issue_descriptions, start=1))
    correction_text = (
        "上一次的结构化结果未通过校验，存在以下问题，请逐条修正后重新输出"
        "完整的、符合原 JSON Schema 的结构化结果（不要只输出差异或说明文字）：\n"
        f"{bullet_list}"
    )
    return [
        *original_messages,
        Message(role="assistant", content=previous_response_json),
        Message(role="user", content=correction_text),
    ]
