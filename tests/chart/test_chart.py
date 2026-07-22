from __future__ import annotations

import pytest

from app.chart import Relative, build_chart
from app.chart.hexagrams import (
    PALACE_BY_LINES,
    PALACE_STAGES,
    SIX_CLASH_NAMES,
    SIX_HARMONY_NAMES,
    WORLD_LINES,
    identify_hexagram,
)


EXPECTED_PALACES = {
    "乾": (
        "乾为天",
        "天风姤",
        "天山遁",
        "天地否",
        "风地观",
        "山地剥",
        "火地晋",
        "火天大有",
    ),
    "坎": (
        "坎为水",
        "水泽节",
        "水雷屯",
        "水火既济",
        "泽火革",
        "雷火丰",
        "地火明夷",
        "地水师",
    ),
    "艮": (
        "艮为山",
        "山火贲",
        "山天大畜",
        "山泽损",
        "火泽睽",
        "天泽履",
        "风泽中孚",
        "风山渐",
    ),
    "震": (
        "震为雷",
        "雷地豫",
        "雷水解",
        "雷风恒",
        "地风升",
        "水风井",
        "泽风大过",
        "泽雷随",
    ),
    "巽": (
        "巽为风",
        "风天小畜",
        "风火家人",
        "风雷益",
        "天雷无妄",
        "火雷噬嗑",
        "山雷颐",
        "山风蛊",
    ),
    "离": (
        "离为火",
        "火山旅",
        "火风鼎",
        "火水未济",
        "山水蒙",
        "风水涣",
        "天水讼",
        "天火同人",
    ),
    "坤": (
        "坤为地",
        "地雷复",
        "地泽临",
        "地天泰",
        "雷天大壮",
        "泽天夬",
        "水天需",
        "水地比",
    ),
    "兑": (
        "兑为泽",
        "泽水困",
        "泽地萃",
        "泽山咸",
        "水山蹇",
        "地山谦",
        "雷山小过",
        "雷泽归妹",
    ),
}


def test_all_sixty_four_hexagrams_have_correct_palace_order_and_world_response() -> None:
    assert len(PALACE_BY_LINES) == 64
    seen = set()
    for lines in PALACE_BY_LINES:
        hexagram = identify_hexagram(lines)
        seen.add(hexagram.name)
        sequence = EXPECTED_PALACES[hexagram.palace]
        assert sequence[hexagram.palace_sequence - 1] == hexagram.name
        assert hexagram.palace_stage == PALACE_STAGES[hexagram.palace_sequence - 1]
        assert hexagram.world_line == WORLD_LINES[hexagram.palace_sequence - 1]
        assert hexagram.response_line == ((hexagram.world_line + 2) % 6) + 1
        assert hexagram.is_wandering_soul == (hexagram.palace_sequence == 7)
        assert hexagram.is_returning_soul == (hexagram.palace_sequence == 8)
    assert len(seen) == 64


def test_pure_qian_najia_relatives_and_line_order() -> None:
    chart = build_chart(
        [7, 7, 7, 7, 7, 7],
        six_spirits=("玄武", "青龙", "朱雀", "勾陈", "螣蛇", "白虎"),
    )

    assert chart.primary.name == "乾为天"
    assert chart.primary.palace == "乾"
    assert chart.primary.world_line == 6
    assert chart.primary.response_line == 3
    assert [line.stem + line.branch for line in chart.lines] == [
        "甲子",
        "甲寅",
        "甲辰",
        "壬午",
        "壬申",
        "壬戌",
    ]
    assert [line.relative.value for line in chart.lines] == [
        "子孙",
        "妻财",
        "父母",
        "官鬼",
        "兄弟",
        "父母",
    ]
    assert [line.spirit for line in chart.lines] == [
        "玄武",
        "青龙",
        "朱雀",
        "勾陈",
        "螣蛇",
        "白虎",
    ]


def test_changed_line_relatives_follow_primary_palace() -> None:
    chart = build_chart([9, 7, 7, 7, 7, 6])

    assert chart.primary.name == "泽天夬"
    assert chart.primary.palace == "坤"
    assert chart.changed.name == "天风姤"
    assert chart.lines[0].changed is not None
    assert chart.lines[5].changed is not None
    assert chart.lines[0].changed.branch == "丑"
    assert chart.lines[5].changed.branch == "戌"
    assert chart.lines[0].changed.relative is Relative.SIBLING
    assert chart.lines[5].changed.relative is Relative.SIBLING
    assert all(line.changed is None for line in chart.lines[1:5])


def test_hidden_spirit_comes_from_palace_pure_hexagram() -> None:
    chart = build_chart([8, 7, 7, 7, 7, 7])

    assert chart.primary.name == "天风姤"
    hidden = chart.lines[1].hidden_spirit
    assert hidden is not None
    assert hidden.relative is Relative.WEALTH
    assert hidden.stem + hidden.branch == "甲寅"
    assert hidden.source_hexagram == "乾为天"
    assert sum(line.hidden_spirit is not None for line in chart.lines) == 1


def test_six_clash_harmony_wandering_and_returning_flags() -> None:
    for lines in PALACE_BY_LINES:
        item = identify_hexagram(lines)
        assert item.is_six_clash == (item.name in SIX_CLASH_NAMES)
        assert item.is_six_harmony == (item.name in SIX_HARMONY_NAMES)


@pytest.mark.parametrize("lines", ([7] * 5, [7] * 7, [7, 7, 7, 7, 7, 5]))
def test_invalid_lines_are_rejected(lines: list[int]) -> None:
    with pytest.raises(ValueError):
        build_chart(lines)


def test_every_single_line_change_flips_only_that_line() -> None:
    for bits in PALACE_BY_LINES:
        for index in range(6):
            values = [7 if bit else 8 for bit in bits]
            values[index] = 9 if bits[index] else 6
            chart = build_chart(values)
            expected = list(bits)
            expected[index] = not expected[index]

            assert chart.primary.lines == bits
            assert chart.changed.lines == tuple(expected)
            assert chart.lines[index].is_moving is True
            assert chart.lines[index].changed is not None
            assert sum(line.is_moving for line in chart.lines) == 1


def test_chart_facts_have_stable_ids_and_sources() -> None:
    chart = build_chart([7, 8, 6, 9, 7, 8])

    ids = [fact.id for fact in chart.facts]
    assert len(ids) == len(set(ids))
    assert "fact-line-state-l3" in ids
    assert "fact-line-state-l4" in ids
    assert all(fact.rule_source for fact in chart.facts)
    moving = next(fact for fact in chart.facts if fact.type == "MOVING")
    serialized = moving.model_dump(mode="json")
    assert serialized["type"] == "动爻"
    assert serialized["value"] == "是"
