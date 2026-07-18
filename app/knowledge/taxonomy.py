"""Static taxonomy for the 《增删卜易》knowledge base.

These tables encode editorial decisions that are cheap to get wrong silently,
so they are kept in one place, in plain data, instead of scattered regexes:

* which chapters are "foundational" (章 000-040: 八宫/纳甲/六亲/世应/动变/用神/
  元神忌神/生克/旺衰/旬空/月破 ...) versus "各门类" category chapters;
* which 占类 (divination category) each category chapter belongs to, per
  implementation_plan.md §8.1;
* the canonical rule-tag vocabulary (§9.2) that the future deterministic
  fact engine is expected to emit (upper snake case, e.g. ``MONTH_BREAK``),
  together with the Chinese keywords used to detect a rule's presence in a
  paragraph of original text;
* the small, explicitly named set of "固定取用" chapters (§8.3 item 1:
  凡例、用神及通用方法论) that retrieval always includes.

Nothing here is invented terminology: every category label and rule tag
traces to a chapter title or a phrase used in implementation_plan.md.
"""

from __future__ import annotations

# --- 占类 (divination category) routing -----------------------------------
# Inclusive chapter-number ranges, in the order chapters appear in the book.
# Chapters 000-040 are cross-cutting/foundational and are not assigned a
# category; instead they are always reachable via fact-tag routing.
CATEGORY_RANGES: list[tuple[int, int, tuple[str, ...]]] = [
    (41, 41, ("天时",)),
    (42, 42, ("身命",)),
    (43, 43, ("身命", "求财")),
    (44, 44, ("身命", "功名")),
    (45, 46, ("身命",)),
    (47, 47, ("六亲",)),
    (48, 48, ("六亲",)),
    (49, 49, ("六亲", "婚姻")),
    (50, 50, ("六亲",)),
    (51, 75, ("功名",)),
    (76, 90, ("求财",)),
    (91, 96, ("婚姻",)),
    (97, 100, ("胎产",)),
    (101, 104, ("出行",)),
    (105, 108, ("词讼",)),
    (109, 114, ("疾病",)),
    (115, 127, ("家宅",)),
    (128, 140, ("茔葬",)),
]

FOUNDATIONAL_MAX_CHAPTER = 40  # chapters 000-040 are the foundational layer

# Chapters explicitly named in implementation_plan.md as the always-included
# "固定取用：凡例、用神及通用方法论" pool (§8.3 item 1, §9.1).
FIXED_PICK_CHAPTER_IDS: tuple[str, ...] = (
    "002_占卦法章",
    "007_动变章",
    "008_用神章",
    "009_用神、元神、忌神、仇神章",
    "010_元神、忌神、衰旺章",
    "031_各门类题头总注章",
    "032_各门类应期总注章",
    "035_飞伏神章",
    "039_两现章",
)

# --- 编辑性文字 (editorial asides) -----------------------------------------
# Bracketed marker names seen in the corpus. Both ASCII and full-width
# brackets are used inconsistently by the source, and the marker itself is
# sometimes bold (``**[乾按]**``) and sometimes not.
EDITORIAL_MARKERS: tuple[str, ...] = (
    "乾按",
    "提要",
    "居士按",
    "居士评",
    "蓝按",
    "注",
)

# --- 主要依据 (primary authoritative voices) -------------------------------
ATTRIBUTION_MARKERS: tuple[str, ...] = ("野鹤曰", "觉子曰")

# --- 规则标签 (rule tags) ---------------------------------------------------
# Canonical, machine-usable tag -> Chinese keywords used to detect the rule's
# presence in a paragraph. The tag names mirror the fact vocabulary sketched
# in implementation_plan.md §9.2 and the example fact JSON in §5.2
# (e.g. ``"type": "MONTH_BREAK"``), so a future rules engine can route on
# ``fact.type`` directly.
RULE_TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "USEFUL_GOD": ("用神",),
    "ORIGIN_GOD": ("元神",),
    "TABOO_GOD": ("忌神",),
    "RIVAL_GOD": ("仇神",),
    "WORLD_RESPONSE": ("世爻", "应爻", "世应"),
    "FIVE_ELEMENT_INTERACTION": ("相生", "相克", "生克"),
    "SEASONAL_STRENGTH": ("旺相", "休囚", "四时旺相"),
    "SIX_COMBINE": ("六合",),
    "THREE_COMBINE": ("三合",),
    "SIX_CLASH": ("六冲",),
    "THREE_PUNISH": ("三刑",),
    "SIX_HARM": ("六害",),
    "HIDDEN_MOTION": ("暗动",),
    "MOVING_DISSIPATE": ("动散",),
    "RETURN_GENERATION": ("回头生", "化回头之生"),
    "RETURN_CONTROL": ("回头克", "化回头之克"),
    "EMPTY_TOMB": ("旬空", "空亡"),
    "MONTH_BREAK": ("月破",),
    "GRAVE_ABSOLUTE": ("生旺墓绝", "入墓", "墓绝"),
    "ADVANCING_SPIRIT": ("进神",),
    "RETREATING_SPIRIT": ("退神",),
    "HIDDEN_SPIRIT": ("伏神", "飞伏"),
    "REVERSE_ECHO": ("反吟",),
    "REPEATED_ECHO": ("伏吟",),
    "SOLE_MOVING": ("独发",),
    "DOUBLE_PRESENT": ("两现",),
    "GHOST_TOMB": ("随鬼入墓",),
    "TIMING": ("应期", "应验"),
    "WANDERING_RETURNING_SOUL": ("游魂", "归魂"),
}

# --- 主题标签 (topic tags) --------------------------------------------------
# Broader, human-facing thematic labels (Chinese), independent of the
# machine rule-tag vocabulary above, used for browsing and FTS.
TOPIC_TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "八宫纳甲": ("八宫", "纳甲", "世应"),
    "六亲": ("父母爻", "官鬼爻", "兄弟爻", "妻财爻", "子孙爻", "六亲"),
    "五行生克": ("五行", "相生", "相克"),
    "旺衰": ("旺相", "休囚", "衰旺"),
    "刑冲合害": ("相刑", "相冲", "相合", "相害", "三刑", "六害"),
    "空破": ("旬空", "月破"),
    "动变": ("动爻", "变爻", "动变"),
    "神煞": ("六神", "星煞"),
    "应期": ("应期", "应验"),
    "卦例": ("占", "得"),
}


def categories_for_chapter(chapter_number: int) -> tuple[str, ...]:
    """Return the 占类 tags assigned to a chapter number, if any."""

    for low, high, categories in CATEGORY_RANGES:
        if low <= chapter_number <= high:
            return categories
    return ()


def is_foundational(chapter_number: int) -> bool:
    return chapter_number <= FOUNDATIONAL_MAX_CHAPTER
