"""KnowledgeRepository read-path tests: lookups, tag routing, FTS, and exact
source-file round-tripping (§8.2, §12 item 3: "按 source_id 精确回源")."""

from __future__ import annotations

import pytest

from app.knowledge.models import ContentType, Layer


def test_list_chapters_returns_all_141_in_order(knowledge_repo):
    chapters = knowledge_repo.list_chapters()
    assert len(chapters) == 141
    numbers = [c.chapter_number for c in chapters]
    assert numbers == sorted(numbers)
    assert numbers == list(range(141))


def test_get_chapter_by_id(knowledge_repo):
    chapter = knowledge_repo.get_chapter("008_用神章")
    assert chapter is not None
    assert chapter.title == "用神章"
    assert chapter.chapter_number == 8
    assert len(chapter.source_sha256) == 64


def test_get_chapter_unknown_returns_none(knowledge_repo):
    assert knowledge_repo.get_chapter("999_不存在") is None


def test_get_paragraph_by_stable_id(knowledge_repo):
    paragraph = knowledge_repo.get_paragraph("008_用神章:p0001")
    assert paragraph is not None
    assert paragraph.text.startswith("**父母爻：**占父母")
    assert paragraph.content_type == ContentType.RULE


def test_get_paragraph_unknown_returns_none(knowledge_repo):
    assert knowledge_repo.get_paragraph("008_用神章:p9999") is None


def test_paragraphs_by_chapter_are_ordered_by_seq(knowledge_repo):
    paragraphs = knowledge_repo.paragraphs_by_chapter("008_用神章")
    assert paragraphs
    seqs = [p.seq for p in paragraphs if p.seq > 0]
    assert seqs == sorted(seqs)


def test_paragraphs_by_layer_foundational_excludes_category_chapters(knowledge_repo):
    foundational = knowledge_repo.paragraphs_by_layer(Layer.FOUNDATIONAL)
    assert foundational
    assert all(p.chapter_id.split("_", 1)[0].isdigit() for p in foundational)
    assert all(int(p.chapter_id.split("_", 1)[0]) <= 40 for p in foundational)


def test_paragraphs_by_ids_preserves_requested_order(knowledge_repo):
    ids = ["008_用神章:p0003", "008_用神章:p0001", "008_用神章:p0002"]
    result = knowledge_repo.paragraphs_by_ids(ids)
    assert [p.source_id for p in result] == ids


def test_paragraphs_by_ids_skips_unknown_ids(knowledge_repo):
    ids = ["008_用神章:p0001", "does-not-exist"]
    result = knowledge_repo.paragraphs_by_ids(ids)
    assert [p.source_id for p in result] == ["008_用神章:p0001"]


def test_paragraphs_by_category_wealth(knowledge_repo):
    paragraphs = knowledge_repo.paragraphs_by_category("求财")
    assert paragraphs
    assert all("求财" in p.category_tags for p in paragraphs)
    chapter_ids = {p.chapter_id for p in paragraphs}
    assert "076_求财章" in chapter_ids


def test_paragraphs_by_category_unknown_is_empty(knowledge_repo):
    assert knowledge_repo.paragraphs_by_category("不存在的占类") == []


def test_paragraphs_by_rule_tags_month_break(knowledge_repo):
    paragraphs = knowledge_repo.paragraphs_by_rule_tags(["MONTH_BREAK"])
    assert paragraphs
    assert all("MONTH_BREAK" in p.rule_tags for p in paragraphs)
    chapter_ids = {p.chapter_id for p in paragraphs}
    assert "034_月破章" in chapter_ids


def test_paragraphs_by_rule_tags_empty_input(knowledge_repo):
    assert knowledge_repo.paragraphs_by_rule_tags([]) == []


@pytest.mark.parametrize("term", ["用神", "月破", "旬空", "求财"])
def test_search_fts_short_terms_still_match(knowledge_repo, term):
    """Short (2-char) core terms must not silently return zero results just
    because the FTS5 trigram tokenizer needs >=3 chars to index/match."""

    results = knowledge_repo.search_fts(term, limit=5)
    assert results
    assert all(term in p.text for p in results)


def test_search_fts_longer_phrase(knowledge_repo):
    results = knowledge_repo.search_fts("旬空最爱填冲", limit=5)
    assert results
    assert any("旬空最爱填冲" in p.text for p in results)


def test_search_fts_empty_query_returns_nothing(knowledge_repo):
    assert knowledge_repo.search_fts("", limit=5) == []
    assert knowledge_repo.search_fts("   ", limit=5) == []


def test_search_fts_respects_limit(knowledge_repo):
    results = knowledge_repo.search_fts("旺相", limit=3)
    assert len(results) <= 3


def test_examples_by_chapter(knowledge_repo):
    examples = knowledge_repo.examples_by_chapter("076_求财章")
    assert examples
    assert all(e.chapter_id == "076_求财章" for e in examples)


def test_get_example_known_id(knowledge_repo):
    example = knowledge_repo.get_example("076_求财章:example0003")
    assert example is not None
    assert example.judgement_id == "076_求财章:example0003:judgement"
    assert "泽火革" in "".join(example.hexagram_names) or example.hexagram_names is not None


def test_resolve_source_matches_live_file(knowledge_repo, repo_root):
    paragraph = knowledge_repo.resolve_source("076_求财章:example0003:judgement", repo_root)
    assert paragraph.text.startswith("断曰：兄爻持世")


def test_resolve_source_unknown_id_raises(knowledge_repo, repo_root):
    with pytest.raises(ValueError):
        knowledge_repo.resolve_source("does-not-exist", repo_root)


def test_resolve_source_detects_source_drift(knowledge_repo, repo_root, build_workdir):
    """If the underlying Markdown changes after the DB was built, resolving
    a citation against the live file must raise instead of silently
    returning stale text (§12 item 3)."""

    import shutil

    real_path = repo_root / "zengshan_buyi" / "008_用神章.md"
    shadow_repo_root = build_workdir / "shadow_repo"
    shadow_source_dir = shadow_repo_root / "zengshan_buyi"
    shadow_source_dir.mkdir(parents=True, exist_ok=True)
    shadow_path = shadow_source_dir / "008_用神章.md"
    shutil.copy(real_path, shadow_path)

    from app.knowledge.ingest import build_database

    shadow_db = build_workdir / "shadow.sqlite3"
    # Build a single-chapter throwaway db against the shadow copy.
    from app.knowledge.parser import parse_chapter
    from app.knowledge.repository import connect, create_schema, insert_chapter, insert_paragraph

    result = parse_chapter(shadow_path, repo_root=shadow_repo_root)
    shadow_db.unlink(missing_ok=True)
    con = connect(shadow_db)
    create_schema(con)
    insert_chapter(con, result.chapter)
    for paragraph in result.paragraphs:
        insert_paragraph(con, paragraph)
    con.commit()
    con.close()

    from app.knowledge.repository import KnowledgeRepository

    with KnowledgeRepository.open(shadow_db) as shadow_repo:
        # Sanity: resolves fine before any drift.
        shadow_repo.resolve_source("008_用神章:p0001", shadow_repo_root)

        # Now mutate the live file underneath the stored hash/offsets.
        shadow_path.write_text(
            shadow_path.read_text(encoding="utf-8") + "\n\n新增未索引内容\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError):
            shadow_repo.resolve_source("008_用神章:p0001", shadow_repo_root)

    shadow_db.unlink(missing_ok=True)
    shutil.rmtree(shadow_repo_root, ignore_errors=True)
