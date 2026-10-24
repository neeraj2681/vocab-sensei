from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class ParseError(Exception):
    """The file is damaged, not the format it claims to be, or has no readable text."""


@dataclass(frozen=True)
class ParsedChapter:
    title: str | None
    text: str  # plain text, one paragraph per line


@dataclass(frozen=True)
class ParsedDocument:
    title: str | None
    author: str | None
    chapters: list[ParsedChapter] = field(default_factory=list)


class DocumentParser(Protocol):
    def parse(self, path: Path) -> ParsedDocument: ...
