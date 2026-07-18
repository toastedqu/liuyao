from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from app.chart.hexagrams import LineBits, TRIGRAM_BITS, identify_hexagram
from app.chart.models import (
    Chart,
    ChartFact,
    ChartLine,
    ChangedLine,
    HiddenSpirit,
)
from app.chart.najia import install_najia, relative_for


LINE_NAMES = ("初爻", "二爻", "三爻", "四爻", "五爻", "上爻")
DEFAULT_SPIRITS = ("青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武")


def _as_line_bits(values: Sequence[int]) -> LineBits:
    return cast(LineBits, tuple(value in (7, 9) for value in values))


def _changed_bits(values: Sequence[int], primary: LineBits) -> LineBits:
    return cast(
        LineBits,
        tuple(not bit if value in (6, 9) else bit for value, bit in zip(values, primary)),
    )


def build_chart(
    line_values: Sequence[int],
    *,
    six_spirits: Sequence[str] = DEFAULT_SPIRITS,
) -> Chart:
    """Build a complete chart from six values ordered 初爻至上爻."""

    if len(line_values) != 6:
        raise ValueError("六爻必须恰好六项，且按初爻至上爻排列")
    if any(value not in (6, 7, 8, 9) for value in line_values):
        raise ValueError("六爻每项只能是 6、7、8 或 9")
    if len(six_spirits) != 6 or any(not spirit for spirit in six_spirits):
        raise ValueError("六神必须恰好六项，且按初爻至上爻排列")

    values = tuple(int(value) for value in line_values)
    primary_bits = _as_line_bits(values)
    changed_bits = _changed_bits(values, primary_bits)
    primary = identify_hexagram(primary_bits)
    changed = identify_hexagram(changed_bits)

    primary_najia = install_najia(primary.lower_trigram, primary.upper_trigram)
    changed_najia = install_najia(changed.lower_trigram, changed.upper_trigram)
    primary_relatives = tuple(
        relative_for(primary.palace_element, line.element) for line in primary_najia
    )
    changed_relatives = tuple(
        relative_for(primary.palace_element, line.element) for line in changed_najia
    )

    visible_relatives = set(primary_relatives)
    palace_pure = identify_hexagram(
        cast(LineBits, TRIGRAM_BITS[primary.palace] + TRIGRAM_BITS[primary.palace])
    )
    palace_najia = install_najia(palace_pure.lower_trigram, palace_pure.upper_trigram)
    palace_relatives = tuple(
        relative_for(primary.palace_element, line.element) for line in palace_najia
    )

    lines: list[ChartLine] = []
    facts: list[ChartFact] = [
        ChartFact(
            id="fact-primary-hexagram",
            type="PRIMARY_HEXAGRAM",
            value=primary.name,
            evidence={
                "lower_trigram": primary.lower_trigram,
                "upper_trigram": primary.upper_trigram,
                "palace": primary.palace,
                "palace_stage": primary.palace_stage,
            },
            rule_source="003_八宫图章:p0001",
        ),
        ChartFact(
            id="fact-changed-hexagram",
            type="CHANGED_HEXAGRAM",
            value=changed.name,
            evidence={
                "lower_trigram": changed.lower_trigram,
                "upper_trigram": changed.upper_trigram,
            },
            rule_source="007_动变章:p0001",
        ),
    ]

    for index, value in enumerate(values):
        position = index + 1
        is_moving = value in (6, 9)
        primary_line = primary_najia[index]
        changed_line = changed_najia[index]
        hidden = None
        palace_relative = palace_relatives[index]
        if palace_relative not in visible_relatives:
            palace_line = palace_najia[index]
            hidden = HiddenSpirit(
                stem=palace_line.stem,
                branch=palace_line.branch,
                element=palace_line.element,
                relative=palace_relative,
                source_hexagram=palace_pure.name,
            )

        changed_result = None
        if is_moving:
            changed_result = ChangedLine(
                is_yang=changed_bits[index],
                stem=changed_line.stem,
                branch=changed_line.branch,
                element=changed_line.element,
                relative=changed_relatives[index],
            )

        lines.append(
            ChartLine(
                position=position,
                name=LINE_NAMES[index],
                raw_value=value,  # type: ignore[arg-type]
                is_yang=primary_bits[index],
                is_moving=is_moving,
                spirit=six_spirits[index],
                stem=primary_line.stem,
                branch=primary_line.branch,
                element=primary_line.element,
                relative=primary_relatives[index],
                is_world=position == primary.world_line,
                is_response=position == primary.response_line,
                changed=changed_result,
                hidden_spirit=hidden,
            )
        )
        facts.extend(
            (
                ChartFact(
                    id=f"fact-line-polarity-l{position}",
                    type="LINE_POLARITY",
                    line=position,
                    value="阳" if primary_bits[index] else "阴",
                    evidence={"raw_value": value},
                    rule_source="007_动变章:p0001",
                ),
                ChartFact(
                    id=f"fact-line-state-l{position}",
                    type="MOVING" if is_moving else "STATIC",
                    line=position,
                    value=True,
                    evidence={"raw_value": value},
                    rule_source="007_动变章:p0001",
                ),
                ChartFact(
                    id=f"fact-najia-l{position}",
                    type="NAJIA",
                    line=position,
                    value=f"{primary_line.stem}{primary_line.branch}",
                    evidence={
                        "element": primary_line.element.value,
                        "relative": primary_relatives[index].value,
                    },
                    rule_source="004_混天甲子章:example0001:chart",
                ),
            )
        )
        if hidden is not None:
            facts.append(
                ChartFact(
                    id=f"fact-hidden-spirit-l{position}",
                    type="HIDDEN_SPIRIT",
                    line=position,
                    value=hidden.relative.value,
                    evidence={
                        "stem_branch": f"{hidden.stem}{hidden.branch}",
                        "element": hidden.element.value,
                        "source_hexagram": hidden.source_hexagram,
                    },
                    rule_source="035_飞伏神章:example0001:question",
                )
            )

    facts.extend(
        (
            ChartFact(
                id=f"fact-world-line-l{primary.world_line}",
                type="WORLD_LINE",
                line=primary.world_line,
                value=True,
                rule_source="006_世应章:example0001:chart",
            ),
            ChartFact(
                id=f"fact-response-line-l{primary.response_line}",
                type="RESPONSE_LINE",
                line=primary.response_line,
                value=True,
                rule_source="006_世应章:example0001:judgement",
            ),
        )
    )

    return Chart(
        raw_lines=cast(tuple, values),
        primary=primary,
        changed=changed,
        lines=cast(tuple, tuple(lines)),
        facts=tuple(facts),
    )
