"""Build pipeline tests: completeness, atomicity, and reproducibility."""

from __future__ import annotations

import sqlite3

import pytest

from app.knowledge.ingest import EXPECTED_CHAPTER_COUNT, KnowledgeBuildError, build_database


def _dump_all_rows(db_path) -> dict[str, list[tuple]]:
    con = sqlite3.connect(str(db_path))
    try:
        tables = ["chapters", "paragraphs", "examples"]
        return {
            table: con.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            for table in tables
        }
    finally:
        con.close()


def test_build_reports_complete_stats(knowledge_db_path, build_workdir):
    # Rebuild into a second path so this test doesn't depend on fixture
    # internals beyond the already-built db existing.
    second_path = build_workdir / "rebuild_stats_check.sqlite3"
    from tests.knowledge.conftest import SOURCE_DIR, REPO_ROOT

    stats = build_database(SOURCE_DIR, second_path, repo_root=REPO_ROOT)
    assert stats.chapters_indexed == EXPECTED_CHAPTER_COUNT
    assert stats.expected_chapters == EXPECTED_CHAPTER_COUNT
    assert stats.complete is True
    assert stats.paragraphs_indexed > 2000
    assert stats.examples_indexed == 321
    assert stats.editorial_paragraphs > 0
    assert isinstance(stats.warnings, list)
    second_path.unlink(missing_ok=True)


def test_build_is_reproducible_across_independent_runs(build_workdir):
    from tests.knowledge.conftest import SOURCE_DIR, REPO_ROOT

    path_a = build_workdir / "repro_a.sqlite3"
    path_b = build_workdir / "repro_b.sqlite3"
    try:
        stats_a = build_database(SOURCE_DIR, path_a, repo_root=REPO_ROOT)
        stats_b = build_database(SOURCE_DIR, path_b, repo_root=REPO_ROOT)

        assert stats_a.chapters_indexed == stats_b.chapters_indexed
        assert stats_a.paragraphs_indexed == stats_b.paragraphs_indexed
        assert stats_a.examples_indexed == stats_b.examples_indexed
        assert len(stats_a.warnings) == len(stats_b.warnings)

        rows_a = _dump_all_rows(path_a)
        rows_b = _dump_all_rows(path_b)
        assert rows_a == rows_b
    finally:
        path_a.unlink(missing_ok=True)
        path_b.unlink(missing_ok=True)


def test_build_rejects_incomplete_source_tree(build_workdir):
    """If the corpus does not contain the expected number of chapters, the
    build must fail loudly rather than silently index a subset."""

    target = build_workdir / "should_not_exist.sqlite3"
    target.unlink(missing_ok=True)
    with pytest.raises(KnowledgeBuildError):
        build_database(
            source_dir=build_workdir,  # has no NNN_title.md chapter files
            db_path=target,
        )
    assert not target.exists()


def test_failed_build_does_not_clobber_existing_database(build_workdir):
    """Atomicity: a failed rebuild must leave a pre-existing database file at
    the target path completely untouched."""

    from tests.knowledge.conftest import SOURCE_DIR, REPO_ROOT

    target = build_workdir / "atomic_target.sqlite3"
    build_database(SOURCE_DIR, target, repo_root=REPO_ROOT)
    original_bytes = target.read_bytes()

    empty_source = build_workdir / "empty_source_dir"
    empty_source.mkdir(exist_ok=True)
    try:
        with pytest.raises(KnowledgeBuildError):
            build_database(empty_source, target, repo_root=REPO_ROOT)
        assert target.read_bytes() == original_bytes
    finally:
        target.unlink(missing_ok=True)
        empty_source.rmdir()


def test_build_leaves_no_stray_temp_files(build_workdir):
    from tests.knowledge.conftest import SOURCE_DIR, REPO_ROOT

    target = build_workdir / "no_stray_temp.sqlite3"
    before = set(build_workdir.iterdir())
    build_database(SOURCE_DIR, target, repo_root=REPO_ROOT)
    after = set(build_workdir.iterdir())
    new_entries = after - before
    assert new_entries == {target}
    target.unlink(missing_ok=True)


def test_missing_source_directory_raises(build_workdir):
    missing = build_workdir / "does_not_exist_at_all"
    with pytest.raises(KnowledgeBuildError):
        build_database(missing, build_workdir / "unused.sqlite3")
