from __future__ import annotations

from dataclasses import dataclass

from app.chart.models import Element, Hexagram


LineBits = tuple[bool, bool, bool, bool, bool, bool]
TrigramBits = tuple[bool, bool, bool]

TRIGRAM_BITS: dict[str, TrigramBits] = {
    "乾": (True, True, True),
    "兑": (True, True, False),
    "离": (True, False, True),
    "震": (True, False, False),
    "巽": (False, True, True),
    "坎": (False, True, False),
    "艮": (False, False, True),
    "坤": (False, False, False),
}
BITS_TO_TRIGRAM = {bits: name for name, bits in TRIGRAM_BITS.items()}

PALACE_ELEMENTS: dict[str, Element] = {
    "乾": Element.METAL,
    "兑": Element.METAL,
    "坎": Element.WATER,
    "坤": Element.EARTH,
    "艮": Element.EARTH,
    "离": Element.FIRE,
    "震": Element.WOOD,
    "巽": Element.WOOD,
}

HEXAGRAM_NAMES: dict[tuple[str, str], str] = {
    ("乾", "乾"): "乾为天",
    ("乾", "兑"): "天泽履",
    ("乾", "离"): "天火同人",
    ("乾", "震"): "天雷无妄",
    ("乾", "巽"): "天风姤",
    ("乾", "坎"): "天水讼",
    ("乾", "艮"): "天山遁",
    ("乾", "坤"): "天地否",
    ("兑", "乾"): "泽天夬",
    ("兑", "兑"): "兑为泽",
    ("兑", "离"): "泽火革",
    ("兑", "震"): "泽雷随",
    ("兑", "巽"): "泽风大过",
    ("兑", "坎"): "泽水困",
    ("兑", "艮"): "泽山咸",
    ("兑", "坤"): "泽地萃",
    ("离", "乾"): "火天大有",
    ("离", "兑"): "火泽睽",
    ("离", "离"): "离为火",
    ("离", "震"): "火雷噬嗑",
    ("离", "巽"): "火风鼎",
    ("离", "坎"): "火水未济",
    ("离", "艮"): "火山旅",
    ("离", "坤"): "火地晋",
    ("震", "乾"): "雷天大壮",
    ("震", "兑"): "雷泽归妹",
    ("震", "离"): "雷火丰",
    ("震", "震"): "震为雷",
    ("震", "巽"): "雷风恒",
    ("震", "坎"): "雷水解",
    ("震", "艮"): "雷山小过",
    ("震", "坤"): "雷地豫",
    ("巽", "乾"): "风天小畜",
    ("巽", "兑"): "风泽中孚",
    ("巽", "离"): "风火家人",
    ("巽", "震"): "风雷益",
    ("巽", "巽"): "巽为风",
    ("巽", "坎"): "风水涣",
    ("巽", "艮"): "风山渐",
    ("巽", "坤"): "风地观",
    ("坎", "乾"): "水天需",
    ("坎", "兑"): "水泽节",
    ("坎", "离"): "水火既济",
    ("坎", "震"): "水雷屯",
    ("坎", "巽"): "水风井",
    ("坎", "坎"): "坎为水",
    ("坎", "艮"): "水山蹇",
    ("坎", "坤"): "水地比",
    ("艮", "乾"): "山天大畜",
    ("艮", "兑"): "山泽损",
    ("艮", "离"): "山火贲",
    ("艮", "震"): "山雷颐",
    ("艮", "巽"): "山风蛊",
    ("艮", "坎"): "山水蒙",
    ("艮", "艮"): "艮为山",
    ("艮", "坤"): "山地剥",
    ("坤", "乾"): "地天泰",
    ("坤", "兑"): "地泽临",
    ("坤", "离"): "地火明夷",
    ("坤", "震"): "地雷复",
    ("坤", "巽"): "地风升",
    ("坤", "坎"): "地水师",
    ("坤", "艮"): "地山谦",
    ("坤", "坤"): "坤为地",
}

PALACE_STAGES = ("本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂")
WORLD_LINES = (6, 1, 2, 3, 4, 5, 4, 3)

SIX_CLASH_NAMES = {
    "乾为天",
    "兑为泽",
    "离为火",
    "震为雷",
    "巽为风",
    "坎为水",
    "艮为山",
    "坤为地",
    "天雷无妄",
    "雷天大壮",
}
SIX_HARMONY_NAMES = {
    "天地否",
    "地天泰",
    "水泽节",
    "泽水困",
    "山火贲",
    "火山旅",
    "雷地豫",
    "地雷复",
}


@dataclass(frozen=True)
class PalacePlacement:
    palace: str
    sequence_index: int


def _palace_sequence(palace: str) -> tuple[LineBits, ...]:
    pure = list(TRIGRAM_BITS[palace] + TRIGRAM_BITS[palace])
    result = [tuple(pure)]
    current = pure.copy()
    for position in range(5):
        current[position] = not current[position]
        result.append(tuple(current))
    current[3] = not current[3]
    result.append(tuple(current))
    for position in range(3):
        current[position] = not current[position]
    result.append(tuple(current))
    return tuple(result)  # type: ignore[return-value]


PALACE_BY_LINES: dict[LineBits, PalacePlacement] = {}
for _palace in TRIGRAM_BITS:
    for _sequence_index, _lines in enumerate(_palace_sequence(_palace)):
        if _lines in PALACE_BY_LINES:
            raise RuntimeError(f"八宫序列重复：{_lines}")
        PALACE_BY_LINES[_lines] = PalacePlacement(_palace, _sequence_index)
if len(PALACE_BY_LINES) != 64:
    raise RuntimeError(f"八宫序列未覆盖六十四卦：{len(PALACE_BY_LINES)}")


def identify_hexagram(lines: LineBits) -> Hexagram:
    lower = BITS_TO_TRIGRAM[lines[:3]]
    upper = BITS_TO_TRIGRAM[lines[3:]]
    placement = PALACE_BY_LINES[lines]
    sequence_index = placement.sequence_index
    world = WORLD_LINES[sequence_index]
    response = ((world + 2) % 6) + 1
    name = HEXAGRAM_NAMES[(upper, lower)]
    return Hexagram(
        name=name,
        lines=lines,
        lower_trigram=lower,
        upper_trigram=upper,
        palace=placement.palace,
        palace_element=PALACE_ELEMENTS[placement.palace],
        palace_sequence=sequence_index + 1,
        palace_stage=PALACE_STAGES[sequence_index],  # type: ignore[arg-type]
        world_line=world,
        response_line=response,
        is_six_clash=name in SIX_CLASH_NAMES,
        is_six_harmony=name in SIX_HARMONY_NAMES,
        is_wandering_soul=sequence_index == 6,
        is_returning_soul=sequence_index == 7,
    )


def all_hexagrams() -> tuple[Hexagram, ...]:
    return tuple(
        identify_hexagram(lines)
        for lines in sorted(PALACE_BY_LINES, key=lambda item: tuple(int(bit) for bit in item))
    )

