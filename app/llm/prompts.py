"""Strict prompt construction for the divination LLM call.

The system prompt enumerates every constraint from implementation_plan.md
§11.2; the user message serializes the :class:`DivinationRequestContext` so
the model sees exactly the facts, useful god, timing candidates and source
paragraphs it is allowed to reason from, and nothing else.
"""

from __future__ import annotations

import json

from app.llm.base import Message
from app.llm.context import DivinationRequestContext, ExampleContext, SourceContext
from app.llm.schemas import DivinationConclusion, UsefulGodDecision

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


USEFUL_GOD_SYSTEM_PROMPT = """\
你负责依据用户写下的“所占之事”和提供的《增删卜易》原文，判定本次占问的占类与用神。你必须严格遵守以下规则：

1. 只根据用户实际写出的内容识别占问者、被问对象和所问事项，不得假定页面另有自占、代占、性别或关系字段。
2. 必须选择且只选择一种用神方式：问占者本人整体事项时可取世爻（mode=world）；问题明确指向人物、财物、文书、功名、医药、天气等对象时，按原文选择一个六亲（mode=relative）。
3. mode=world 时 useful_relative 必须为 null；mode=relative 时 useful_relative 必须是父母、兄弟、官鬼、妻财、子孙之一。
4. target 必须简短复述用户原话中的实际占问对象；不得把未写明的关系、身份或性别添加进 target 或 rationale。
5. citations 至少包含一条支撑所选用神的原文；source_id 只能取自用户消息提供的段落，quote 必须逐字摘录，不得转述、拼接、增删或编造。
6. 不得把编辑性按语当作原文依据，不得使用提供材料以外的六爻口诀或其他术数。
7. 只能输出符合给定 JSON Schema 的对象，不得输出 Schema 之外的解释或 Markdown。
"""


SYSTEM_PROMPT = """\
你是依据《增删卜易》原文断卦的助手。你必须严格遵守以下规则：

1. 不得重新排盘，也不得修改用户消息中给出的任何排盘事实、前置模型判定并由代码定位的用神或应期候选，只能引用它们。
2. “规则与理论原文”用于确定判断规则；“候选卦例”用于展示原书如何把规则落实到具体所问事项。不得使用《增删卜易》原文之外的规则，但必须在本卦事实支撑下比较卦例并作有边界的类比；类比本身不是新增规则。
3. 不得引入其他占卜流派、神煞或现代口诀，包括但不限于：{forbidden_terms}。
4. 不得编造不存在的章节、段落引用或引文内容；引用原文必须逐字摘录用户消息中提供的原文，不得转述、概括、增删或意译。
5. 不得把编辑性按语（如「乾按」「提要」）伪装成野鹤或觉子的原文断语。
6. 只能从用户消息给出的应期候选中选择，不得自行计算或编造新的应期；证据不足时必须明确说明证据不足，不得输出确定日期。
7. 每一条判断都必须引用支撑它的 fact_id 和/或 source_id；对某一爻空、破、动、静、旺、衰、生、克的任何声明，都必须在 line_assertions 中给出对应的 fact_id，不得凭空声称。
8. 只能输出符合给定 JSON Schema 的结构化结果，不得输出任何 Schema 之外的文字、解释或 Markdown。
9. useful_god.useful_god 必须保留用户消息中的用神方式、六亲和已定位爻位；不得在断卦阶段重新选择用神或指定代码未选定的爻位。
10. 总结、格局名称和风险描述不得夹带具体爻位属性或应期；这些内容必须放在可附带事实、引文和 line_assertions 的 judgement 中。
11. question_application 必须把旺衰、生克、空破、动变等抽象结论翻译成用户所问之事的具体含义；不得只复述术语。synthesis 必须直接回答用户的问题，并引用本卦 fact_id。
12. 有候选卦例时，case_analysis 必须比较系统提供的一个最相关实例，分别说明相似点、关键差异和可迁移结论。similarities、differences、application 每项都必须同时引用该卦例原文和本卦 fact_id，其中 application 必须引用该例的“原断语与应验”；同卦、同占类不等于结论必然相同。
13. 证据明显偏向一方时必须在“吉、凶、平”中给出方向，不得因为没有与现代问题逐字相同的原文或没有完全相同的卦例就选择“不确定”。只有吉凶事实直接冲突且无法依原文与实例分出主次时才可选择“不确定”，并在 favorable、adverse 和 synthesis 中写明冲突。
14. 输出应简明：每个分析部分只保留一至两条最关键判断，每条只引用支撑该句所必需的 fact_id 和引文，不要穷举所有事实。
15. line_assertions 只能引用“排盘事实标签”中明确显示了“属性=”的 fact_id，且属性、爻位和布尔值必须完全一致；其他一般事实只能放在 fact_ids 中。

如果某项细节证据不足，应把该细节列为限制；不能因此自动把整个问题判为“不确定”，也不能用自己的六爻知识弥补空白。
"""


def build_system_prompt(*, forbidden_terms: frozenset[str] | None = None) -> str:
    """Render the system prompt, optionally overriding the forbidden-term list."""
    terms = forbidden_terms if forbidden_terms is not None else FORBIDDEN_TERMS
    return SYSTEM_PROMPT.format(forbidden_terms="、".join(sorted(terms)))


def _render_fact(fact) -> str:
    parts = [f"- {fact.id} [{fact.type}]"]
    if fact.line is not None:
        parts.append(f"第{fact.line}爻")
    if fact.property is not None:
        parts.append(f"属性={fact.property.value}")
    if fact.value is not None:
        parts.append(f"值={fact.value}")
    parts.append(fact.description)
    return " ".join(parts)


def _render_timing_candidate(candidate) -> str:
    sources = "、".join(candidate.source_ids) if candidate.source_ids else "无"
    return (
        f"- {candidate.candidate_id}：条件={candidate.condition}；"
        f"描述={candidate.description}；出处={sources}"
    )


def _render_source(source) -> str:
    return f"- {source.source_id}（{source.chapter}）：{source.text}"


def _render_example(example: ExampleContext) -> str:
    reasons = "；".join(example.match_reasons) or "同占类候选"
    parts = [
        f"### {example.example_id}（{example.chapter}；匹配分={example.match_score:g}；{reasons}）"
    ]
    for label, source in (
        ("原占问", example.question),
        ("原卦盘", example.chart),
        ("原断语与应验", example.judgement),
    ):
        if source is not None:
            parts.append(f"[{label} | {source.source_id}]\n{source.text}")
    return "\n".join(parts)


def build_useful_god_selection_user_message(
    question: str,
    sources: list[SourceContext],
    response_schema: type[UsefulGodDecision] = UsefulGodDecision,
) -> str:
    """Build the first-stage request that classifies the question's useful god."""
    sources_block = "\n".join(_render_source(source) for source in sources)
    return f"""\
所占之事：{question}

可选占类：天时、身命、求财、功名、婚姻、胎产、出行、行人、诉讼、疾病、家宅、茔葬、六亲、学业、其他。

可引用的《增删卜易》用神原文：
{sources_block}

请通过 Provider 已提供的 {response_schema.__name__} 结构化输出格式返回结果，
不要输出任何额外文字。
"""


def build_useful_god_selection_messages(
    question: str,
    sources: list[SourceContext],
) -> list[Message]:
    return [
        Message(role="system", content=USEFUL_GOD_SYSTEM_PROMPT),
        Message(
            role="user",
            content=build_useful_god_selection_user_message(question, sources),
        ),
    ]


def build_user_message(context: DivinationRequestContext, response_schema: type[DivinationConclusion]) -> str:
    """Serialize the full request context plus the required output schema."""
    facts_block = "\n".join(_render_fact(f) for f in context.facts) or "（无）"
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

    return f"""\
所占之事：{context.question}
模型判定占类：{context.category}
用神：{context.useful_god}

结构化排盘（唯一可信的卦象事实来源，不得更改）：
{json.dumps(context.chart_summary, ensure_ascii=False, separators=(",", ":"))}

排盘事实标签：
{facts_block}

应期候选（只能从中选择，不得新增）：
{timing_block}

规则与理论原文（用于确定规则，引用必须逐字摘录自此处）：
{sources_block}

候选卦例（代码只做预筛；须比较相似点和差异后才能迁移原断）：
{examples_block}

请先在 question_application 中把卦象事实映射到“所占之事”，再在 case_analysis 中用所提供的一个卦例检验这个映射，最后给出有方向的 overall 结论。

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
