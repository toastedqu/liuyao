"""Retriever pipeline tests: fixed pick, category routing, fact-tag routing,
卦例 scoring, and the staged/deduplicated ``retrieve()`` orchestration."""

from __future__ import annotations

from app.knowledge.taxonomy import FIXED_PICK_CHAPTER_IDS


def test_fixed_pick_covers_named_methodology_chapters(retriever):
    paragraphs = retriever.fixed_pick()
    assert paragraphs
    chapter_ids = {p.chapter_id for p in paragraphs}
    assert chapter_ids <= set(FIXED_PICK_CHAPTER_IDS)
    assert "008_用神章" in chapter_ids
    assert "032_各门类应期总注章" in chapter_ids


def test_fixed_pick_is_cached_and_stable(retriever):
    first = retriever.fixed_pick()
    second = retriever.fixed_pick()
    assert [p.source_id for p in first] == [p.source_id for p in second]


def test_by_category_routes_to_correct_chapters(retriever):
    wealth = retriever.by_category("求财")
    assert wealth
    assert all("求财" in p.category_tags for p in wealth)

    marriage = retriever.by_category("婚姻")
    assert marriage
    assert all("婚姻" in p.category_tags for p in marriage)

    assert {p.chapter_id for p in wealth}.isdisjoint({p.chapter_id for p in marriage})


def test_by_fact_tags_routes_month_break_to_chapter_034(retriever):
    paragraphs = retriever.by_fact_tags(["MONTH_BREAK"])
    chapter_ids = {p.chapter_id for p in paragraphs}
    assert "034_月破章" in chapter_ids


def test_by_fact_tags_reaches_beyond_the_dedicated_chapter(retriever):
    """A fact tag like MONTH_BREAK should also surface mentions of 月破 in
    category chapters (e.g. 求财), not only the dedicated foundational
    chapter -- that is the point of fact-tag routing as a cross-cutting
    layer distinct from category routing."""

    paragraphs = retriever.by_fact_tags(["MONTH_BREAK"])
    chapter_ids = {p.chapter_id for p in paragraphs}
    assert len(chapter_ids) > 1


def test_score_examples_ranks_hexagram_match_highest(retriever):
    scored = retriever.score_examples(category="求财", hexagram_name="泽火革", limit=5)
    assert scored
    top = scored[0]
    assert top.example.example_id == "076_求财章:example0001"
    assert any("hexagram" in reason for reason in top.reasons)


def test_score_examples_without_any_match_is_empty(retriever):
    scored = retriever.score_examples(category="不存在的占类", hexagram_name="不存在的卦")
    assert scored == []


def test_score_examples_respects_limit(retriever):
    scored = retriever.score_examples(category="求财", limit=2)
    assert len(scored) <= 2


def test_score_examples_deterministic_ordering(retriever):
    first = retriever.score_examples(category="疾病", fact_tags=["MONTH_BREAK"], limit=10)
    second = retriever.score_examples(category="疾病", fact_tags=["MONTH_BREAK"], limit=10)
    assert [s.example.example_id for s in first] == [s.example.example_id for s in second]


def test_keyword_search_stage(retriever):
    results = retriever.keyword_search("用神", limit=5)
    assert results


def test_retrieve_prioritizes_fixed_pick_first(retriever):
    result = retriever.retrieve(category="求财", fact_tags=["MONTH_BREAK"], keywords="求财")
    assert result.paragraphs
    stages_in_order = [p.stage for p in result.paragraphs]
    first_non_fixed = next(
        (i for i, s in enumerate(stages_in_order) if s != "fixed_pick"), len(stages_in_order)
    )
    assert all(s == "fixed_pick" for s in stages_in_order[:first_non_fixed])
    assert "category" in stages_in_order or "fact_tag" in stages_in_order


def test_retrieve_deduplicates_across_stages(retriever):
    result = retriever.retrieve(category="求财", fact_tags=["MONTH_BREAK"], keywords="求财")
    ids = result.paragraph_ids()
    assert len(ids) == len(set(ids))


def test_retrieve_includes_scored_examples(retriever):
    result = retriever.retrieve(category="求财", hexagram_name="泽火革", example_limit=3)
    assert result.examples
    assert result.examples[0].example.example_id == "076_求财章:example0001"


def test_retrieve_with_no_query_context_still_returns_fixed_pick(retriever):
    result = retriever.retrieve()
    assert result.paragraphs
    assert all(p.stage == "fixed_pick" for p in result.paragraphs)
    assert result.examples == []
