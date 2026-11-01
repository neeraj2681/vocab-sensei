"""Removes publisher boilerplate that isn't part of the book itself."""

import re
from dataclasses import replace

from app.extraction.types import ParsedChapter, ParsedDocument

# Project Gutenberg wraps every book in "*** START OF THE PROJECT GUTENBERG EBOOK ... ***" and
# "*** END OF THE PROJECT GUTENBERG EBOOK ... ***"; the license text comes after the end marker.
_GUTENBERG_START = re.compile(
    r"\*{3} ?START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK[^*]*\*{3}", re.I
)
_GUTENBERG_END = re.compile(r"\*{3} ?END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK", re.I)


def remove_nul_characters(document: ParsedDocument) -> ParsedDocument:
    """Drops NUL characters, which some PDFs contain and PostgreSQL can't store in text."""
    return replace(
        document,
        title=document.title.replace("\x00", "") if document.title else document.title,
        chapters=[
            ParsedChapter(
                title=c.title.replace("\x00", "") if c.title else c.title,
                text=c.text.replace("\x00", ""),
            )
            for c in document.chapters
        ],
    )


def strip_gutenberg_boilerplate(document: ParsedDocument) -> ParsedDocument:
    chapters = list(document.chapters)

    start = next((i for i, c in enumerate(chapters) if _GUTENBERG_START.search(c.text)), None)
    if start is not None:
        chapter = chapters[start]
        match = _GUTENBERG_START.search(chapter.text)
        assert match is not None
        chapters = [_with_text(chapter, chapter.text[match.end() :]), *chapters[start + 1 :]]

    end = next((i for i, c in enumerate(chapters) if _GUTENBERG_END.search(c.text)), None)
    if end is not None:
        chapter = chapters[end]
        match = _GUTENBERG_END.search(chapter.text)
        assert match is not None
        chapters = [*chapters[:end], _with_text(chapter, chapter.text[: match.start()])]

    return replace(document, chapters=[c for c in chapters if c.text])


def _with_text(chapter: ParsedChapter, text: str) -> ParsedChapter:
    return ParsedChapter(title=chapter.title, text=text.strip())
