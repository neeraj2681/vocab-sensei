"""Plain-text books (e.g. Project Gutenberg .txt files).

Lines are usually hard-wrapped at ~70 characters with a blank line between paragraphs, so a
paragraph is a run of non-blank lines. Title and author come from a Gutenberg header if present.
"""

import re
from pathlib import Path

from app.extraction.chapters import split_at_headings
from app.extraction.types import ParsedDocument, ParseError

_HEADER_LINES = 60  # Gutenberg puts "Title:" / "Author:" near the top
_FIELD = re.compile(r"^(Title|Author):\s*(.+?)\s*$", re.M)


class TxtParser:
    def parse(self, path: Path) -> ParsedDocument:
        text = _decode(path.read_bytes())
        paragraphs = paragraphs_of(text)
        if not paragraphs:
            raise ParseError("the file has no text")
        header = "\n".join(text.splitlines()[:_HEADER_LINES])
        fields = {name: value for name, value in _FIELD.findall(header)}
        return ParsedDocument(
            title=fields.get("Title"),
            author=fields.get("Author"),
            chapters=split_at_headings(paragraphs),
        )


def paragraphs_of(text: str) -> list[str]:
    """One string per paragraph: blank lines separate paragraphs, wrapped lines are joined."""
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))
    return [" ".join(block.split()) for block in blocks if block.strip()]


def _decode(data: bytes) -> str:
    if b"\x00" in data[:4096]:
        raise ParseError("this doesn't look like a text file")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")  # older Windows-encoded files
