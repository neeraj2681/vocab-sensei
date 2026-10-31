from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from app.extraction.pdf import PdfParser, paragraphs_of, paragraphs_of_page
from app.extraction.types import ParseError
from tests.extraction.pdf_builder import build_pdf

PARAGRAPH = [
    "Call me Ishmael. Some years ago, never mind how long precisely, having",
    "little or no money in my purse, and nothing particular to interest me on",
    "shore, I thought I would sail about a little.",
]
SECOND = [
    "It is a way I have of driving off the spleen and regulating the circula-",
    "tion of the blood, and of keeping my spirits up when they are low.",
]


def test_chapters_come_from_the_bookmarks(tmp_path: Path) -> None:
    pdf = build_pdf(
        tmp_path / "moby.pdf",
        [["Moby-Dick, or The Whale", *PARAGRAPH], PARAGRAPH, SECOND, PARAGRAPH],
        outline={1: "Loomings", 3: "The Carpet-Bag"},
    )

    book = PdfParser().parse(pdf)

    assert (book.title, book.author) == ("Moby-Dick", "Herman Melville")
    assert [c.title for c in book.chapters] == [None, "Loomings", "The Carpet-Bag"]
    assert "regulating the circulation of the blood" in book.chapters[1].text  # pages 1-2


def test_without_bookmarks_chapters_come_from_headings(tmp_path: Path) -> None:
    pdf = build_pdf(
        tmp_path / "moby.pdf",
        [["CHAPTER 1. Loomings.", *PARAGRAPH], ["CHAPTER 2. The Carpet-Bag.", *SECOND]],
    )

    book = PdfParser().parse(pdf)

    assert [c.title for c in book.chapters] == [
        "CHAPTER 1. Loomings.",
        "CHAPTER 2. The Carpet-Bag.",
    ]


def test_lines_are_joined_into_paragraphs() -> None:
    page = "\n".join([*PARAGRAPH, *SECOND, "42"])

    paragraphs = paragraphs_of_page(page)

    assert paragraphs == [
        " ".join(PARAGRAPH),
        "It is a way I have of driving off the spleen and regulating the circulation of the "
        "blood, and of keeping my spirits up when they are low.",
    ]  # hyphenated "circula-tion" rejoined; the page number dropped


def test_a_heading_line_starts_its_own_paragraph() -> None:
    page = "\n".join(
        ["the end of a paragraph that runs to the margin and keeps going on", "CHAPTER 2.", *SECOND]
    )

    assert paragraphs_of_page(page)[1] == "CHAPTER 2."


def test_a_wrapped_heading_is_joined() -> None:
    page = "\n".join(
        ["CHAPTER 57. Of Whales in Paint; in Teeth; in Wood; in Sheet-", "Iron; in Stars.", *SECOND]
    )

    assert paragraphs_of_page(page)[0] == (
        "CHAPTER 57. Of Whales in Paint; in Teeth; in Wood; in Sheet-Iron; in Stars."
    )


def test_a_paragraph_that_starts_like_a_heading_is_not_one() -> None:
    page = "\n".join(
        [
            "BOOK I. (Folio), CHAPTER II. (Right Whale).--In one respect this is the",
            "most venerable of the leviathans, hunted first.",
            *SECOND,
        ]
    )

    assert paragraphs_of_page(page)[0].startswith("BOOK I. (Folio), CHAPTER II. (Right Whale)")
    assert paragraphs_of_page(page)[0].endswith("leviathans, hunted first.")


def test_a_paragraph_continues_across_a_page_break() -> None:
    first_page = [*PARAGRAPH, "BOOK III. (Duodecimo), CHAPTER III. (Mealy-mouthed Porpoise).--The"]
    second_page = ["largest kind of Porpoise; and only found in the Pacific."]

    paragraphs = paragraphs_of(["\n".join(first_page), "\n".join(second_page)])

    assert paragraphs[-1] == (
        "BOOK III. (Duodecimo), CHAPTER III. (Mealy-mouthed Porpoise).--The "
        "largest kind of Porpoise; and only found in the Pacific."
    )


def test_missing_metadata_is_unknown(tmp_path: Path) -> None:
    pdf = build_pdf(tmp_path / "x.pdf", [PARAGRAPH], title=None, author=None)

    book = PdfParser().parse(pdf)

    assert (book.title, book.author) == (None, None)


def test_scanned_pdfs_are_rejected(tmp_path: Path) -> None:
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=420, height=595)  # pages with no text, like scanned images
    path = tmp_path / "scan.pdf"
    with path.open("wb") as out:
        writer.write(out)

    with pytest.raises(ParseError, match="scanned PDFs aren't supported yet"):
        PdfParser().parse(path)


def test_password_protected_pdfs_are_rejected(tmp_path: Path) -> None:
    source = build_pdf(tmp_path / "plain.pdf", [PARAGRAPH])
    writer = PdfWriter(clone_from=PdfReader(source))
    writer.encrypt(user_password="secret", algorithm="RC4-128")
    path = tmp_path / "locked.pdf"
    with path.open("wb") as out:
        writer.write(out)

    with pytest.raises(ParseError, match="password-protected"):
        PdfParser().parse(path)


def test_damaged_files_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.7\nnot really a pdf")

    with pytest.raises(ParseError, match="not a valid PDF"):
        PdfParser().parse(path)
