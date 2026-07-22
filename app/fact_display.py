"""Human-readable rendering for deterministic facts."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any, Final

from pydantic import JsonValue


LINE_NAMES: Final[tuple[str, ...]] = (
    "初爻",
    "二爻",
    "三爻",
    "四爻",
    "五爻",
    "上爻",
)

FACT_LAYER_LABELS: Final[dict[str, str]] = {
    "chart": "排盘层",
    "raw": "原始事实层",
    "derived": "推导事实层",
    "effective": "效力事实层",
}

FACT_VALUE_LABELS: Final[dict[str, str]] = {
    "activated_adverse": "暗动后形成不利作用",
    "activated_context": "暗动已激活，但仅作背景",
    "activated_favorable": "暗动后形成有利作用",
    "active_moving": "虽逢月破，但动爻仍可发挥作用",
    "adverse": "不利",
    "adverse_changed_to_official": "用神或元神化官鬼且无回头生，形成不利作用",
    "adverse_overrides_useful_strength": "变卦克本卦，不利作用成立",
    "adverse_real_tomb": "休囚受克且墓未冲开，随鬼入墓之凶成立",
    "adverse_return_harm": "反吟兼回头冲克，形成不利作用",
    "adverse_stagnation": "伏吟且用神不旺，阻滞不利",
    "conditional": "条件性作用",
    "conditional_near_event": "近事逢化进退，须结合应期条件判断",
    "conditional_opened_or_supported": "墓已冲开或目标得扶，仅作条件性影响",
    "conditional_outward_generation": "本卦生变卦，有外泄之象，作用取决于具体条件",
    "conditional_possible_scatter": "动爻受日冲且无扶，存在冲散可能",
    "conditional_release_when_clashed": "伏吟中用神旺，待冲可解",
    "conditional_reversal": "反吟且用神不旺，成败反复",
    "conditional_success": "反吟但用神旺，仍有条件可成",
    "conditional_supported": "得到生扶，原不利状态暂不按实害论",
    "conflict": "有用与无用条件并见",
    "conflict_with_return_generation": "化官鬼与回头生并见，作用相互冲突",
    "context_only": "仅作背景",
    "effective_adverse": "不利效力成立",
    "effective_empty": "旬空效力成立",
    "effective_empty_month_broken": "旬空兼月破，空破效力成立",
    "effective_support": "生扶效力成立",
    "effective_transformation": "变爻月破效力成立",
    "enemy": "仇神",
    "favorable": "有利",
    "generates_useful": "三合局生用神",
    "generates_world": "三合局生世爻",
    "inactive_static": "静爻月破且无生扶，月破效力成立",
    "neutral": "中性背景",
    "neutral_outward_control": "本卦克变卦，仅作中性外向制约",
    "nominal_only_moving": "仅名义旬空：动爻不为空",
    "nominal_only_supported": "仅名义旬空：得生扶不为空",
    "nominal_only_transformation": "仅名义旬空：变爻随动不为空",
    "not_scattered": "旺相或得扶，动爻受日冲而不散",
    "origin": "元神",
    "overcomes_useful": "三合局克用神",
    "overcomes_world": "三合局克世爻",
    "overridden_by_support": "墓绝得到生扶，不利作用被化解",
    "taboo": "忌神",
    "true_empty": "静而休囚无扶，真空成立",
    "unresolved": "暂未判定",
    "useful": "伏神有用",
    "useful_in_group_context": "用神入三合局，仅作格局背景",
    "useful_in_group_detained": "用神入三合局，有牵绊滞留之象",
    "useless": "伏神无用",
    "world_in_group": "世爻入三合局",
}

_ASCII_LETTER = re.compile(r"[A-Za-z]")
_FACT_ID = re.compile(r"^fact-\S+$")


def line_name(position: int) -> str:
    if type(position) is not int or not 1 <= position <= len(LINE_NAMES):
        raise ValueError(f"无效爻位：{position}")
    return LINE_NAMES[position - 1]


def fact_layer_label(layer: str) -> str:
    try:
        return FACT_LAYER_LABELS[layer]
    except KeyError as error:
        raise ValueError(f"事实层级未登记中文名称：{layer}") from error


def _localize_result_value(value: JsonValue) -> JsonValue:
    if value is None:
        return "无"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, str):
        if not _ASCII_LETTER.search(value) or _FACT_ID.fullmatch(value):
            return value
        try:
            return FACT_VALUE_LABELS[value]
        except KeyError as error:
            raise ValueError(f"事实结果未登记中文名称：{value}") from error
    if isinstance(value, list):
        return [_localize_result_value(item) for item in value]
    if isinstance(value, dict):
        localized: dict[str, JsonValue] = {}
        for key, item in value.items():
            if _ASCII_LETTER.search(key):
                raise ValueError(f"事实结果字段未登记中文名称：{key}")
            localized[key] = _localize_result_value(item)
        return localized
    return value


def _required_evidence(
    evidence: Mapping[str, JsonValue],
    key: str,
    expected_type: type,
) -> Any:
    value = evidence.get(key)
    if type(value) is not expected_type:
        raise ValueError(f"爻间五行生克事实缺少有效参数：{key}")
    return value


def describe_line_element_relation(fact: Any) -> str:
    """Describe the direction between both lines without relying on the fact ID."""
    evidence = fact.evidence
    if not isinstance(evidence, Mapping):
        raise ValueError("爻间五行生克事实的参数必须是映射")

    first_line = _required_evidence(evidence, "first_line", int)
    first_element = _required_evidence(evidence, "first_element", str)
    first_moving = _required_evidence(evidence, "first_moving", bool)
    second_line = _required_evidence(evidence, "second_line", int)
    second_element = _required_evidence(evidence, "second_element", str)
    second_moving = _required_evidence(evidence, "second_moving", bool)

    first = (
        f"{line_name(first_line)}（{first_element}，"
        f"{'动' if first_moving else '静'}）"
    )
    second = (
        f"{line_name(second_line)}（{second_element}，"
        f"{'动' if second_moving else '静'}）"
    )
    relation = fact.value
    if relation == "生":
        direction = f"{first}生{second}"
    elif relation == "克":
        direction = f"{first}克{second}"
    elif relation == "受生":
        direction = f"{second}生{first}"
    elif relation == "受克":
        direction = f"{second}克{first}"
    elif relation == "比和":
        direction = f"{first}与{second}比和"
    else:
        raise ValueError(f"未知的爻间五行关系：{relation}")

    return direction


def fact_result_for_display(fact: Any) -> JsonValue:
    if fact.type == "LINE_ELEMENT_RELATION":
        return describe_line_element_relation(fact)
    return _localize_result_value(fact.value)
