"""Typed data model for the 《增删卜易》knowledge base.

Every value that eventually reaches an LLM prompt or a user-facing citation
must be traceable to one row in this model, and every row must be traceable
back to an exact byte range in one file under ``zengshan_buyi/``. Nothing in
this module talks to SQLite directly; see ``repository.py`` for storage and
``parser.py`` for how these records are produced from Markdown.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """The kind of unit a stable id points at."""

    HEADING = "heading"
    RULE = "rule"
    EDITORIAL = "editorial"
    EXAMPLE_QUESTION = "example_question"
    EXAMPLE_CHART = "example_chart"
    EXAMPLE_JUDGEMENT = "example_judgement"


class Layer(str, Enum):
    """Corpus stratification described in implementation_plan.md §8.1."""

    FOUNDATIONAL = "foundational"  # base rules + general methodology (章 000-040)
    CATEGORY = "category"  # 各门类 (求财/婚姻/疾病 ...) chapters (章 041-140)
    EXAMPLE = "example"  # 卦例 question/chart/judgement fragments
    EDITORIAL = "editorial"  # [乾按]/[提要]/[居士按] ... asides


class ParseWarning(BaseModel):
    """A non-fatal anomaly surfaced by the parser for human review."""

    chapter_id: str
    message: str
    context: str = ""


class ChapterRecord(BaseModel):
    """One indexed Markdown file under ``zengshan_buyi/``."""

    chapter_id: str  # e.g. "008_用神章" (stable: derived from the filename)
    chapter_number: int
    title: str
    source_path: str  # path relative to the repository root
    source_sha256: str
    paragraph_count: int = 0
    example_count: int = 0


class ParagraphRecord(BaseModel):
    """One stable, individually citable unit of original text.

    ``source_id`` is the stable identifier referenced everywhere else in the
    system (e.g. ``"008_用神章:p0001"`` or
    ``"076_求财章:example0003:judgement"``).
    """

    source_id: str
    chapter_id: str
    seq: int
    content_type: ContentType
    layer: Layer
    section_title: str = ""
    text: str
    is_editorial: bool = False
    attributions: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    rule_tags: list[str] = Field(default_factory=list)
    category_tags: list[str] = Field(default_factory=list)
    example_id: Optional[str] = None
    source_path: str = ""
    source_sha256: str = ""
    char_start: int = 0
    char_end: int = 0


class ExampleRecord(BaseModel):
    """A 卦例 (worked example) grouping question/chart/judgement fragments."""

    example_id: str
    chapter_id: str
    seq: int
    question_id: Optional[str] = None
    chart_id: Optional[str] = None
    judgement_id: Optional[str] = None
    hexagram_names: list[str] = Field(default_factory=list)
    category_tags: list[str] = Field(default_factory=list)
    rule_tags: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    combined_text: str = ""


class ChapterParseResult(BaseModel):
    """Everything produced by parsing a single chapter file."""

    chapter: ChapterRecord
    paragraphs: list[ParagraphRecord]
    examples: list[ExampleRecord]
    warnings: list[ParseWarning]


class BuildStats(BaseModel):
    """Summary emitted by ``scripts/build_knowledge_base.py``."""

    chapters_indexed: int = 0
    expected_chapters: int = 141
    paragraphs_indexed: int = 0
    examples_indexed: int = 0
    editorial_paragraphs: int = 0
    warnings: list[ParseWarning] = Field(default_factory=list)
    db_path: str = ""
    built_at: str = ""

    @property
    def complete(self) -> bool:
        return self.chapters_indexed == self.expected_chapters
