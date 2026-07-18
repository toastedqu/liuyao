"""End-to-end tests for the CLI scripts (build_knowledge_base, extract_examples)."""

from __future__ import annotations

import json

from scripts.build_knowledge_base import main as build_main
from scripts.extract_examples import main as extract_main


def test_build_knowledge_base_cli_success(build_workdir, source_dir, repo_root):
    db_path = build_workdir / "cli_build.sqlite3"
    report_path = build_workdir / "cli_build_report.json"
    exit_code = build_main(
        [
            "--source",
            str(source_dir),
            "--db",
            str(db_path),
            "--report",
            str(report_path),
        ]
    )
    assert exit_code == 0
    assert db_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["chapters_indexed"] == 141
    assert report["expected_chapters"] == 141

    db_path.unlink(missing_ok=True)
    report_path.unlink(missing_ok=True)


def test_build_knowledge_base_cli_fails_on_incomplete_source(build_workdir):
    empty_dir = build_workdir / "cli_empty_source"
    empty_dir.mkdir(exist_ok=True)
    db_path = build_workdir / "cli_should_not_exist.sqlite3"
    exit_code = build_main(["--source", str(empty_dir), "--db", str(db_path)])
    assert exit_code != 0
    assert not db_path.exists()
    empty_dir.rmdir()


def test_extract_examples_cli_writes_all_examples(build_workdir, source_dir):
    out_path = build_workdir / "cli_examples.json"
    exit_code = extract_main(["--source", str(source_dir), "--out", str(out_path)])
    assert exit_code == 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(data) == 321
    sample = next(e for e in data if e["example_id"] == "076_求财章:example0003")
    assert sample["judgement"].startswith("断曰：兄爻持世")
    assert sample["category_tags"] == ["求财"]
    out_path.unlink(missing_ok=True)


def test_extract_examples_cli_single_chapter_filter(build_workdir, source_dir):
    out_path = build_workdir / "cli_examples_single.json"
    exit_code = extract_main(
        ["--source", str(source_dir), "--out", str(out_path), "--chapter", "076_求财章"]
    )
    assert exit_code == 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data
    assert all(e["chapter_id"] == "076_求财章" for e in data)
    out_path.unlink(missing_ok=True)


def test_extract_examples_cli_unknown_chapter_fails(build_workdir, source_dir):
    out_path = build_workdir / "cli_examples_unknown.json"
    exit_code = extract_main(
        ["--source", str(source_dir), "--out", str(out_path), "--chapter", "999_不存在"]
    )
    assert exit_code != 0
    assert not out_path.exists()
