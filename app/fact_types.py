"""Chinese display names for deterministic chart and rule fact types."""

from __future__ import annotations

from typing import Final


CHART_FACT_TYPE_LABELS: Final[dict[str, str]] = {
    "PRIMARY_HEXAGRAM": "主卦",
    "CHANGED_HEXAGRAM": "变卦",
    "LINE_POLARITY": "爻之阴阳",
    "MOVING": "动爻",
    "STATIC": "静爻",
    "NAJIA": "纳甲",
    "HIDDEN_SPIRIT": "伏神",
    "WORLD_LINE": "世爻",
    "RESPONSE_LINE": "应爻",
}

RULE_FACT_TYPE_LABELS: Final[dict[str, str]] = {
    "ADVANCE": "化进神",
    "ADVANCE_EFFECT": "化进神效力",
    "BRANCH_CLASH_PAIR": "地支相冲组合",
    "BRANCH_COMBINE_PAIR": "地支相合组合",
    "BRANCH_PUNISHMENT_PAIR": "地支相刑组合",
    "CHANGED_DAY_RELATION": "日辰对变爻作用",
    "CHANGED_ELEMENT_RELATION": "变爻对本爻生克",
    "CHANGED_LIFE_STAGE": "变爻生旺墓绝",
    "CHANGED_LIFE_STAGE_EFFECT": "变爻生旺墓绝效力",
    "CHANGED_MONTH_BREAK": "变爻月破",
    "CHANGED_MONTH_BREAK_EFFECT": "变爻月破效力",
    "CHANGED_SEASONAL_STRENGTH": "变爻四时旺衰",
    "CHANGED_SIX_CLASH": "变卦六冲",
    "CHANGED_SIX_HARMONY": "变卦六合",
    "CHANGED_TO_OFFICIAL": "动爻化官鬼",
    "CHANGED_TO_OFFICIAL_EFFECT": "化官鬼效力",
    "CHANGED_VOID": "变爻旬空",
    "CHANGED_VOID_EFFECT": "变爻旬空效力",
    "CLASH_TO_HARMONY": "六冲变六合",
    "DARK_MOVEMENT": "暗动",
    "DARK_MOVEMENT_EFFECT": "暗动效力",
    "DAY_BREAK": "日破",
    "DAY_COMBINE": "日辰合爻",
    "DAY_RELATION": "日辰对本爻作用",
    "DYNAMIC_LIFE_STAGE": "动爻引发的生旺墓绝",
    "DYNAMIC_LIFE_STAGE_EFFECT": "动爻引发的生旺墓绝效力",
    "ENEMY_GOD": "仇神",
    "FLYING_HIDDEN_RELATION": "飞伏生克关系",
    "GHOST_TOMB": "随鬼入墓",
    "HEXAGRAM_CHANGE_EFFECT": "卦变生克效力",
    "HEXAGRAM_CHANGE_RELATION": "卦变生克关系",
    "HIDDEN_DAY_RELATION": "日辰对伏神作用",
    "HIDDEN_LIFE_STAGE": "伏神生旺墓绝",
    "HIDDEN_MONTH_BREAK": "伏神月破",
    "HIDDEN_SEASONAL_STRENGTH": "伏神四时旺衰",
    "HIDDEN_SPIRIT_EFFECT": "伏神效力",
    "HIDDEN_VOID": "伏神旬空",
    "LIFE_STAGE": "本爻生旺墓绝",
    "LIFE_STAGE_EFFECT": "本爻生旺墓绝效力",
    "LINE_CLASH": "爻位相冲",
    "LINE_COMBINE": "爻位相合",
    "LINE_ELEMENT_RELATION": "爻间五行生克",
    "LINE_HARM": "爻位六害",
    "LINE_PUNISHMENT": "爻位相刑",
    "MONTH_BREAK": "月破",
    "MONTH_BREAK_EFFECT": "月破效力",
    "MONTH_COMBINE": "月建合爻",
    "MOVING_DAY_CLASH": "动爻逢日冲",
    "MOVING_DAY_CLASH_EFFECT": "动爻逢日冲效力",
    "MOVING_GENERATES_USEFUL": "动爻生用神",
    "MOVING_OVERCOMES_USEFUL": "动爻克用神",
    "PRIMARY_SIX_CLASH": "主卦六冲",
    "PRIMARY_SIX_HARMONY": "主卦六合",
    "REPEATED_CHANT": "伏吟",
    "REPEATED_CHANT_EFFECT": "伏吟效力",
    "RETREAT": "化退神",
    "RETREAT_EFFECT": "化退神效力",
    "RETURNING_SOUL": "归魂",
    "RETURN_CLASH": "回头冲",
    "RETURN_COMBINE": "回头合",
    "RETURN_GENERATE": "回头生",
    "RETURN_OVERCOME": "回头克",
    "REVERSE_CHANT": "反吟",
    "REVERSE_CHANT_EFFECT": "反吟效力",
    "SEASONAL_STRENGTH": "本爻四时旺衰",
    "SINGLE_MOVING": "独发",
    "SINGLE_STATIC": "独静",
    "SIX_GOD": "六神",
    "STAR_HAPPINESS": "天喜",
    "STAR_HORSE": "驿马",
    "STAR_LU": "禄神",
    "STAR_NOBLE": "太乙贵人",
    "TABOO_GOD": "忌神",
    "THREE_HARMONY": "三合成局",
    "THREE_HARMONY_EFFECT": "三合局效力",
    "THREE_HARMONY_PENDING": "三合待成",
    "THREE_HARMONY_WORLD_EFFECT": "三合局对世爻效力",
    "USEFUL_GOD": "用神",
    "USEFUL_GOD_MULTIPLE": "用神两现",
    "VOID_EFFECT": "旬空效力",
    "WANDERING_SOUL": "游魂",
    "YEAR_COMMAND": "太岁",
    "YUAN_GOD": "元神",
    "旬空": "旬空",
}

FACT_TYPE_LABELS: Final[dict[str, str]] = {
    **CHART_FACT_TYPE_LABELS,
    **RULE_FACT_TYPE_LABELS,
}
_KNOWN_LABELS = frozenset(FACT_TYPE_LABELS.values())


def fact_type_label(fact_type: str) -> str:
    """Return a Chinese label and reject unlocalized fact types."""
    if fact_type in _KNOWN_LABELS:
        return fact_type
    try:
        return FACT_TYPE_LABELS[fact_type]
    except KeyError as error:
        raise ValueError(f"事实类型未登记中文名称：{fact_type}") from error
