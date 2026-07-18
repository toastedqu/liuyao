"""《增删卜易》knowledge base: stable citations, SQLite/FTS5 storage, and the
staged (non-vector) retrieval pipeline described in implementation_plan.md §8.

Typical usage::

    from app.knowledge import KnowledgeRepository, Retriever

    with KnowledgeRepository.open(settings.KNOWLEDGE_DB_PATH) as repo:
        retriever = Retriever(repo)
        result = retriever.retrieve(category="求财", fact_tags=["MONTH_BREAK"])

Building (or rebuilding) the database itself is done by
``scripts/build_knowledge_base.py``, not by importing this package -- see
``app.knowledge.ingest.build_database`` for the underlying function.
"""

from __future__ import annotations

from app.knowledge.ingest import KnowledgeBuildError, build_database
from app.knowledge.models import (
    BuildStats,
    ChapterParseResult,
    ChapterRecord,
    ContentType,
    ExampleRecord,
    Layer,
    ParagraphRecord,
    ParseWarning,
)
from app.knowledge.parser import parse_chapter, parse_corpus
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.retrieval import RetrievalResult, RetrievedParagraph, Retriever, ScoredExample

__all__ = [
    "KnowledgeBuildError",
    "build_database",
    "BuildStats",
    "ChapterParseResult",
    "ChapterRecord",
    "ContentType",
    "ExampleRecord",
    "Layer",
    "ParagraphRecord",
    "ParseWarning",
    "parse_chapter",
    "parse_corpus",
    "KnowledgeRepository",
    "RetrievalResult",
    "RetrievedParagraph",
    "Retriever",
    "ScoredExample",
]
