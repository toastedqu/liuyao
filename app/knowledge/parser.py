"""Parse one 《增删卜易》 Markdown chapter into stable, citable records.

The parser never rewrites, reflows, or normalizes original text. Every
``ParagraphRecord.text`` (and every example fragment) is an exact substring
of the source file, sliced by character offset, so verbatim-quote checks and
source round-trips are simple equality tests instead of heuristics.

Block splitting treats fenced ```...``` hexagram diagrams as atomic (blank
lines inside a fence do not end the block), then classifies each block as a
heading, an editorial aside, a plain rule/commentary paragraph, or -- when a
fenced block is found -- the chart of a 卦例 (worked example), pairing it
with the immediately preceding block (question) and immediately following
block (judgement) when available.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from app.knowledge.models import (
    ChapterParseResult,
    ChapterRecord,
    ContentType,
    ExampleRecord,
    Layer,
    ParagraphRecord,
    ParseWarning,
)
from app.knowledge.taxonomy import (
    ATTRIBUTION_MARKERS,
    EDITORIAL_MARKERS,
    RULE_TAG_KEYWORDS,
    TOPIC_TAG_KEYWORDS,
    categories_for_chapter,
    is_foundational,
)

CHAPTER_FILENAME_RE = re.compile(r"^(\d{3})_(.+)$")
CHAPTER_HEADING_RE = re.compile(r"^#\s*《增删卜易》(?:(\d{3})章、)?(.+?)\s*$")
HEADING_LINE_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$")
DIVIDER_RE = re.compile(r"^-{3,}$")
FENCE_MARKER_RE = re.compile(r"^```")
_EDITORIAL_MARKER_ALT = "|".join(EDITORIAL_MARKERS)
EDITORIAL_START_RE = re.compile(
    rf"^\*{{0,2}}[\[［]({_EDITORIAL_MARKER_ALT})[\]］]\*{{0,2}}\s*"
)
HEXAGRAM_NAME_RE = re.compile(r"[“\"]([^”\"]{2,8})[”\"]")


@dataclass
class _Block:
    start: int
    end: int
    text: str


def split_blocks(text: str) -> list[_Block]:
    """Split ``text`` into blank-line-delimited blocks, keeping fenced code
    blocks atomic and recording exact character offsets into ``text``."""

    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)

    blocks: list[_Block] = []
    in_fence = False
    cur_start: int | None = None
    cur_end: int | None = None

    for i, raw_line in enumerate(lines):
        content = raw_line.rstrip("\n").rstrip("\r")
        is_fence_marker = bool(FENCE_MARKER_RE.match(content.strip()))
        blank = content.strip() == "" and not in_fence

        if is_fence_marker:
            if cur_start is None:
                cur_start = offsets[i]
            in_fence = not in_fence
            cur_end = offsets[i] + len(content)
            continue

        if blank:
            if cur_start is not None:
                blocks.append(_Block(cur_start, cur_end, text[cur_start:cur_end]))
                cur_start = None
                cur_end = None
            continue

        if cur_start is None:
            cur_start = offsets[i]
        cur_end = offsets[i] + len(content)

    if cur_start is not None:
        blocks.append(_Block(cur_start, cur_end, text[cur_start:cur_end]))

    return blocks


def _detect_attributions(text: str) -> list[str]:
    found = []
    for marker in ATTRIBUTION_MARKERS:
        if marker in text:
            found.append(marker.rstrip("曰"))
    return found


def _detect_rule_tags(text: str) -> list[str]:
    tags = []
    for tag, keywords in RULE_TAG_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)
    return tags


def _detect_topic_tags(text: str) -> list[str]:
    tags = []
    for tag, keywords in TOPIC_TAG_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)
    return tags


def _extract_hexagram_names(text: str) -> list[str]:
    return list(dict.fromkeys(HEXAGRAM_NAME_RE.findall(text)))


def _fence_inner_span(block: _Block) -> tuple[int, int, str]:
    """Return (start, end, text) for the content strictly inside a fenced
    block, excluding the ``` marker lines themselves."""

    lines = block.text.split("\n")
    # First and last lines are the ``` markers.
    inner_lines = lines[1:-1]
    inner_text = "\n".join(inner_lines)
    # Compute offsets: skip past the opening fence line + its newline.
    first_line_len = len(lines[0])
    inner_start = block.start + first_line_len + 1  # +1 for the newline
    inner_end = inner_start + len(inner_text)
    return inner_start, inner_end, inner_text


def parse_chapter(path: Path, repo_root: Path | None = None) -> ChapterParseResult:
    """Parse a single chapter Markdown file into paragraphs and examples."""

    raw_bytes = path.read_bytes()
    text = raw_bytes.decode("utf-8")
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    if repo_root is not None:
        try:
            source_path = str(path.relative_to(repo_root))
        except ValueError:
            source_path = str(path)
    else:
        source_path = str(path)

    warnings: list[ParseWarning] = []

    filename_match = CHAPTER_FILENAME_RE.match(path.stem)
    if not filename_match:
        raise ValueError(f"Chapter filename does not match NNN_title.md: {path}")
    chapter_number = int(filename_match.group(1))
    chapter_id = path.stem

    first_line = text.splitlines()[0] if text else ""
    heading_match = CHAPTER_HEADING_RE.match(first_line)
    if heading_match:
        heading_number = heading_match.group(1)
        title = heading_match.group(2)
        if heading_number is not None and int(heading_number) != chapter_number:
            warnings.append(
                ParseWarning(
                    chapter_id=chapter_id,
                    message="Chapter number in heading does not match filename",
                    context=first_line,
                )
            )
    else:
        title = filename_match.group(2)
        warnings.append(
            ParseWarning(
                chapter_id=chapter_id,
                message="Chapter heading line did not match expected pattern",
                context=first_line,
            )
        )

    blocks = split_blocks(text)
    layer = Layer.FOUNDATIONAL if is_foundational(chapter_number) else Layer.CATEGORY
    category_tags = list(categories_for_chapter(chapter_number))

    paragraphs: list[ParagraphRecord] = []
    examples: list[ExampleRecord] = []

    paragraph_seq = 0
    example_seq = 0
    current_section = ""
    current_editorial_mode = False

    def next_paragraph_id() -> tuple[int, str]:
        nonlocal paragraph_seq
        paragraph_seq += 1
        return paragraph_seq, f"{chapter_id}:p{paragraph_seq:04d}"

    i = 0
    n = len(blocks)
    while i < n:
        block = blocks[i]
        stripped = block.text.strip()

        if DIVIDER_RE.match(stripped):
            i += 1
            continue

        heading_match = HEADING_LINE_RE.match(stripped)
        is_chapter_title_block = i == 0 and CHAPTER_HEADING_RE.match(stripped)
        if heading_match and not is_chapter_title_block:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2)
            seq, source_id = next_paragraph_id()
            paragraphs.append(
                ParagraphRecord(
                    source_id=source_id,
                    chapter_id=chapter_id,
                    seq=seq,
                    content_type=ContentType.HEADING,
                    layer=layer,
                    section_title=current_section,
                    text=block.text,
                    is_editorial=False,
                    topic_tags=_detect_topic_tags(heading_text),
                    category_tags=list(category_tags),
                    source_path=source_path,
                    source_sha256=sha256,
                    char_start=block.start,
                    char_end=block.end,
                )
            )
            current_section = heading_text
            current_editorial_mode = False
            i += 1
            continue

        if is_chapter_title_block:
            # The document title itself is chapter metadata, not a citable
            # paragraph; skip it here (it is recorded on ChapterRecord).
            i += 1
            continue

        if FENCE_MARKER_RE.match(stripped):
            example_seq += 1
            example_id = f"{chapter_id}:example{example_seq:04d}"

            question_id = None
            question_text = ""
            if paragraphs and paragraphs[-1].content_type in (
                ContentType.RULE,
                ContentType.EDITORIAL,
            ):
                question_para = paragraphs.pop()
                paragraph_seq -= 1
                question_id = f"{example_id}:question"
                question_text = question_para.text
                paragraphs.append(
                    question_para.model_copy(
                        update={
                            "source_id": question_id,
                            "content_type": ContentType.EXAMPLE_QUESTION,
                            "layer": Layer.EXAMPLE,
                            "example_id": example_id,
                        }
                    )
                )
            else:
                warnings.append(
                    ParseWarning(
                        chapter_id=chapter_id,
                        message=f"Example {example_id} has no preceding question paragraph",
                        context=stripped[:80],
                    )
                )

            chart_start, chart_end, chart_text = _fence_inner_span(block)
            chart_id = f"{example_id}:chart"
            paragraphs.append(
                ParagraphRecord(
                    source_id=chart_id,
                    chapter_id=chapter_id,
                    seq=-1,
                    content_type=ContentType.EXAMPLE_CHART,
                    layer=Layer.EXAMPLE,
                    section_title=current_section,
                    text=chart_text,
                    is_editorial=current_editorial_mode,
                    category_tags=list(category_tags),
                    example_id=example_id,
                    source_path=source_path,
                    source_sha256=sha256,
                    char_start=chart_start,
                    char_end=chart_end,
                )
            )

            judgement_id = None
            judgement_text = ""
            if i + 1 < n:
                nxt = blocks[i + 1]
                nxt_stripped = nxt.text.strip()
                if not DIVIDER_RE.match(nxt_stripped) and not HEADING_LINE_RE.match(
                    nxt_stripped
                ) and not FENCE_MARKER_RE.match(nxt_stripped):
                    judgement_id = f"{example_id}:judgement"
                    judgement_text = nxt.text
                    is_editorial = bool(EDITORIAL_START_RE.match(nxt_stripped))
                    paragraphs.append(
                        ParagraphRecord(
                            source_id=judgement_id,
                            chapter_id=chapter_id,
                            seq=-1,
                            content_type=ContentType.EXAMPLE_JUDGEMENT,
                            layer=Layer.EXAMPLE,
                            section_title=current_section,
                            text=judgement_text,
                            is_editorial=is_editorial or current_editorial_mode,
                            attributions=_detect_attributions(judgement_text),
                            rule_tags=_detect_rule_tags(judgement_text),
                            topic_tags=_detect_topic_tags(judgement_text),
                            category_tags=list(category_tags),
                            example_id=example_id,
                            source_path=source_path,
                            source_sha256=sha256,
                            char_start=nxt.start,
                            char_end=nxt.end,
                        )
                    )
                    i += 1  # consume the judgement block too
            if judgement_id is None:
                warnings.append(
                    ParseWarning(
                        chapter_id=chapter_id,
                        message=f"Example {example_id} has no judgement paragraph",
                        context=stripped[:80],
                    )
                )

            combined_text = "\n".join(t for t in (question_text, chart_text, judgement_text) if t)
            examples.append(
                ExampleRecord(
                    example_id=example_id,
                    chapter_id=chapter_id,
                    seq=example_seq,
                    question_id=question_id,
                    chart_id=chart_id,
                    judgement_id=judgement_id,
                    hexagram_names=_extract_hexagram_names(combined_text),
                    category_tags=list(category_tags),
                    rule_tags=_detect_rule_tags(combined_text),
                    topic_tags=_detect_topic_tags(combined_text),
                    combined_text=combined_text,
                )
            )
            i += 1
            continue

        # Plain content block: either an editorial aside or a rule paragraph.
        is_editorial_start = bool(EDITORIAL_START_RE.match(stripped))
        if is_editorial_start:
            current_editorial_mode = True
        content_type = (
            ContentType.EDITORIAL
            if (is_editorial_start or current_editorial_mode)
            else ContentType.RULE
        )
        seq, source_id = next_paragraph_id()
        paragraphs.append(
            ParagraphRecord(
                source_id=source_id,
                chapter_id=chapter_id,
                seq=seq,
                content_type=content_type,
                layer=Layer.EDITORIAL if content_type == ContentType.EDITORIAL else layer,
                section_title=current_section,
                text=block.text,
                is_editorial=content_type == ContentType.EDITORIAL,
                attributions=_detect_attributions(block.text),
                rule_tags=_detect_rule_tags(block.text),
                topic_tags=_detect_topic_tags(block.text),
                category_tags=list(category_tags),
                source_path=source_path,
                source_sha256=sha256,
                char_start=block.start,
                char_end=block.end,
            )
        )
        i += 1

    editorial_count = sum(1 for p in paragraphs if p.is_editorial)

    chapter = ChapterRecord(
        chapter_id=chapter_id,
        chapter_number=chapter_number,
        title=title,
        source_path=source_path,
        source_sha256=sha256,
        paragraph_count=len(paragraphs),
        example_count=len(examples),
    )

    if editorial_count == 0 and chapter_number not in (0,):
        # Not every chapter has editorial asides; this is informational only
        # and intentionally not appended to warnings (would be too noisy).
        pass

    return ChapterParseResult(
        chapter=chapter, paragraphs=paragraphs, examples=examples, warnings=warnings
    )


def parse_corpus(source_dir: Path, repo_root: Path | None = None) -> list[ChapterParseResult]:
    """Parse every ``NNN_title.md`` file in ``source_dir``, in chapter order."""

    results = []
    for path in sorted(source_dir.glob("*.md")):
        results.append(parse_chapter(path, repo_root=repo_root))
    return results
