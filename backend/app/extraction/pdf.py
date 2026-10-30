"""Text PDFs, read with pypdf (BSD).

Chapters come from the PDF's bookmarks (outline) when it has at least two top-level entries;
otherwise from heading lines, like plain text. PDF text arrives as visual lines, so paragraphs are
rebuilt: a line joins the previous one unless the previous line ended a sentence and was short
(the last line of a paragraph) or is a chapter heading (which may wrap onto one more line).
Page numbers on their own line are dropped. Scanned PDFs (images, no text layer) are rejected
until OCR arrives in Phase 2.
"""

import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf.generic import Destination

from app.extraction.chapters import is_heading, merge_short, split_at_headings
from app.extraction.types import ParsedChapter, ParsedDocument, ParseError

MIN_TEXT_PER_PAGE = 20  # fewer characters per page on average means there's no text layer
_SHORT_LINE = 0.75  # a line shorter than this share of the page's longest line can end a paragraph
_SENTENCE_END = re.compile(r"[.!?:;\"'\u201d\u2019)]$")  # incl. closing curly quotes
_PAGE_NUMBER = re.compile(r"^\W*\d+\W*$")


class PdfParser:
    def parse(self, path: Path) -> ParsedDocument:
        try:
            reader = PdfReader(path)
            if reader.is_encrypted and not reader.decrypt(""):
                raise ParseError("password-protected PDFs aren't supported")
            pages = [page.extract_text() or "" for page in reader.pages]
        except PdfReadError as exc:
            raise ParseError(f"not a valid PDF ({exc})") from None

        if sum(len(p.strip()) for p in pages) < MIN_TEXT_PER_PAGE * max(1, len(pages)):
            raise ParseError(
                "this PDF has no text layer (a scanned book?); scanned PDFs aren't supported yet"
            )

        chapters = _chapters_from_outline(reader, pages) or split_at_headings(paragraphs_of(pages))
        metadata = reader.metadata
        return ParsedDocument(
            title=_clean_field(metadata.title if metadata else None),
            author=_clean_field(metadata.author if metadata else None),
            chapters=chapters,
        )


def paragraphs_of(pages: list[str]) -> list[str]:
    """Paragraphs of consecutive pages; one cut off mid-sentence continues on the next page."""
    paragraphs: list[tuple[str, bool]] = []  # (text, is a heading)
    for page in pages:
        found = _page_paragraphs(page)
        if paragraphs and found:
            (last, last_heading), (first, first_heading) = paragraphs[-1], found[0]
            if not (last_heading or first_heading or _SENTENCE_END.search(last)):
                paragraphs[-1] = (_join(last, first), False)
                found = found[1:]
        paragraphs.extend(found)
    return [text for text, _ in paragraphs]


def paragraphs_of_page(text: str) -> list[str]:
    return [paragraph for paragraph, _ in _page_paragraphs(text)]


def _page_paragraphs(text: str) -> list[tuple[str, bool]]:
    """(paragraph, is a heading) for one page's visual lines."""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if line and not _PAGE_NUMBER.match(line)]
    if not lines:
        return []
    longest = max(len(line) for line in lines)

    def ends_paragraph(line: str) -> bool:  # the short last line of a paragraph
        return bool(_SENTENCE_END.search(line)) and len(line) < _SHORT_LINE * longest

    paragraphs: list[tuple[str, bool]] = []
    current = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        heading = _heading_at(lines, i, longest)
        if heading is not None:  # a heading is always a paragraph of its own
            if current:
                paragraphs.append((current, False))
            paragraphs.append((heading, True))
            current = ""
            i += 2 if heading != line else 1
            continue
        current = _join(current, line) if current else line
        if ends_paragraph(line):
            paragraphs.append((current, False))
            current = ""
        i += 1
    if current:
        paragraphs.append((current, False))
    return paragraphs


def _heading_at(lines: list[str], i: int, longest: int) -> str | None:
    """The heading starting at line i, if any; a long one may wrap onto the next line.

    A full-width line that just stops is the start of a paragraph that happens to begin like a
    heading ("BOOK I. (Folio), CHAPTER II. ...--In one respect this is the"), unless it and the
    next line together make a complete heading.
    """
    line = lines[i]
    if not is_heading(line):
        return None
    if _SENTENCE_END.search(line) or len(line) < _SHORT_LINE * longest:
        return line
    if i + 1 < len(lines):
        joined = _join(line, lines[i + 1])
        if is_heading(joined) and _SENTENCE_END.search(joined):
            return joined
    return None


def _join(text: str, line: str) -> str:
    """Appends a visual line: "circula-" + "tion" is "circulation"; "Sheet-" + "Iron" keeps it."""
    if text.endswith("-"):
        return text[:-1] + line if line[:1].islower() else text + line
    return f"{text} {line}"


def _chapters_from_outline(reader: PdfReader, pages: list[str]) -> list[ParsedChapter] | None:
    starts: list[tuple[int, str]] = []
    for item in reader.outline:  # nested lists are sub-entries; only top-level ones are chapters
        if isinstance(item, Destination):
            page = reader.get_destination_page_number(item)
            if page is not None and page >= 0 and (not starts or page > starts[-1][0]):
                starts.append((page, str(item.title).strip()))
    if len(starts) < 2:
        return None

    def text(first: int, end: int) -> str:
        return "\n".join(paragraphs_of(pages[first:end]))

    chapters = [ParsedChapter(None, text(0, starts[0][0]))] if starts[0][0] > 0 else []
    for i, (page, title) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(pages)
        chapters.append(ParsedChapter(title or None, text(page, end)))
    return merge_short([c for c in chapters if c.text])


_PLACEHOLDERS = {"untitled", "anonymous", "unknown", "author", "title"}  # filler some tools write


def _clean_field(value: object) -> str | None:
    text = " ".join(str(value).split()) if value else ""
    return text if text and text.lower() not in _PLACEHOLDERS else None
