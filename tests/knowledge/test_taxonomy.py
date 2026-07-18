"""Tests for the static taxonomy tables (占类/规则标签/固定取用)."""

from __future__ import annotations

from app.knowledge.taxonomy import (
    CATEGORY_RANGES,
    FIXED_PICK_CHAPTER_IDS,
    categories_for_chapter,
    is_foundational,
)


def test_foundational_cutoff():
    assert is_foundational(0)
    assert is_foundational(40)
    assert not is_foundational(41)
    assert not is_foundational(140)


def test_foundational_chapters_have_no_category():
    for n in (0, 8, 29, 34, 40):
        assert categories_for_chapter(n) == ()


def test_category_examples_match_known_chapters():
    assert categories_for_chapter(76) == ("求财",)
    assert categories_for_chapter(91) == ("婚姻",)
    assert categories_for_chapter(109) == ("疾病",)
    assert categories_for_chapter(41) == ("天时",)


def test_category_ranges_do_not_overlap():
    ranges = sorted(CATEGORY_RANGES, key=lambda r: r[0])
    for (low1, high1, _), (low2, high2, _) in zip(ranges, ranges[1:]):
        assert high1 < low2


def test_category_ranges_cover_all_chapters_041_to_140():
    covered = set()
    for low, high, _ in CATEGORY_RANGES:
        covered.update(range(low, high + 1))
    assert covered == set(range(41, 141))


def test_fixed_pick_chapter_ids_are_all_foundational():
    for chapter_id in FIXED_PICK_CHAPTER_IDS:
        number = int(chapter_id.split("_", 1)[0])
        assert is_foundational(number), chapter_id


def test_unknown_chapter_number_has_no_category():
    assert categories_for_chapter(9999) == ()
