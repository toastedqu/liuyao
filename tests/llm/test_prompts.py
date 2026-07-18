"""Tests for app.llm.prompts: system prompt constraints, user message
serialization and the correction-round message builder.
"""

from __future__ import annotations

import json

import pytest

from app.llm.base import Message
from app.llm.context import ExampleContext, SourceContext
from app.llm.prompts import (
    FORBIDDEN_TERMS,
    USEFUL_GOD_SYSTEM_PROMPT,
    build_correction_messages,
    build_messages,
    build_system_prompt,
    build_useful_god_selection_messages,
    build_useful_god_selection_user_message,
    build_user_message,
)
from app.llm.schemas import DivinationConclusion, UsefulGodDecision


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
    assert "不得因为没有与现代问题逐字相同" in prompt
    assert "明确显示了“属性=”的 fact_id" in prompt


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
    assert "timing-0001" in text
    assert "008_用神章:p0001" in text
    assert "用神旺相" in text  # source text is inlined verbatim
    assert "自占" not in text
    assert "代占" not in text


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
    assert "同占类：求财" in text
    theory_block = text.split("候选卦例", maxsplit=1)[0]
    assert "076_求财章:example0001:judgement" not in theory_block


def test_build_user_message_embeds_json_schema(sample_context) -> None:
    text = build_user_message(sample_context, DivinationConclusion)
    schema_json = json.dumps(DivinationConclusion.model_json_schema(), ensure_ascii=False)
    assert "Provider 已提供的 DivinationConclusion" in text
    assert schema_json not in text


def test_useful_god_selection_prompt_uses_question_and_source_only(
    sample_context,
) -> None:
    text = build_useful_god_selection_user_message(
        sample_context.question,
        sample_context.sources,
    )

    assert sample_context.question in text
    assert "008_用神章:p0001" in text
    assert "model-classified" not in text
    assert "chart_summary" not in text
    assert "Provider 已提供的 UsefulGodDecision" in text
    assert json.dumps(
        UsefulGodDecision.model_json_schema(),
        ensure_ascii=False,
    ) not in text


def test_useful_god_selection_messages_use_dedicated_system_prompt(
    sample_context,
) -> None:
    messages = build_useful_god_selection_messages(
        sample_context.question,
        sample_context.sources,
    )

    assert [message.role for message in messages] == ["system", "user"]
    assert messages[0].content == USEFUL_GOD_SYSTEM_PROMPT
    assert "不得假定页面另有自占、代占" in messages[0].content


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
