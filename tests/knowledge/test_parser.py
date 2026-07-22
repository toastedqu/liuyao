"""Parser unit tests: stable ids, content classification, and verbatim
round-trips against the original Markdown for the entire corpus.
"""

from __future__ import annotations

import re

import pytest

from app.knowledge.models import ContentType, Layer
from app.knowledge.parser import (
    FENCE_MARKER_RE,
    _fence_inner_span,
    _is_didactic_chart_intro,
    _looks_like_example_chart,
    parse_chapter,
    split_blocks,
)

EXPECTED_CHAPTER_COUNT = 141
STABLE_ID_RE = re.compile(r"^\d{3}_[^:]+:p\d{4}$")
EXAMPLE_ID_RE = re.compile(r"^\d{3}_[^:]+:example\d{4}:(question|chart|judgement)$")


def test_all_141_chapters_are_present(source_dir):
    files = sorted(source_dir.glob("*.md"))
    assert len(files) == EXPECTED_CHAPTER_COUNT
    numbers = sorted(int(f.stem.split("_", 1)[0]) for f in files)
    assert numbers == list(range(EXPECTED_CHAPTER_COUNT))


def test_parse_corpus_indexes_all_chapters(parsed_corpus):
    assert len(parsed_corpus) == EXPECTED_CHAPTER_COUNT
    chapter_ids = {r.chapter.chapter_id for r in parsed_corpus}
    assert len(chapter_ids) == EXPECTED_CHAPTER_COUNT  # no duplicate/overwritten ids


def test_every_chapter_has_at_least_one_paragraph(parsed_corpus):
    for result in parsed_corpus:
        assert result.paragraphs, f"{result.chapter.chapter_id} produced no paragraphs"


def test_stable_ids_follow_documented_convention(parsed_corpus):
    """implementation_plan.md §8.2 gives ``008_用神章:p0001`` and
    ``076_求财章:example0003:judgement`` as the stable id shape."""

    for result in parsed_corpus:
        for paragraph in result.paragraphs:
            if paragraph.example_id is None:
                assert STABLE_ID_RE.match(paragraph.source_id), paragraph.source_id
            else:
                assert EXAMPLE_ID_RE.match(paragraph.source_id), paragraph.source_id


def test_plan_example_id_exists_verbatim(parsed_corpus):
    """The exact id used as an example in implementation_plan.md §8.2 must
    resolve to real judgement text about the 泽火革 example."""

    chapter = next(r for r in parsed_corpus if r.chapter.chapter_id == "076_求财章")
    by_id = {p.source_id: p for p in chapter.paragraphs}
    judgement = by_id["076_求财章:example0003:judgement"]
    assert judgement.content_type == ContentType.EXAMPLE_JUDGEMENT
    assert judgement.text.startswith("断曰：兄爻持世")


def test_ids_are_unique_within_chapter(parsed_corpus):
    for result in parsed_corpus:
        ids = [p.source_id for p in result.paragraphs]
        assert len(ids) == len(set(ids)), result.chapter.chapter_id


def test_ids_are_stable_across_reparse(source_dir, repo_root):
    """Re-parsing the same file must produce byte-identical ids/text/offsets
    (determinism is a prerequisite for reproducible builds)."""

    path = source_dir / "008_用神章.md"
    first = parse_chapter(path, repo_root=repo_root)
    second = parse_chapter(path, repo_root=repo_root)
    assert [p.model_dump() for p in first.paragraphs] == [p.model_dump() for p in second.paragraphs]
    assert [e.model_dump() for e in first.examples] == [e.model_dump() for e in second.examples]


def test_every_paragraph_text_is_a_verbatim_source_excerpt(parsed_corpus, repo_root):
    """The single most important property of the knowledge base: nothing is
    reflowed, summarized or paraphrased. Every stored paragraph (including
    卦例 question/chart/judgement fragments) must equal the exact substring
    of the original file at its recorded offsets."""

    checked = 0
    for result in parsed_corpus:
        raw = (repo_root / result.chapter.source_path).read_text(encoding="utf-8")
        for paragraph in result.paragraphs:
            excerpt = raw[paragraph.char_start : paragraph.char_end]
            assert excerpt == paragraph.text, paragraph.source_id
            checked += 1
    assert checked > 2000  # sanity: we actually checked the whole corpus


def test_chapter_000_has_no_chapter_number_suffix_in_heading(source_dir, repo_root):
    """000_增删卜易序.md is the one file whose H1 heading has no ``NNN章、``
    prefix; the parser must still recover chapter_number=0 from the
    filename without raising or misparsing."""

    result = parse_chapter(source_dir / "000_增删卜易序.md", repo_root=repo_root)
    assert result.chapter.chapter_number == 0
    assert result.chapter.title == "序"


def test_editorial_markers_are_flagged_editorial(parsed_corpus):
    chapter = next(r for r in parsed_corpus if r.chapter.chapter_id == "008_用神章")
    editorial = [p for p in chapter.paragraphs if p.is_editorial]
    assert editorial
    assert all(p.content_type == ContentType.EDITORIAL for p in editorial)
    assert any("[乾按]" in p.text or "［乾按］" in p.text for p in editorial)


def test_editorial_markers_include_all_known_variants(parsed_corpus):
    variants_found = set()
    for result in parsed_corpus:
        for paragraph in result.paragraphs:
            if not paragraph.is_editorial:
                continue
            for marker in ("乾按", "提要", "居士按", "居士评", "蓝按"):
                if marker in paragraph.text:
                    variants_found.add(marker)
    assert {"乾按", "提要", "居士按", "居士评", "蓝按"} <= variants_found


def test_attribution_detection_for_yehe_and_juezi(parsed_corpus):
    """野鹤曰/觉子曰 must be detected and never classified as editorial
    purely because they are commentary -- they are 主要依据 per §8.1."""

    found_yehe = False
    found_juezi = False
    for result in parsed_corpus:
        for paragraph in result.paragraphs:
            if "野鹤" in paragraph.attributions:
                found_yehe = True
                assert "野鹤曰" in paragraph.text
            if "觉子" in paragraph.attributions:
                found_juezi = True
                assert "觉子曰" in paragraph.text
    assert found_yehe and found_juezi


def test_rule_paragraph_with_attribution_is_not_forced_editorial(source_dir, repo_root):
    """A paragraph that merely contains 野鹤曰/觉子曰 inline (not preceded by
    an editorial bracket marker) stays a RULE paragraph -- editorial status
    is reserved for [乾按]/[提要]/... asides."""

    result = parse_chapter(source_dir / "076_求财章.md", repo_root=repo_root)
    hit = next(p for p in result.paragraphs if "觉子曰：倘得日月为财" in p.text)
    assert hit.content_type == ContentType.RULE
    assert hit.is_editorial is False
    assert "觉子" in hit.attributions


def test_chapters_000_to_040_are_foundational_layer(parsed_corpus):
    for result in parsed_corpus:
        if result.chapter.chapter_number <= 40:
            for paragraph in result.paragraphs:
                if paragraph.content_type in (
                    ContentType.RULE,
                    ContentType.HEADING,
                ):
                    assert paragraph.layer == Layer.FOUNDATIONAL


def test_category_chapters_get_category_tags(parsed_corpus):
    chapter = next(r for r in parsed_corpus if r.chapter.chapter_id == "076_求财章")
    for paragraph in chapter.paragraphs:
        assert "求财" in paragraph.category_tags
    marriage = next(r for r in parsed_corpus if r.chapter.chapter_id == "091_婚姻章")
    for paragraph in marriage.paragraphs:
        assert "婚姻" in paragraph.category_tags


def test_examples_link_existing_paragraph_ids(parsed_corpus):
    for result in parsed_corpus:
        by_id = {p.source_id: p for p in result.paragraphs}
        for example in result.examples:
            assert example.chart_id in by_id
            if example.question_id is not None:
                assert example.question_id in by_id
            if example.judgement_id is not None:
                assert example.judgement_id in by_id


def test_example_count_matches_actual_hexagram_charts(source_dir, parsed_corpus):
    total_examples = sum(len(r.examples) for r in parsed_corpus)
    total_worked_charts = 0
    for path in source_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        blocks = split_blocks(text)
        for index, block in enumerate(blocks):
            if FENCE_MARKER_RE.match(block.text.strip()):
                inner = _fence_inner_span(block)[2]
                if _looks_like_example_chart(inner):
                    previous = blocks[index - 1].text if index else ""
                    total_worked_charts += int(
                        not _is_didactic_chart_intro(previous)
                    )
    assert total_examples == total_worked_charts == 306


def test_flying_spirit_illustrations_remain_theory(source_dir, repo_root):
    chapter = parse_chapter(
        source_dir / "035_飞伏神章.md",
        repo_root=repo_root,
    )

    assert chapter.examples[0].question_id == (
        "035_飞伏神章:example0001:question"
    )
    by_id = {paragraph.source_id: paragraph for paragraph in chapter.paragraphs}
    assert "卯月 壬辰日" in by_id[chapter.examples[0].question_id].text
    assert by_id["035_飞伏神章:p0002"].content_type == ContentType.RULE
    assert by_id["035_飞伏神章:p0006"].content_type == ContentType.RULE


def test_worked_case_judgement_spans_all_blocks_until_next_case(
    source_dir,
    repo_root,
):
    chapter = parse_chapter(
        source_dir / "034_月破章.md",
        repo_root=repo_root,
    )
    by_id = {paragraph.source_id: paragraph for paragraph in chapter.paragraphs}
    judgement = by_id["034_月破章:example0003:judgement"]

    assert "\n\n" in judgement.text
    raw = (repo_root / chapter.chapter.source_path).read_text(encoding="utf-8")
    assert raw[judgement.char_start : judgement.char_end] == judgement.text


def test_case_narrative_is_not_reindexed_as_general_theory(
    source_dir,
    repo_root,
):
    chapter = parse_chapter(
        source_dir / "034_月破章.md",
        repo_root=repo_root,
    )
    by_id = {paragraph.source_id: paragraph for paragraph in chapter.paragraphs}

    assert "余劝辞荣" in by_id[
        "034_月破章:example0005:judgement"
    ].text
    assert not any(
        paragraph.example_id is None and "余劝辞荣" in paragraph.text
        for paragraph in chapter.paragraphs
    )


@pytest.mark.parametrize(
    ("chapter_name", "example_id"),
    [
        ("065_援例章.md", "065_援例章:example0002"),
        ("077_谒贵求财章.md", "077_谒贵求财章:example0002"),
        ("091_婚姻章.md", "091_婚姻章:example0006"),
    ],
)
def test_bold_first_judgement_stays_with_worked_case(
    source_dir,
    repo_root,
    chapter_name,
    example_id,
):
    chapter = parse_chapter(
        source_dir / chapter_name,
        repo_root=repo_root,
    )
    example = next(
        item for item in chapter.examples if item.example_id == example_id
    )
    by_id = {paragraph.source_id: paragraph for paragraph in chapter.paragraphs}

    assert example.judgement_id is not None
    assert by_id[example.judgement_id].text.startswith("**")


def test_fenced_origin_and_taboo_lists_remain_theory(source_dir, repo_root):
    chapter = parse_chapter(
        source_dir / "010_元神、忌神、衰旺章.md",
        repo_root=repo_root,
    )

    assert chapter.examples == []
    fenced_rules = [
        paragraph
        for paragraph in chapter.paragraphs
        if "以上元神见生不生" in paragraph.text
        or "以上乃有力之忌神" in paragraph.text
        or "以上乃无力之忌神" in paragraph.text
    ]
    assert len(fenced_rules) == 3
    assert all(paragraph.content_type == ContentType.RULE for paragraph in fenced_rules)
    assert all(paragraph.layer == Layer.FOUNDATIONAL for paragraph in fenced_rules)


class TestSplitBlocks:
    def test_blank_lines_separate_blocks(self):
        text = "para one\n\npara two\n"
        blocks = split_blocks(text)
        assert [b.text for b in blocks] == ["para one", "para two"]

    def test_fenced_block_with_internal_blank_line_stays_atomic(self):
        text = "before\n\n```\nline1\n\nline2\n```\n\nafter\n"
        blocks = split_blocks(text)
        assert [b.text for b in blocks] == [
            "before",
            "```\nline1\n\nline2\n```",
            "after",
        ]

    def test_offsets_slice_back_to_the_same_text(self):
        text = "alpha beta\n\ngamma\ndelta\n\n```\nfence\n```\n"
        blocks = split_blocks(text)
        for block in blocks:
            assert text[block.start : block.end] == block.text


def test_unknown_filename_pattern_raises(build_workdir):
    bad_file = build_workdir / "not_a_chapter.md"
    bad_file.write_text("# nothing", encoding="utf-8")
    try:
        with pytest.raises(ValueError):
            parse_chapter(bad_file)
    finally:
        bad_file.unlink(missing_ok=True)
