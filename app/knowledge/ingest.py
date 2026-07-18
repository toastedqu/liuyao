"""Build the 《增删卜易》 SQLite knowledge base from ``zengshan_buyi/*.md``.

The build is:

* **Deterministic** -- chapters are processed in filename order, and all tag
  vocabularies are static data (see ``taxonomy.py``), so re-running the build
  against the same source tree always produces the same rows.
* **Atomic** -- the database is assembled in a temporary file next to the
  final path and only renamed into place (``os.replace``, atomic on the same
  filesystem) once the full build succeeds; a partially-built or corrupt
  database is never observable at ``db_path``.
* **Verified** -- ``build_database`` raises ``KnowledgeBuildError`` if fewer
  than the expected 141 chapters were indexed, so a silent partial build can
  never pass unnoticed (implementation_plan.md §8.3 milestone: "所有章节均
  被索引").
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.knowledge.models import BuildStats
from app.knowledge.parser import parse_corpus
from app.knowledge.repository import connect, create_schema, insert_chapter, insert_example, insert_paragraph

EXPECTED_CHAPTER_COUNT = 141


class KnowledgeBuildError(RuntimeError):
    """Raised when the corpus cannot be fully and correctly indexed."""


def build_database(
    source_dir: Path | str,
    db_path: Path | str,
    repo_root: Path | str | None = None,
    expected_chapters: int = EXPECTED_CHAPTER_COUNT,
) -> BuildStats:
    """Parse every chapter under ``source_dir`` and write a fresh database to
    ``db_path``, replacing any existing file atomically."""

    source_dir = Path(source_dir)
    db_path = Path(db_path)
    repo_root = Path(repo_root) if repo_root is not None else source_dir.parent

    if not source_dir.is_dir():
        raise KnowledgeBuildError(f"Source directory does not exist: {source_dir}")

    results = parse_corpus(source_dir, repo_root=repo_root)

    if len(results) != expected_chapters:
        raise KnowledgeBuildError(
            f"Expected {expected_chapters} chapters under {source_dir}, found {len(results)}"
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{db_path.name}.", suffix=".tmp", dir=str(db_path.parent)
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    tmp_path.unlink(missing_ok=True)  # sqlite3.connect must create it fresh

    stats = BuildStats(expected_chapters=expected_chapters, db_path=str(db_path))

    try:
        con = connect(tmp_path)
        try:
            create_schema(con)
            for result in results:
                insert_chapter(con, result.chapter)
                for paragraph in result.paragraphs:
                    insert_paragraph(con, paragraph)
                for example in result.examples:
                    insert_example(con, example)
                stats.paragraphs_indexed += len(result.paragraphs)
                stats.examples_indexed += len(result.examples)
                stats.editorial_paragraphs += sum(
                    1 for p in result.paragraphs if p.is_editorial
                )
                stats.warnings.extend(result.warnings)
            stats.chapters_indexed = len(results)
            con.commit()
        finally:
            con.close()

        if not stats.complete:
            raise KnowledgeBuildError(
                f"Indexed {stats.chapters_indexed} chapters, expected {expected_chapters}"
            )

        os.replace(tmp_path, db_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    stats.built_at = datetime.now(timezone.utc).isoformat()
    return stats
