"""Ganzhi (干支) constants shared by the calendar and chart packages.

Ten heavenly stems (天干) and twelve earthly branches (地支), their five-phase
(五行) elements, yin/yang polarity, the standard six-clash (六冲) and
six-combine (六合) branch pairings, and the twelve "jie" (节) solar-term to
month-branch mapping used for 月建 (see 004_混天甲子章.md and 029_旬空章.md for
the branch/element and 旬空 tables that these constants encode).
"""

from __future__ import annotations

STEMS: tuple[str, ...] = ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸")
BRANCHES: tuple[str, ...] = (
    "子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥",
)

STEM_INDEX: dict[str, int] = {stem: index for index, stem in enumerate(STEMS)}
BRANCH_INDEX: dict[str, int] = {branch: index for index, branch in enumerate(BRANCHES)}

# 五行: wood(木) fire(火) earth(土) metal(金) water(水)
STEM_ELEMENT: dict[str, str] = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}
BRANCH_ELEMENT: dict[str, str] = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

# odd position (0-indexed even) stems/branches are yang, the rest yin.
STEM_IS_YANG: dict[str, bool] = {stem: index % 2 == 0 for index, stem in enumerate(STEMS)}
BRANCH_IS_YANG: dict[str, bool] = {
    branch: index % 2 == 0 for index, branch in enumerate(BRANCHES)
}

# 六冲: branch clashes with the branch six positions away.
SIX_CLASH_PAIRS: tuple[tuple[str, str], ...] = tuple(
    (BRANCHES[i], BRANCHES[(i + 6) % 12]) for i in range(6)
)
# 六合: branch i combines with branch (13 - i) % 12 (029/003 tables are
# consistent with this, e.g. 子丑合, 寅亥合, 卯戌合, 辰酉合, 巳申合, 午未合).
SIX_COMBINE_PAIRS: tuple[tuple[str, str], ...] = tuple(
    sorted({tuple(sorted((BRANCHES[i], BRANCHES[(13 - i) % 12]))) for i in range(12)})
)


def clash_partner(branch: str) -> str:
    """Return the branch that clashes (六冲) with ``branch``."""

    index = BRANCH_INDEX[branch]
    return BRANCHES[(index + 6) % 12]


def combine_partner(branch: str) -> str:
    """Return the branch that combines (六合) with ``branch``."""

    index = BRANCH_INDEX[branch]
    return BRANCHES[(13 - index) % 12]


def is_six_clash(branch_a: str, branch_b: str) -> bool:
    return clash_partner(branch_a) == branch_b


def is_six_combine(branch_a: str, branch_b: str) -> bool:
    return combine_partner(branch_a) == branch_b


# The twelve "节" (sectional solar terms) that mark 月建 (month-branch)
# boundaries, in the order the sun's apparent ecliptic longitude passes
# through them. Longitude 315° is 立春 (start of 寅月); each subsequent 节 is
# +30° of longitude and +1 branch, cycling through all 12 branches once.
JIE_NAMES_FROM_LICHUN: tuple[str, ...] = (
    "立春", "惊蛰", "清明", "立夏", "芒种", "小暑",
    "立秋", "白露", "寒露", "立冬", "大雪", "小寒",
)
LICHUN_LONGITUDE: float = 315.0
# Month branch (地支) for the k-th jie after 立春 (k=0 -> 寅, k=1 -> 卯, ...).
MONTH_BRANCH_FOR_JIE_INDEX: tuple[str, ...] = tuple(
    BRANCHES[(2 + k) % 12] for k in range(12)
)

# 五虎遁 (year stem -> 寅月 stem) mnemonic: 甲己之年丙作首, 乙庚之年戊为头,
# 丙辛之年寻庚上, 丁壬壬寅顺行流, 戊癸之年甲寅求.
YEAR_STEM_TO_YIN_MONTH_STEM_OFFSET = 2  # 甲(0) -> 丙(2); formula: (2*(year_stem%5)+2) % 10


def yin_month_stem_index(year_stem_index: int) -> int:
    """Return the heavenly-stem index of 寅月 for a BaZi year stem (五虎遁)."""

    return (2 * (year_stem_index % 5) + 2) % 10


# 五鼠遁 (day stem -> 子时 stem) mnemonic: 甲己还加甲, 乙庚丙作初,
# 丙辛从戊起, 丁壬庚子居, 戊癸何方发, 壬子是真途.
def zi_hour_stem_index(day_stem_index: int) -> int:
    """Return the heavenly-stem index of 子时 for a given day stem (五鼠遁)."""

    return (2 * (day_stem_index % 5)) % 10
