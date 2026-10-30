from pathlib import Path

import pytest

from app.extraction.txt import TxtParser
from app.extraction.types import ParsedDocument, ParseError

GUTENBERG = """\
The Project Gutenberg eBook of Moby Dick; Or, The Whale

Title: Moby Dick; Or, The Whale

Author: Herman Melville

*** START OF THE PROJECT GUTENBERG EBOOK MOBY DICK; OR, THE WHALE ***

CONTENTS

CHAPTER 1. Loomings.

CHAPTER 2. The Carpet-Bag.


CHAPTER 1. Loomings.

Call me Ishmael. Some years ago--never mind how long precisely--having
little or no money in my purse, and nothing particular to interest me on
shore, I thought I would sail about a little and see the watery part of
the world.

It is a way I have of driving off the spleen and regulating the
circulation.


CHAPTER 2. The Carpet-Bag.

I stuffed a shirt or two into my old carpet-bag, tucked it under my arm,
and started for Cape Horn and the Pacific, quitting the good city of old
Manhatto.
"""


def parse(tmp_path: Path, content: bytes) -> ParsedDocument:
    path = tmp_path / "book.txt"
    path.write_bytes(content)
    return TxtParser().parse(path)


def test_reads_title_author_and_chapters(tmp_path: Path) -> None:
    path = tmp_path / "moby.txt"
    path.write_text(GUTENBERG)

    book = TxtParser().parse(path)

    assert (book.title, book.author) == ("Moby Dick; Or, The Whale", "Herman Melville")
    titles = [c.title for c in book.chapters]
    assert titles[-2:] == ["CHAPTER 1. Loomings.", "CHAPTER 2. The Carpet-Bag."]


def test_wrapped_lines_become_one_paragraph_per_line(tmp_path: Path) -> None:
    path = tmp_path / "moby.txt"
    path.write_text(GUTENBERG)

    loomings = TxtParser().parse(path).chapters[-2]

    first, second = loomings.text.split("\n")
    assert first.startswith("Call me Ishmael.")
    assert first.endswith("see the watery part of the world.")
    assert second == "It is a way I have of driving off the spleen and regulating the circulation."


def test_windows_line_endings_and_encoding(tmp_path: Path) -> None:
    text = "Caf\xe9 society was lugubrious.\r\n\r\nA second paragraph about it.\r\n"

    book = parse(tmp_path, text.encode("cp1252"))

    assert book.chapters[0].text == "Café society was lugubrious.\nA second paragraph about it."


def test_without_a_header_title_and_author_are_unknown(tmp_path: Path) -> None:
    book = parse(tmp_path, b"Just some text that is long enough to be a chapter of its own.")

    assert (book.title, book.author) == (None, None)


@pytest.mark.parametrize(
    ("content", "message"),
    [(b"", "no text"), (b"  \n\n  ", "no text"), (b"\x89PNG\r\n\x00\x00", "text file")],
)
def test_rejects_files_without_text(tmp_path: Path, content: bytes, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse(tmp_path, content)
