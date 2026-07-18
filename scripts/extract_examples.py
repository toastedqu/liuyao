#!/usr/bin/env python3
"""Extract every 卦例 (worked example) from ``zengshan_buyi/*.md`` as JSON.

This is a standalone companion to ``build_knowledge_base.py``: it does not
touch SQLite at all, it just re-uses the same parser to produce a flat,
human-reviewable list of examples (question / hexagram diagram / judgement,
plus detected hexagram names, category tags and rule tags). This is intended
for building the golden-example test fixtures and blind-test set described
in implementation_plan.md §16.3, and for manually auditing parser quality.

Usage:
    python scripts/extract_examples.py [--source zengshan_buyi] \
        [--out data/generated/examples.json] [--chapter 076_求财章]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.knowledge.parser import parse_corpus  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=REPO_ROOT / "zengshan_buyi",
        help="Directory containing the NNN_title.md chapter files.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "data" / "generated" / "examples.json",
        help="Output JSON path.",
    )
    parser.add_argument(
        "--chapter",
        type=str,
        default=None,
        help="Only extract examples from this chapter_id (e.g. 076_求财章).",
    )
    args = parser.parse_args(argv)

    results = parse_corpus(args.source, repo_root=REPO_ROOT)
    if args.chapter:
        results = [r for r in results if r.chapter.chapter_id == args.chapter]
        if not results:
            print(f"No such chapter: {args.chapter}", file=sys.stderr)
            return 1

    paragraphs_by_id = {
        p.source_id: p for result in results for p in result.paragraphs
    }

    examples_out = []
    for result in results:
        for example in result.examples:
            question = paragraphs_by_id.get(example.question_id) if example.question_id else None
            chart = paragraphs_by_id.get(example.chart_id) if example.chart_id else None
            judgement = paragraphs_by_id.get(example.judgement_id) if example.judgement_id else None
            examples_out.append(
                {
                    "example_id": example.example_id,
                    "chapter_id": example.chapter_id,
                    "question": question.text if question else None,
                    "chart": chart.text if chart else None,
                    "judgement": judgement.text if judgement else None,
                    "hexagram_names": example.hexagram_names,
                    "category_tags": example.category_tags,
                    "rule_tags": example.rule_tags,
                    "topic_tags": example.topic_tags,
                }
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(examples_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total_chapters = len(results)
    total_examples = len(examples_out)
    missing_question = sum(1 for e in examples_out if e["question"] is None)
    missing_judgement = sum(1 for e in examples_out if e["judgement"] is None)
    print(f"chapters scanned : {total_chapters}")
    print(f"examples written : {total_examples}")
    print(f"missing question : {missing_question}")
    print(f"missing judgement: {missing_judgement}")
    print(f"output           : {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
