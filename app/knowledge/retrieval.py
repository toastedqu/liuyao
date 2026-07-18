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

import re
from dataclasses import dataclass, field

from app.knowledge.models import ContentType, ExampleRecord, Layer, ParagraphRecord
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.taxonomy import FIXED_PICK_CHAPTER_IDS


_CHINESE_RUN_RE = re.compile(r"[\u3400-\u9fff]+")
_QUERY_STOP_PHRASES = (
    "本次",
    "此次",
    "这次",
    "这个",
    "请问",
    "想问",
    "是否",
    "能否",
    "可否",
    "会不会",
    "怎么样",
    "如何",
    "何时",
    "可以",
    "能够",
    "顺利",
    "事情",
    "情况",
    "结果",
    "目前",
    "未来",
)
_NON_DISCRIMINATING_EXAMPLE_TAGS = {"EMPTY_TOMB", "WORLD_RESPONSE"}
_USEFUL_RELATIVE_TERMS = {
    "父母": ("父母", "父爻", "母爻", "文书"),
    "兄弟": ("兄弟", "兄爻"),
    "官鬼": ("官鬼", "官爻", "鬼爻"),
    "妻财": ("妻财", "财爻", "财星"),
    "子孙": ("子孙", "子爻", "福神"),
}


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
            self._fixed_pick_cache = self._theory_only(
                self._repo.paragraphs_by_chapter_ids(FIXED_PICK_CHAPTER_IDS)
            )
        return self._fixed_pick_cache

    def by_category(self, category: str) -> list[ParagraphRecord]:
        """Stage 2: 占类路由."""

        return self._theory_only(self._repo.paragraphs_by_category(category))

    def by_fact_tags(self, fact_tags: list[str]) -> list[ParagraphRecord]:
        """Stage 3: 事实标签路由."""

        return self._theory_only(self._repo.paragraphs_by_rule_tags(fact_tags))

    def score_examples(
        self,
        *,
        category: str | None = None,
        fact_tags: list[str] | None = None,
        hexagram_name: str | None = None,
        changed_hexagram_name: str | None = None,
        query_text: str | None = None,
        useful_relative: str | None = None,
        limit: int = 5,
    ) -> list[ScoredExample]:
        """Stage 4: 卦例特征匹配.

        Scores every complete, non-editorial 卦例 by category specificity,
        current fact tags, primary/changed hexagram, useful relative and
        meaningful wording shared with the user's question. This keeps
        examples separate from theory paragraphs while making same-category
        cases about the actual asked matter rank ahead of generic early cases.
        """

        fact_tags = fact_tags or []
        query_terms = self._query_terms(query_text or "")
        scored: list[ScoredExample] = []
        for example in self._repo.all_examples():
            if not (
                example.question_id
                and example.chart_id
                and example.judgement_id
            ):
                continue
            judgement = self._repo.get_paragraph(example.judgement_id)
            if judgement is None or judgement.is_editorial:
                continue

            score = 0.0
            reasons: list[str] = []
            if category and category in example.category_tags:
                score += 15.0 / len(example.category_tags)
                reasons.append(f"category:{category}")
            overlap = (
                set(fact_tags)
                & set(example.rule_tags)
                - _NON_DISCRIMINATING_EXAMPLE_TAGS
            )
            if overlap:
                score += min(8.0, 2.5 * len(overlap))
                reasons.append("rule_tags:" + ",".join(sorted(overlap)))
            if hexagram_name and any(
                self._hexagram_role_matches(hexagram_name, name, role="primary")
                for name in example.hexagram_names
            ):
                score += 6.0
                reasons.append(f"hexagram:{hexagram_name}")
            if changed_hexagram_name and any(
                self._hexagram_role_matches(
                    changed_hexagram_name,
                    name,
                    role="changed",
                )
                for name in example.hexagram_names
            ):
                score += 3.0
                reasons.append(f"changed_hexagram:{changed_hexagram_name}")
            relative_terms = _USEFUL_RELATIVE_TERMS.get(
                useful_relative or "",
                (useful_relative,) if useful_relative else (),
            )
            if relative_terms and any(term in judgement.text for term in relative_terms):
                score += 1.5
                reasons.append(f"useful_relative:{useful_relative}")

            question_text = ""
            if example.question_id:
                question = self._repo.get_paragraph(example.question_id)
                question_text = question.text if question else ""
            matched_terms = self._maximal_matches(query_terms, question_text)
            if matched_terms:
                score += min(
                    6.0,
                    sum(max(1.0, (len(term) - 1) * 0.75) for term in matched_terms),
                )
                reasons.append("question_terms:" + ",".join(matched_terms[:5]))
            if score > 0:
                scored.append(ScoredExample(example=example, score=score, reasons=reasons))

        scored.sort(key=lambda s: (-s.score, s.example.chapter_id, s.example.seq))
        return scored[:limit]

    def keyword_search(self, keywords: str, limit: int = 10) -> list[ParagraphRecord]:
        """Stage 5: SQLite FTS5 keyword supplement."""

        return self._theory_only(self._repo.search_fts(keywords, limit=limit))

    def retrieve(
        self,
        *,
        category: str | None = None,
        fact_tags: list[str] | None = None,
        hexagram_name: str | None = None,
        changed_hexagram_name: str | None = None,
        keywords: str | None = None,
        example_query: str | None = None,
        useful_relative: str | None = None,
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
            changed_hexagram_name=changed_hexagram_name,
            query_text=example_query,
            useful_relative=useful_relative,
            limit=example_limit,
        )

        return RetrievalResult(paragraphs=ordered, examples=examples)

    @staticmethod
    def _theory_only(paragraphs: list[ParagraphRecord]) -> list[ParagraphRecord]:
        return [
            paragraph
            for paragraph in paragraphs
            if paragraph.content_type == ContentType.RULE
            and paragraph.layer != Layer.EXAMPLE
            and not paragraph.is_editorial
        ]

    @staticmethod
    def _query_terms(text: str) -> list[str]:
        cleaned = text
        for phrase in _QUERY_STOP_PHRASES:
            cleaned = cleaned.replace(phrase, " ")

        terms: set[str] = set()
        for run in _CHINESE_RUN_RE.findall(cleaned):
            if 2 <= len(run) <= 6:
                terms.add(run)
            for width in range(2, min(4, len(run)) + 1):
                terms.update(
                    run[index : index + width]
                    for index in range(len(run) - width + 1)
                )
        return sorted(terms, key=lambda term: (-len(term), term))

    @staticmethod
    def _maximal_matches(terms: list[str], text: str) -> list[str]:
        matches: list[str] = []
        for term in terms:
            if term not in text or any(term in longer for longer in matches):
                continue
            matches.append(term)
        return matches

    @staticmethod
    def _hexagram_role_matches(
        query_name: str,
        example_name: str,
        *,
        role: str,
    ) -> bool:
        parts = example_name.split("之", 1)
        if role == "primary":
            candidate = parts[0]
        elif role == "changed" and len(parts) == 2:
            candidate = parts[1]
        else:
            return False
        return bool(
            Retriever._hexagram_aliases(query_name)
            & Retriever._hexagram_aliases(candidate)
        )

    @staticmethod
    def _hexagram_aliases(name: str) -> set[str]:
        normalized = name.strip()
        aliases = {normalized}
        if len(normalized) >= 3 and normalized[1] == "为":
            aliases.add(normalized[0])
        elif len(normalized) > 2:
            aliases.add(normalized[2:])
        return aliases
