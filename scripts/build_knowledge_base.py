#!/usr/bin/env python3
"""Build the 《增删卜易》 SQLite + FTS5 knowledge base.

Usage:
    python scripts/build_knowledge_base.py \
        [--source zengshan_buyi] \
        [--db data/generated/knowledge.sqlite3] \
        [--report data/generated/knowledge_build_report.json]

Exits non-zero (and prints the reason to stderr) if the corpus cannot be
fully indexed -- in particular if the number of parsed chapters does not
equal 141, per implementation_plan.md §8.3's milestone acceptance criterion
("所有章节均被索引").  Parse warnings (recoverable anomalies such as a 卦例
missing its judgement paragraph) are printed but do not fail the build.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.knowledge.ingest import KnowledgeBuildError, build_database  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=REPO_ROOT / "zengshan_buyi",
        help="Directory containing the NNN_title.md chapter files.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=REPO_ROOT / "data" / "generated" / "knowledge.sqlite3",
        help="Output SQLite database path.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPO_ROOT / "data" / "generated" / "knowledge_build_report.json",
        help="Where to write the JSON build statistics/warning report.",
    )
    parser.add_argument(
        "--expected-chapters",
        type=int,
        default=141,
        help="Number of chapters the build must find (default: 141).",
    )
    args = parser.parse_args(argv)

    try:
        stats = build_database(
            source_dir=args.source,
            db_path=args.db,
            repo_root=REPO_ROOT,
            expected_chapters=args.expected_chapters,
        )
    except KnowledgeBuildError as exc:
        print(f"knowledge base build FAILED: {exc}", file=sys.stderr)
        return 1

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        stats.model_dump_json(indent=2), encoding="utf-8"
    )

    print(f"chapters indexed   : {stats.chapters_indexed}/{stats.expected_chapters}")
    print(f"paragraphs indexed : {stats.paragraphs_indexed}")
    print(f"examples indexed   : {stats.examples_indexed}")
    print(f"editorial paragraphs: {stats.editorial_paragraphs}")
    print(f"parse warnings     : {len(stats.warnings)}")
    for warning in stats.warnings:
        print(f"  [warn] {warning.chapter_id}: {warning.message}")
    print(f"database written to: {args.db}")
    print(f"report written to  : {args.report}")

    if not stats.complete:
        print("knowledge base build FAILED: incomplete chapter coverage", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
