from __future__ import annotations

from app.rules.models import Element, Relative


BRANCHES = ("子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥")
BRANCH_ELEMENT: dict[str, Element] = {
    "子": Element.WATER,
    "丑": Element.EARTH,
    "寅": Element.WOOD,
    "卯": Element.WOOD,
    "辰": Element.EARTH,
    "巳": Element.FIRE,
    "午": Element.FIRE,
    "未": Element.EARTH,
    "申": Element.METAL,
    "酉": Element.METAL,
    "戌": Element.EARTH,
    "亥": Element.WATER,
}

GENERATES: dict[Element, Element] = {
    Element.WOOD: Element.FIRE,
    Element.FIRE: Element.EARTH,
    Element.EARTH: Element.METAL,
    Element.METAL: Element.WATER,
    Element.WATER: Element.WOOD,
}
OVERCOMES: dict[Element, Element] = {
    Element.WOOD: Element.EARTH,
    Element.EARTH: Element.WATER,
    Element.WATER: Element.FIRE,
    Element.FIRE: Element.METAL,
    Element.METAL: Element.WOOD,
}

CLASH: dict[str, str] = {
    "子": "午",
    "午": "子",
    "丑": "未",
    "未": "丑",
    "寅": "申",
    "申": "寅",
    "卯": "酉",
    "酉": "卯",
    "辰": "戌",
    "戌": "辰",
    "巳": "亥",
    "亥": "巳",
}
COMBINE: dict[str, str] = {
    "子": "丑",
    "丑": "子",
    "寅": "亥",
    "亥": "寅",
    "卯": "戌",
    "戌": "卯",
    "辰": "酉",
    "酉": "辰",
    "巳": "申",
    "申": "巳",
    "午": "未",
    "未": "午",
}
HARM: dict[str, str] = {
    "子": "未",
    "未": "子",
    "丑": "午",
    "午": "丑",
    "寅": "巳",
    "巳": "寅",
    "卯": "辰",
    "辰": "卯",
    "申": "亥",
    "亥": "申",
    "酉": "戌",
    "戌": "酉",
}
PUNISHMENTS = {
    frozenset(("寅", "巳")),
    frozenset(("巳", "申")),
    frozenset(("申", "寅")),
    frozenset(("子", "卯")),
    frozenset(("丑", "戌")),
    frozenset(("戌", "未")),
}
SELF_PUNISHMENT = frozenset(("辰", "午", "酉", "亥"))

THREE_HARMONIES: dict[tuple[str, str, str], Element] = {
    ("申", "子", "辰"): Element.WATER,
    ("巳", "酉", "丑"): Element.METAL,
    ("寅", "午", "戌"): Element.FIRE,
    ("亥", "卯", "未"): Element.WOOD,
}

GROWTH: dict[Element, str] = {
    Element.METAL: "巳",
    Element.WOOD: "亥",
    Element.FIRE: "寅",
    Element.WATER: "申",
    Element.EARTH: "申",
}
PROSPERITY: dict[Element, str] = {
    Element.METAL: "酉",
    Element.WOOD: "卯",
    Element.FIRE: "午",
    Element.WATER: "子",
    Element.EARTH: "子",
}
TOMB: dict[Element, str] = {
    Element.METAL: "丑",
    Element.WOOD: "未",
    Element.FIRE: "戌",
    Element.WATER: "辰",
    Element.EARTH: "辰",
}
EXTINCTION: dict[Element, str] = {
    Element.METAL: "寅",
    Element.WOOD: "申",
    Element.FIRE: "亥",
    Element.WATER: "巳",
    Element.EARTH: "巳",
}

ADVANCE_PAIRS = {
    ("寅", "卯"),
    ("巳", "午"),
    ("申", "酉"),
    ("亥", "子"),
    ("丑", "辰"),
    ("辰", "未"),
    ("未", "戌"),
    ("戌", "丑"),
}
RETREAT_PAIRS = {(target, source) for source, target in ADVANCE_PAIRS}

TAIYI_NOBLE: dict[str, frozenset[str]] = {
    "甲": frozenset(("丑", "未")),
    "戊": frozenset(("丑", "未")),
    "庚": frozenset(("丑", "未")),
    "乙": frozenset(("子", "申")),
    "己": frozenset(("子", "申")),
    "丙": frozenset(("亥", "酉")),
    "丁": frozenset(("亥", "酉")),
    "壬": frozenset(("卯", "巳")),
    "癸": frozenset(("卯", "巳")),
    "辛": frozenset(("午", "寅")),
}
LU_SHEN: dict[str, str] = {
    "甲": "寅",
    "乙": "卯",
    "丙": "巳",
    "戊": "巳",
    "丁": "午",
    "己": "午",
    "庚": "申",
    "辛": "酉",
    "壬": "亥",
    "癸": "子",
}
YI_MA: dict[str, str] = {
    "申": "寅",
    "子": "寅",
    "辰": "寅",
    "巳": "亥",
    "酉": "亥",
    "丑": "亥",
    "寅": "申",
    "午": "申",
    "戌": "申",
    "亥": "巳",
    "卯": "巳",
    "未": "巳",
}
TIAN_XI: dict[str, str] = {
    "寅": "戌",
    "卯": "戌",
    "辰": "戌",
    "巳": "丑",
    "午": "丑",
    "未": "丑",
    "申": "辰",
    "酉": "辰",
    "戌": "辰",
    "亥": "未",
    "子": "未",
    "丑": "未",
}


def generates(source: Element, target: Element) -> bool:
    return GENERATES[source] is target


def overcomes(source: Element, target: Element) -> bool:
    return OVERCOMES[source] is target


def source_element_for(target: Element) -> Element:
    return next(source for source, generated in GENERATES.items() if generated is target)


def overcoming_element_for(target: Element) -> Element:
    return next(source for source, overcome in OVERCOMES.items() if overcome is target)


def relative_for(palace: Element, line: Element) -> Relative:
    if line is palace:
        return Relative.SIBLING
    if generates(line, palace):
        return Relative.PARENT
    if generates(palace, line):
        return Relative.CHILD
    if overcomes(line, palace):
        return Relative.OFFICIAL
    return Relative.WEALTH


def relation_between(source: Element, target: Element) -> str:
    if source is target:
        return "比和"
    if generates(source, target):
        return "生"
    if overcomes(source, target):
        return "克"
    if generates(target, source):
        return "受生"
    return "受克"


def is_punishment(first: str, second: str) -> bool:
    if first == second:
        return first in SELF_PUNISHMENT
    return frozenset((first, second)) in PUNISHMENTS


def validate_branch(branch: str) -> None:
    if branch not in BRANCH_ELEMENT:
        raise ValueError(f"未知地支：{branch}")
