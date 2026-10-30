"""Turning plain text into chapters, shared by the TXT and PDF parsers (and the EPUB merge rule).

Plain text has no markup, so chapters are found from heading lines such as "CHAPTER 1. Loomings.",
"Chapter XII", "BOOK TWO" or "PART III". A table of contents is a run of heading-like lines with
no text between them, so three or more in a row stay ordinary text (see `_contents_lines`).
A heading followed directly by another heading has no text of its own ("PART ONE" just before
"CHAPTER 1") and is dropped.
"""

import re
from collections.abc import Sequence

from app.extraction.types import ParsedChapter

MIN_CHAPTER_CHARS = 100  # shorter sections (a lone "PART ONE" heading) merge into the next one
MAX_HEADING_CHARS = 120  # Moby-Dick has 99-character chapter titles
MIN_CONTENTS_RUN = 3  # this many heading-like lines in a row are a table of contents

_NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
    "sixteen|seventeen|eighteen|nineteen|twenty|first|second|third|fourth|fifth|last"
)
_HEADING = re.compile(
    rf"^(?:CHAPTER|Chapter|BOOK|Book|PART|Part|LETTER|Letter)\s+"
    rf"(?:\d+|[IVXLCDM]+|[ivxlcdm]+|(?i:{_NUMBER_WORDS}))\b"
)


def is_heading(paragraph: str) -> bool:
    return len(paragraph) <= MAX_HEADING_CHARS and _HEADING.match(paragraph) is not None


def split_at_headings(paragraphs: Sequence[str]) -> list[ParsedChapter]:
    """Chapters cut at heading paragraphs; without any headings, the whole text is one chapter."""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    contents = _contents_lines(paragraphs)
    for i, paragraph in enumerate(paragraphs):
        if i not in contents and is_heading(paragraph):
            sections.append((paragraph, []))
        elif sections:
            sections[-1][1].append(paragraph)
        else:
            preamble.append(paragraph)

    chapters = [ParsedChapter(None, "\n".join(preamble))] if preamble else []
    chapters += [ParsedChapter(title, "\n".join(body)) for title, body in sections if body]
    return merge_short(chapters)


def _contents_lines(paragraphs: Sequence[str]) -> set[int]:
    """Indexes of table-of-contents lines: runs of heading-like lines (long entries included).

    The last line of a run may be the first real chapter right after the contents; it only counts
    as contents if the same heading appears again later.
    """
    found: set[int] = set()
    run: list[int] = []
    for i, paragraph in enumerate([*paragraphs, ""]):  # the sentinel ends a final run
        if _HEADING.match(paragraph):
            run.append(i)
            continue
        if len(run) >= MIN_CONTENTS_RUN:
            *entries, last = run
            found.update(entries)
            if _key(paragraphs[last]) in {_key(p) for p in paragraphs[last + 1 :]}:
                found.add(last)
        run = []
    return found


def _key(heading: str) -> str:
    return " ".join(heading.lower().split())


def merge_short(chapters: list[ParsedChapter]) -> list[ParsedChapter]:
    """Fold heading-only sections into the following chapter, keeping the outer title."""
    merged: list[ParsedChapter] = []
    pending: ParsedChapter | None = None
    for chapter in chapters:
        if pending is not None:
            chapter = ParsedChapter(pending.title, f"{pending.text}\n{chapter.text}")
            pending = None
        if len(chapter.text) < MIN_CHAPTER_CHARS:
            pending = chapter
        else:
            merged.append(chapter)
    if pending is not None:  # a short last section stays on its own
        merged.append(pending)
    return merged
