"""SQLite storage for the 《增删卜易》knowledge base.

Schema overview
---------------
``chapters``    one row per indexed Markdown file (§8.2: 章节编号和标题、
                源文件路径和内容哈希).
``paragraphs``  one row per stable citable unit (§8.2: 段落 ID、原文、内容
                类型、主题标签、规则标签、适用占类). ``char_start``/
                ``char_end`` allow slicing the *original* file to verify a
                citation is not a paraphrase (§8.2, §12 item 3).
``examples``    one row per 卦例, linking its question/chart/judgement
                paragraph ids and pre-computed feature tags used for
                reference retrieval (§8.3 item 4), never as an outcome score.
``paragraphs_fts``  an FTS5 external-content index over ``paragraphs.text``
                using the ``trigram`` tokenizer (works for CJK text without
                a word-segmentation dependency), used only as the
                supplementary keyword search described in §8.3 item 5.

The module only depends on the standard library (``sqlite3``, ``json``).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from app.knowledge.models import (
    ChapterRecord,
    ContentType,
    ExampleRecord,
    Layer,
    ParagraphRecord,
)

SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE chapters (
    chapter_id TEXT PRIMARY KEY,
    chapter_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    paragraph_count INTEGER NOT NULL,
    example_count INTEGER NOT NULL
);

CREATE TABLE paragraphs (
    source_id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapters(chapter_id),
    seq INTEGER NOT NULL,
    content_type TEXT NOT NULL,
    layer TEXT NOT NULL,
    section_title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    is_editorial INTEGER NOT NULL DEFAULT 0,
    attributions TEXT NOT NULL DEFAULT '[]',
    topic_tags TEXT NOT NULL DEFAULT '[]',
    rule_tags TEXT NOT NULL DEFAULT '[]',
    category_tags TEXT NOT NULL DEFAULT '[]',
    example_id TEXT,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL
);

CREATE INDEX idx_paragraphs_chapter ON paragraphs(chapter_id);
CREATE INDEX idx_paragraphs_layer ON paragraphs(layer);
CREATE INDEX idx_paragraphs_example ON paragraphs(example_id);

CREATE TABLE paragraph_category_tags (
    source_id TEXT NOT NULL REFERENCES paragraphs(source_id),
    tag TEXT NOT NULL
);
CREATE INDEX idx_pct_tag ON paragraph_category_tags(tag);
CREATE INDEX idx_pct_source ON paragraph_category_tags(source_id);

CREATE TABLE paragraph_rule_tags (
    source_id TEXT NOT NULL REFERENCES paragraphs(source_id),
    tag TEXT NOT NULL
);
CREATE INDEX idx_prt_tag ON paragraph_rule_tags(tag);
CREATE INDEX idx_prt_source ON paragraph_rule_tags(source_id);

CREATE TABLE examples (
    example_id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapters(chapter_id),
    seq INTEGER NOT NULL,
    question_id TEXT,
    chart_id TEXT,
    judgement_id TEXT,
    hexagram_names TEXT NOT NULL DEFAULT '[]',
    category_tags TEXT NOT NULL DEFAULT '[]',
    rule_tags TEXT NOT NULL DEFAULT '[]',
    topic_tags TEXT NOT NULL DEFAULT '[]',
    combined_text TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_examples_chapter ON examples(chapter_id);

CREATE VIRTUAL TABLE paragraphs_fts USING fts5(
    text,
    content='paragraphs',
    content_rowid='rowid',
    tokenize='trigram'
);
"""


def connect(db_path: Path | str, read_only: bool = False) -> sqlite3.Connection:
    """Open a connection with sane defaults for this database."""

    if read_only:
        uri = f"file:{Path(db_path).as_posix()}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
    else:
        con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def create_schema(con: sqlite3.Connection) -> None:
    con.executescript(_SCHEMA_SQL)
    con.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )


def insert_chapter(con: sqlite3.Connection, chapter: ChapterRecord) -> None:
    con.execute(
        """
        INSERT INTO chapters (
            chapter_id, chapter_number, title, source_path, source_sha256,
            paragraph_count, example_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chapter.chapter_id,
            chapter.chapter_number,
            chapter.title,
            chapter.source_path,
            chapter.source_sha256,
            chapter.paragraph_count,
            chapter.example_count,
        ),
    )


def insert_paragraph(con: sqlite3.Connection, paragraph: ParagraphRecord) -> None:
    con.execute(
        """
        INSERT INTO paragraphs (
            source_id, chapter_id, seq, content_type, layer, section_title,
            text, is_editorial, attributions, topic_tags, rule_tags,
            category_tags, example_id, source_path, source_sha256,
            char_start, char_end
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            paragraph.source_id,
            paragraph.chapter_id,
            paragraph.seq,
            paragraph.content_type.value,
            paragraph.layer.value,
            paragraph.section_title,
            paragraph.text,
            int(paragraph.is_editorial),
            json.dumps(paragraph.attributions, ensure_ascii=False),
            json.dumps(paragraph.topic_tags, ensure_ascii=False),
            json.dumps(paragraph.rule_tags, ensure_ascii=False),
            json.dumps(paragraph.category_tags, ensure_ascii=False),
            paragraph.example_id,
            paragraph.source_path,
            paragraph.source_sha256,
            paragraph.char_start,
            paragraph.char_end,
        ),
    )
    con.execute(
        "INSERT INTO paragraphs_fts(rowid, text) VALUES ((SELECT rowid FROM paragraphs WHERE source_id = ?), ?)",
        (paragraph.source_id, paragraph.text),
    )
    for tag in paragraph.category_tags:
        con.execute(
            "INSERT INTO paragraph_category_tags(source_id, tag) VALUES (?, ?)",
            (paragraph.source_id, tag),
        )
    for tag in paragraph.rule_tags:
        con.execute(
            "INSERT INTO paragraph_rule_tags(source_id, tag) VALUES (?, ?)",
            (paragraph.source_id, tag),
        )


def insert_example(con: sqlite3.Connection, example: ExampleRecord) -> None:
    con.execute(
        """
        INSERT INTO examples (
            example_id, chapter_id, seq, question_id, chart_id, judgement_id,
            hexagram_names, category_tags, rule_tags, topic_tags, combined_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            example.example_id,
            example.chapter_id,
            example.seq,
            example.question_id,
            example.chart_id,
            example.judgement_id,
            json.dumps(example.hexagram_names, ensure_ascii=False),
            json.dumps(example.category_tags, ensure_ascii=False),
            json.dumps(example.rule_tags, ensure_ascii=False),
            json.dumps(example.topic_tags, ensure_ascii=False),
            example.combined_text,
        ),
    )


def _row_to_paragraph(row: sqlite3.Row) -> ParagraphRecord:
    return ParagraphRecord(
        source_id=row["source_id"],
        chapter_id=row["chapter_id"],
        seq=row["seq"],
        content_type=ContentType(row["content_type"]),
        layer=Layer(row["layer"]),
        section_title=row["section_title"],
        text=row["text"],
        is_editorial=bool(row["is_editorial"]),
        attributions=json.loads(row["attributions"]),
        topic_tags=json.loads(row["topic_tags"]),
        rule_tags=json.loads(row["rule_tags"]),
        category_tags=json.loads(row["category_tags"]),
        example_id=row["example_id"],
        source_path=row["source_path"],
        source_sha256=row["source_sha256"],
        char_start=row["char_start"],
        char_end=row["char_end"],
    )


def _row_to_example(row: sqlite3.Row) -> ExampleRecord:
    return ExampleRecord(
        example_id=row["example_id"],
        chapter_id=row["chapter_id"],
        seq=row["seq"],
        question_id=row["question_id"],
        chart_id=row["chart_id"],
        judgement_id=row["judgement_id"],
        hexagram_names=json.loads(row["hexagram_names"]),
        category_tags=json.loads(row["category_tags"]),
        rule_tags=json.loads(row["rule_tags"]),
        topic_tags=json.loads(row["topic_tags"]),
        combined_text=row["combined_text"],
    )


class KnowledgeRepository:
    """Read access to a built knowledge base.

    This class intentionally exposes only read operations: writing is the
    exclusive responsibility of ``ingest.build_database`` so that the
    database on disk always corresponds to a single, complete, atomic build.
    """

    def __init__(self, con: sqlite3.Connection):
        self._con = con

    @classmethod
    def open(cls, db_path: Path | str) -> "KnowledgeRepository":
        return cls(connect(db_path, read_only=True))

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> "KnowledgeRepository":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get_paragraph(self, source_id: str) -> Optional[ParagraphRecord]:
        row = self._con.execute(
            "SELECT * FROM paragraphs WHERE source_id = ?", (source_id,)
        ).fetchone()
        return _row_to_paragraph(row) if row else None

    def get_chapter(self, chapter_id: str) -> Optional[ChapterRecord]:
        row = self._con.execute(
            "SELECT * FROM chapters WHERE chapter_id = ?", (chapter_id,)
        ).fetchone()
        if not row:
            return None
        return ChapterRecord(
            chapter_id=row["chapter_id"],
            chapter_number=row["chapter_number"],
            title=row["title"],
            source_path=row["source_path"],
            source_sha256=row["source_sha256"],
            paragraph_count=row["paragraph_count"],
            example_count=row["example_count"],
        )

    def list_chapters(self) -> list[ChapterRecord]:
        rows = self._con.execute(
            "SELECT * FROM chapters ORDER BY chapter_number"
        ).fetchall()
        return [
            ChapterRecord(
                chapter_id=row["chapter_id"],
                chapter_number=row["chapter_number"],
                title=row["title"],
                source_path=row["source_path"],
                source_sha256=row["source_sha256"],
                paragraph_count=row["paragraph_count"],
                example_count=row["example_count"],
            )
            for row in rows
        ]

    def paragraphs_by_chapter(self, chapter_id: str) -> list[ParagraphRecord]:
        rows = self._con.execute(
            "SELECT * FROM paragraphs WHERE chapter_id = ? ORDER BY seq",
            (chapter_id,),
        ).fetchall()
        return [_row_to_paragraph(row) for row in rows]

    def paragraphs_by_layer(self, layer: Layer) -> list[ParagraphRecord]:
        rows = self._con.execute(
            "SELECT * FROM paragraphs WHERE layer = ? ORDER BY chapter_id, seq",
            (layer.value,),
        ).fetchall()
        return [_row_to_paragraph(row) for row in rows]

    def paragraphs_by_ids(self, source_ids: Iterable[str]) -> list[ParagraphRecord]:
        ids = list(source_ids)
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self._con.execute(
            f"SELECT * FROM paragraphs WHERE source_id IN ({placeholders})",
            ids,
        ).fetchall()
        by_id = {row["source_id"]: _row_to_paragraph(row) for row in rows}
        return [by_id[i] for i in ids if i in by_id]

    def paragraphs_by_chapter_ids(self, chapter_ids: Iterable[str]) -> list[ParagraphRecord]:
        ids = list(chapter_ids)
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self._con.execute(
            f"SELECT * FROM paragraphs WHERE chapter_id IN ({placeholders}) ORDER BY chapter_id, seq",
            ids,
        ).fetchall()
        return [_row_to_paragraph(row) for row in rows]

    def paragraphs_by_category(self, category: str) -> list[ParagraphRecord]:
        rows = self._con.execute(
            """
            SELECT p.* FROM paragraphs p
            JOIN paragraph_category_tags t ON t.source_id = p.source_id
            WHERE t.tag = ?
            ORDER BY p.chapter_id, p.seq
            """,
            (category,),
        ).fetchall()
        return [_row_to_paragraph(row) for row in rows]

    def paragraphs_by_rule_tags(self, tags: Iterable[str]) -> list[ParagraphRecord]:
        tag_list = list(dict.fromkeys(tags))
        if not tag_list:
            return []
        placeholders = ",".join("?" for _ in tag_list)
        rows = self._con.execute(
            f"""
            SELECT DISTINCT p.* FROM paragraphs p
            JOIN paragraph_rule_tags t ON t.source_id = p.source_id
            WHERE t.tag IN ({placeholders})
            ORDER BY p.chapter_id, p.seq
            """,
            tag_list,
        ).fetchall()
        return [_row_to_paragraph(row) for row in rows]

    def search_fts(self, query: str, limit: int = 20) -> list[ParagraphRecord]:
        term = query.strip()
        if not term:
            return []
        # FTS5's trigram tokenizer indexes (and can only match) runs of three
        # or more characters. Many core terms in this corpus are exactly two
        # characters (用神, 月破, 旬空, 六合, 六冲 ...), so short queries fall
        # back to a direct substring scan; FTS is only ever a supplement
        # (§8.3 item 5), so correctness here matters more than raw speed.
        if len(term) < 3:
            like_term = f"%{term.replace('%', '').replace('_', '')}%"
            rows = self._con.execute(
                "SELECT * FROM paragraphs WHERE text LIKE ? ESCAPE '\\' LIMIT ?",
                (like_term, limit),
            ).fetchall()
            return [_row_to_paragraph(row) for row in rows]

        escaped = term.replace('"', '""')
        rows = self._con.execute(
            """
            SELECT p.* FROM paragraphs p
            JOIN paragraphs_fts f ON f.rowid = p.rowid
            WHERE paragraphs_fts MATCH ?
            LIMIT ?
            """,
            (f'"{escaped}"', limit),
        ).fetchall()
        return [_row_to_paragraph(row) for row in rows]

    def examples_by_chapter(self, chapter_id: str) -> list[ExampleRecord]:
        rows = self._con.execute(
            "SELECT * FROM examples WHERE chapter_id = ? ORDER BY seq",
            (chapter_id,),
        ).fetchall()
        return [_row_to_example(row) for row in rows]

    def get_example(self, example_id: str) -> Optional[ExampleRecord]:
        row = self._con.execute(
            "SELECT * FROM examples WHERE example_id = ?", (example_id,)
        ).fetchone()
        return _row_to_example(row) if row else None

    def all_examples(self) -> list[ExampleRecord]:
        rows = self._con.execute("SELECT * FROM examples ORDER BY chapter_id, seq").fetchall()
        return [_row_to_example(row) for row in rows]

    def resolve_source(self, source_id: str, repo_root: Path | str) -> ParagraphRecord:
        """Return the paragraph for ``source_id`` after verifying that the
        stored text is still an exact substring of the live Markdown file on
        disk (§8.2: "引用必须返回本地原文"; §12 item 3).

        Raises ``ValueError`` if the source file has drifted since the
        knowledge base was built (different hash, or the recorded offsets no
        longer slice out the same text).
        """

        paragraph = self.get_paragraph(source_id)
        if paragraph is None:
            raise ValueError(f"Unknown source_id: {source_id}")

        full_path = Path(repo_root) / paragraph.source_path
        raw_bytes = full_path.read_bytes()
        import hashlib

        current_hash = hashlib.sha256(raw_bytes).hexdigest()
        if current_hash != paragraph.source_sha256:
            raise ValueError(
                f"Source file {paragraph.source_path} has changed since the "
                f"knowledge base was built (hash mismatch for {source_id})"
            )
        text = raw_bytes.decode("utf-8")
        excerpt = text[paragraph.char_start : paragraph.char_end]
        if excerpt != paragraph.text:
            raise ValueError(
                f"Stored text for {source_id} no longer matches the source file excerpt"
            )
        return paragraph
