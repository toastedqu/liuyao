"""Retrieval pipeline over the knowledge base.

Implements the priority order from implementation_plan.md §8.3, explicitly
*not* using a vector database or semantic-similarity search (§8.3, §18):

1. **固定取用 (fixed pick)** -- the small, explicitly named pool of 凡例/
   用神/通用方法论 chapters (``taxonomy.FIXED_PICK_CHAPTER_IDS``) is always
   returned first.
2. **占类路由 (category routing)** -- paragraphs whose chapter is tagged
   with the requested 占类 (e.g. 求财, 婚姻).
3. **事实标签路由 (fact-tag routing)** -- paragraphs whose ``rule_tags``
   match a fact emitted by the (future) deterministic rules engine, e.g.
   ``MONTH_BREAK`` for a 月破 fact.
4. **卦例特征匹配 (example feature scoring)** -- 卦例 ranked by overlap of
   category, rule tags, and hexagram name with the current query.
5. **SQLite FTS5 (trigram)** -- a keyword fallback over the raw question
   text, used only to supplement, never to replace, the structured stages
   above.

Every returned item records which stage produced it, so callers (and tests)
can verify that nothing reached the LLM prompt through an unintended path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.knowledge.models import ExampleRecord, ParagraphRecord
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.taxonomy import FIXED_PICK_CHAPTER_IDS


@dataclass
class RetrievedParagraph:
    paragraph: ParagraphRecord
    stage: str


@dataclass
class ScoredExample:
    example: ExampleRecord
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    paragraphs: list[RetrievedParagraph]
    examples: list[ScoredExample]

    def paragraph_ids(self) -> list[str]:
        return [p.paragraph.source_id for p in self.paragraphs]


class Retriever:
    """Read-only retrieval over an already-built ``KnowledgeRepository``."""

    def __init__(self, repository: KnowledgeRepository):
        self._repo = repository
        self._fixed_pick_cache: list[ParagraphRecord] | None = None

    def fixed_pick(self) -> list[ParagraphRecord]:
        """Stage 1: 凡例、用神及通用方法论 -- always included."""

        if self._fixed_pick_cache is None:
            self._fixed_pick_cache = self._repo.paragraphs_by_chapter_ids(
                FIXED_PICK_CHAPTER_IDS
            )
        return self._fixed_pick_cache

    def by_category(self, category: str) -> list[ParagraphRecord]:
        """Stage 2: 占类路由."""

        return self._repo.paragraphs_by_category(category)

    def by_fact_tags(self, fact_tags: list[str]) -> list[ParagraphRecord]:
        """Stage 3: 事实标签路由."""

        return self._repo.paragraphs_by_rule_tags(fact_tags)

    def score_examples(
        self,
        *,
        category: str | None = None,
        fact_tags: list[str] | None = None,
        hexagram_name: str | None = None,
        limit: int = 5,
    ) -> list[ScoredExample]:
        """Stage 4: 卦例特征匹配.

        Scores every 卦例 by how many of (category, fact tags, hexagram
        name) it matches, and returns the top ``limit`` with a nonzero
        score, highest first, ties broken by chapter/seq for determinism.
        """

        fact_tags = fact_tags or []
        scored: list[ScoredExample] = []
        for example in self._repo.all_examples():
            score = 0.0
            reasons: list[str] = []
            if category and category in example.category_tags:
                score += 3.0
                reasons.append(f"category:{category}")
            overlap = set(fact_tags) & set(example.rule_tags)
            if overlap:
                score += 2.0 * len(overlap)
                reasons.append("rule_tags:" + ",".join(sorted(overlap)))
            if hexagram_name and any(
                hexagram_name in name or name in hexagram_name
                for name in example.hexagram_names
            ):
                score += 5.0
                reasons.append(f"hexagram:{hexagram_name}")
            if score > 0:
                scored.append(ScoredExample(example=example, score=score, reasons=reasons))

        scored.sort(key=lambda s: (-s.score, s.example.chapter_id, s.example.seq))
        return scored[:limit]

    def keyword_search(self, keywords: str, limit: int = 10) -> list[ParagraphRecord]:
        """Stage 5: SQLite FTS5 keyword supplement."""

        return self._repo.search_fts(keywords, limit=limit)

    def retrieve(
        self,
        *,
        category: str | None = None,
        fact_tags: list[str] | None = None,
        hexagram_name: str | None = None,
        keywords: str | None = None,
        example_limit: int = 5,
        fts_limit: int = 10,
    ) -> RetrievalResult:
        """Run the full staged pipeline and return a deduplicated result.

        Deduplication keeps the *first* (highest priority) stage a
        paragraph was found under.
        """

        fact_tags = fact_tags or []
        ordered: list[RetrievedParagraph] = []
        seen: set[str] = set()

        def add_all(paragraphs: list[ParagraphRecord], stage: str) -> None:
            for paragraph in paragraphs:
                if paragraph.source_id in seen:
                    continue
                seen.add(paragraph.source_id)
                ordered.append(RetrievedParagraph(paragraph=paragraph, stage=stage))

        add_all(self.fixed_pick(), "fixed_pick")
        if category:
            add_all(self.by_category(category), "category")
        if fact_tags:
            add_all(self.by_fact_tags(fact_tags), "fact_tag")
        if keywords:
            add_all(self.keyword_search(keywords, limit=fts_limit), "fts")

        examples = self.score_examples(
            category=category,
            fact_tags=fact_tags,
            hexagram_name=hexagram_name,
            limit=example_limit,
        )

        return RetrievalResult(paragraphs=ordered, examples=examples)
