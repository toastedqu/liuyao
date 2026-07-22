from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from app.fact_display import (
    FACT_VALUE_LABELS,
    describe_line_element_relation,
    fact_layer_label,
    fact_result_for_display,
)
from app.rules.models import FactLayer, RuleFact


@pytest.mark.parametrize(
    ("relation", "first_element", "second_element", "expected_direction"),
    (
        ("生", "木", "火", "初爻（木，静）生二爻（火，动）"),
        ("克", "木", "土", "初爻（木，静）克二爻（土，动）"),
        ("受生", "火", "木", "二爻（木，动）生初爻（火，静）"),
        ("受克", "木", "金", "二爻（金，动）克初爻（木，静）"),
        ("比和", "土", "土", "初爻（土，静）与二爻（土，动）比和"),
    ),
)
def test_line_element_relation_names_both_lines_and_direction(
    relation: str,
    first_element: str,
    second_element: str,
    expected_direction: str,
) -> None:
    fact = SimpleNamespace(
        value=relation,
        evidence={
            "first_line": 1,
            "first_element": first_element,
            "first_moving": False,
            "second_line": 2,
            "second_element": second_element,
            "second_moving": True,
        },
    )

    description = describe_line_element_relation(fact)

    assert description == expected_direction


def test_line_element_relation_rejects_incomplete_evidence() -> None:
    fact = SimpleNamespace(value="生", evidence={"first_line": 1})

    with pytest.raises(ValueError, match="缺少有效参数"):
        describe_line_element_relation(fact)


def test_every_machine_result_has_a_chinese_label() -> None:
    assert all(
        re.search(r"[\u4e00-\u9fff]", label)
        and re.search(r"[A-Za-z_]", label) is None
        for label in FACT_VALUE_LABELS.values()
    )


@pytest.mark.parametrize(
    ("machine_value", "expected"),
    (
        ("effective_support", "生扶效力成立"),
        ("nominal_only_moving", "仅名义旬空：动爻不为空"),
        ("not_scattered", "旺相或得扶，动爻受日冲而不散"),
        ("conditional_supported", "得到生扶，原不利状态暂不按实害论"),
        ("neutral_outward_control", "本卦克变卦，仅作中性外向制约"),
    ),
)
def test_fact_results_translate_machine_values(
    machine_value: str,
    expected: str,
) -> None:
    fact = SimpleNamespace(type="EFFECT", value=machine_value)

    assert fact_result_for_display(fact) == expected


def test_fact_results_translate_booleans_and_reject_unknown_machine_values() -> None:
    assert fact_result_for_display(
        SimpleNamespace(type="BOOLEAN", value=True)
    ) == "是"
    assert fact_layer_label("effective") == "效力事实层"

    with pytest.raises(ValueError, match="事实结果未登记中文名称"):
        fact_result_for_display(
            SimpleNamespace(type="EFFECT", value="unknown_machine_status")
        )


def test_rule_fact_json_serialization_never_exposes_machine_result_values() -> None:
    fact = RuleFact(
        id="fact-life-stage-effect-test",
        type="LIFE_STAGE_EFFECT",
        layer=FactLayer.EFFECTIVE,
        rule_id="ZSBY-030-LIFE-STAGE",
        value="effective_support",
        source_ids=("030_生旺墓绝章:p0005",),
        rule_source="030_生旺墓绝章:p0005",
    )

    serialized = fact.model_dump(mode="json")

    assert serialized["type"] == "本爻生旺墓绝效力"
    assert serialized["value"] == "生扶效力成立"
