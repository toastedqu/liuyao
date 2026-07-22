"""Tests for app.llm.prompts: system prompt constraints, user message
serialization and the correction-round message builder.
"""

from __future__ import annotations

import json
import re

import pytest

from app.llm.base import Message
from app.llm.context import ExampleContext, FactContext, SourceContext
from app.llm.prompts import (
    FORBIDDEN_TERMS,
    QUESTION_CATEGORY_SYSTEM_PROMPT,
    build_correction_messages,
    build_messages,
    build_question_category_messages,
    build_question_category_user_message,
    build_system_prompt,
    build_user_message,
)
from app.llm.schemas import DivinationConclusion, QuestionCategory


def test_system_prompt_lists_all_forbidden_actions() -> None:
    prompt = build_system_prompt()
    assert "不得重新排盘" in prompt
    assert "不得使用《增删卜易》原文之外" in prompt
    assert "不得引入其他占卜流派" in prompt
    assert "不得编造不存在的章节" in prompt
    assert "乾按" in prompt
    assert "只能从用户消息给出的应期候选中选择" in prompt
    assert "line_assertions" in prompt
    assert "候选卦例" in prompt
    assert "不得因为没有完全相同的卦例" in prompt
    assert "明确显示了“属性=”的 fact_id" in prompt
    assert "唯一允许决定总体吉凶方向" in prompt
    assert "必须以最终效力说明" in prompt
    assert "卦例结果影响而判凶" not in prompt


def test_system_prompt_includes_forbidden_terms() -> None:
    prompt = build_system_prompt()
    for term in FORBIDDEN_TERMS:
        assert term in prompt


def test_system_prompt_honors_custom_forbidden_terms() -> None:
    prompt = build_system_prompt(forbidden_terms=frozenset({"自定义术语"}))
    assert "自定义术语" in prompt
    assert "紫微斗数" not in prompt


def test_build_user_message_includes_all_context_sections(sample_context) -> None:
    text = build_user_message(sample_context, DivinationConclusion)
    assert sample_context.question in text
    assert sample_context.category in text
    assert "妻财" in text
    assert "fact-0001" in text
    assert "本卦裁决证据" in text
    assert "质量控制=仅有利主证" in text
    assert "test-favorable" in text
    assert "timing-0001" in text
    assert "008_用神章:p0001" in text
    assert "用神旺相" in text  # source text is inlined verbatim
    assert "模型判定问占视角：自占" in text
    assert "月破：三爻月破" in text
    assert "爻体：兄弟 乙丑土，朱雀，阴爻，发动" in text
    assert "变爻：官鬼 丙寅木（阳）" in text
    assert "属性=动；事实编号=fact-0002" in text
    assert "动爻：是" not in text
    assert "MONTH_BREAK" not in text
    assert "MOVING" not in text
    facts_block = text.split(
        "卦象事实（按全卦、初爻至上爻归类；事实编号仅用于引用校验）：\n",
        maxsplit=1,
    )[1].split(
        "\n\n本卦裁决证据",
        maxsplit=1,
    )[0]
    assert re.findall(
        r"^### (全卦|初爻|二爻|三爻|四爻|五爻|上爻)$",
        facts_block,
        re.MULTILINE,
    ) == ["全卦", "初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]
    assert next(
        line for line in facts_block.splitlines() if "fact-0001" in line
    ).endswith("〔事实编号=fact-0001〕")
    facts_without_ids = re.sub(r"fact-\S+", "", facts_block)
    assert re.search(r"[A-Za-z]", facts_without_ids) is None


def test_build_user_message_names_both_lines_in_relation_facts(
    sample_context,
) -> None:
    relation = FactContext(
        id="fact-line-element-relation-l1-l2",
        type="爻间五行生克",
        layer="raw",
        description="结果=二爻（土，动）生初爻（金，静）",
        related_lines=[1, 2],
    )
    context = sample_context.model_copy(update={"facts": [relation]})

    text = build_user_message(context, DivinationConclusion)

    assert "爻间五行生克：二爻（土，动）生初爻（金，静）" in text
    assert "ZSBY" not in text
    assert "关联爻位=初爻、二爻" in text
    assert "二爻（土，动）生初爻（金，静）" in text
    global_block = text.split("### 全卦\n", maxsplit=1)[1].split(
        "\n\n### 初爻",
        maxsplit=1,
    )[0]
    assert relation.id in global_block
    assert text.count(relation.id) == 1


def test_build_user_message_consolidates_line_body_facts(sample_context) -> None:
    body_facts = [
        FactContext(
            id="fact-polarity",
            type="LINE_POLARITY",
            description="结果=阳",
            line=1,
        ),
        FactContext(
            id="fact-static",
            type="STATIC",
            description="结果=是",
            line=1,
            value=True,
            property="静",
        ),
        FactContext(
            id="fact-najia",
            type="NAJIA",
            description="结果=甲子",
            line=1,
        ),
        FactContext(
            id="fact-spirit",
            type="SIX_GOD",
            layer="raw",
            description="结果=青龙",
            line=1,
        ),
        FactContext(
            id="fact-hidden",
            type="HIDDEN_SPIRIT",
            description="结果=父母",
            line=1,
        ),
        FactContext(
            id="fact-month-break",
            type="MONTH_BREAK",
            layer="raw",
            description="结果=月破",
            line=1,
        ),
    ]
    context = sample_context.model_copy(update={"facts": body_facts})

    text = build_user_message(context, DivinationConclusion)
    first_line_block = text.split("### 初爻\n", maxsplit=1)[1].split(
        "\n\n### 二爻",
        maxsplit=1,
    )[0]

    assert (
        "爻体：妻财 甲子水，青龙，阳爻，安静；伏神：父母 庚午火"
        in first_line_block
    )
    assert "属性=静；事实编号=fact-static" in first_line_block
    assert "fact-polarity" in first_line_block
    assert "fact-najia" in first_line_block
    assert "fact-spirit" in first_line_block
    assert "fact-hidden" in first_line_block
    assert "爻之阴阳：" not in first_line_block
    assert "静爻：" not in first_line_block
    assert "纳甲：" not in first_line_block
    assert "六神：" not in first_line_block
    assert "\n- 伏神：" not in first_line_block
    assert "月破：月破" in first_line_block


def test_build_user_message_orders_each_line_by_fact_layer(sample_context) -> None:
    context = sample_context.model_copy(
        update={
            "facts": [
                FactContext(
                    id="fact-effective",
                    type="MONTH_BREAK_EFFECT",
                    layer="effective",
                    description="月破效力成立",
                    line=1,
                ),
                FactContext(
                    id="fact-derived",
                    type="USEFUL_GOD",
                    layer="derived",
                    description="此爻为用神",
                    line=1,
                ),
                FactContext(
                    id="fact-raw",
                    type="MONTH_BREAK",
                    layer="raw",
                    description="此爻月破",
                    line=1,
                ),
                FactContext(
                    id="fact-chart",
                    type="NAJIA",
                    description="甲子水",
                    line=1,
                ),
            ]
        }
    )

    text = build_user_message(context, DivinationConclusion)
    first_line_block = text.split("### 初爻\n", maxsplit=1)[1].split(
        "\n\n### 二爻",
        maxsplit=1,
    )[0]

    assert (
        first_line_block.index("fact-chart")
        < first_line_block.index("fact-raw")
        < first_line_block.index("fact-derived")
        < first_line_block.index("fact-effective")
    )


def test_build_user_message_groups_worked_examples_separately(sample_context) -> None:
    question = SourceContext(
        source_id="076_求财章:example0001:question",
        chapter="求财章",
        text="占求财，得泽火革。",
    )
    judgement = SourceContext(
        source_id="076_求财章:example0001:judgement",
        chapter="求财章",
        text="断曰：如缘木以求鱼也。",
    )
    context = sample_context.model_copy(
        update={
            "sources": [*sample_context.sources, question, judgement],
            "examples": [
                ExampleContext(
                    example_id="076_求财章:example0001",
                    chapter="求财章",
                    match_score=8.5,
                    match_reasons=["同占类：求财"],
                    question=question,
                    judgement=judgement,
                )
            ],
        }
    )

    text = build_user_message(context, DivinationConclusion)

    assert "候选卦例" in text
    assert "076_求财章:example0001" in text
    assert "原断语与应验" in text
    assert "仅作方法参考" in text
    assert "匹配分=" not in text
    assert "同占类：求财" not in text
    theory_block = text.split("候选卦例", maxsplit=1)[0]
    assert "076_求财章:example0001:judgement" not in theory_block


def test_build_user_message_embeds_json_schema(sample_context) -> None:
    text = build_user_message(sample_context, DivinationConclusion)
    schema_json = json.dumps(DivinationConclusion.model_json_schema(), ensure_ascii=False)
    assert "Provider 已提供的 DivinationConclusion" in text
    assert schema_json not in text


def test_question_category_prompt_uses_question_without_divination_rules(
    sample_context,
) -> None:
    text = build_question_category_user_message(sample_context.question)

    assert sample_context.question in text
    assert "008_用神章:p0001" not in text
    assert "父母爻" not in text
    assert "model-classified" not in text
    assert "chart_summary" not in text
    assert "Provider 已提供的 QuestionCategory" in text
    assert "问占视角：自占、代占" in text
    assert json.dumps(
        QuestionCategory.model_json_schema(),
        ensure_ascii=False,
    ) not in text


def test_question_category_messages_use_dedicated_system_prompt(
    sample_context,
) -> None:
    messages = build_question_category_messages(sample_context.question)

    assert [message.role for message in messages] == ["system", "user"]
    assert messages[0].content == QUESTION_CATEGORY_SYSTEM_PROMPT
    assert "不得拒绝选择或输出歧义状态" in messages[0].content
    assert "用户已经另行选择用神" in messages[0].content
    assert "明确替父母、子女、伴侣" in messages[0].content


def test_build_messages_returns_system_then_user(sample_context) -> None:
    messages = build_messages(sample_context, DivinationConclusion)
    assert [m.role for m in messages] == ["system", "user"]
    assert messages[0].content == build_system_prompt()


def test_build_correction_messages_appends_assistant_and_correction_turns() -> None:
    original = [Message(role="system", content="sys"), Message(role="user", content="usr")]
    corrected = build_correction_messages(original, '{"bad": true}', ["第一条错误", "第二条错误"])

    assert corrected[:2] == original
    assert corrected[2].role == "assistant"
    assert corrected[2].content == '{"bad": true}'
    assert corrected[3].role == "user"
    assert "第一条错误" in corrected[3].content
    assert "第二条错误" in corrected[3].content
    assert "1. 第一条错误" in corrected[3].content
    assert "2. 第二条错误" in corrected[3].content


def test_build_correction_messages_requires_at_least_one_issue() -> None:
    original = [Message(role="system", content="sys")]
    with pytest.raises(ValueError):
        build_correction_messages(original, "{}", [])
