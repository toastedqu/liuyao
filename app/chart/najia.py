from __future__ import annotations

from dataclasses import dataclass

from app.chart.hexagrams import LineBits
from app.chart.models import Element, Relative


BRANCH_ELEMENTS: dict[str, Element] = {
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


@dataclass(frozen=True)
class TrigramNajia:
    inner_stem: str
    inner_branches: tuple[str, str, str]
    outer_stem: str
    outer_branches: tuple[str, str, str]


NAJIA: dict[str, TrigramNajia] = {
    "乾": TrigramNajia("甲", ("子", "寅", "辰"), "壬", ("午", "申", "戌")),
    "坎": TrigramNajia("戊", ("寅", "辰", "午"), "戊", ("申", "戌", "子")),
    "艮": TrigramNajia("丙", ("辰", "午", "申"), "丙", ("戌", "子", "寅")),
    "震": TrigramNajia("庚", ("子", "寅", "辰"), "庚", ("午", "申", "戌")),
    "巽": TrigramNajia("辛", ("丑", "亥", "酉"), "辛", ("未", "巳", "卯")),
    "离": TrigramNajia("己", ("卯", "丑", "亥"), "己", ("酉", "未", "巳")),
    "坤": TrigramNajia("乙", ("未", "巳", "卯"), "癸", ("丑", "亥", "酉")),
    "兑": TrigramNajia("丁", ("巳", "卯", "丑"), "丁", ("亥", "酉", "未")),
}


@dataclass(frozen=True)
class NajiaLine:
    stem: str
    branch: str
    element: Element


def install_najia(lower_trigram: str, upper_trigram: str) -> tuple[NajiaLine, ...]:
    inner = NAJIA[lower_trigram]
    outer = NAJIA[upper_trigram]
    return tuple(
        NajiaLine(inner.inner_stem, branch, BRANCH_ELEMENTS[branch])
        for branch in inner.inner_branches
    ) + tuple(
        NajiaLine(outer.outer_stem, branch, BRANCH_ELEMENTS[branch])
        for branch in outer.outer_branches
    )


def relative_for(palace_element: Element, line_element: Element) -> Relative:
    if line_element is palace_element:
        return Relative.SIBLING
    if GENERATES[line_element] is palace_element:
        return Relative.PARENT
    if GENERATES[palace_element] is line_element:
        return Relative.CHILD
    if OVERCOMES[line_element] is palace_element:
        return Relative.OFFICIAL
    return Relative.WEALTH

