from app.extraction.cleanup import strip_gutenberg_boilerplate
from app.extraction.types import ParsedChapter, ParsedDocument


def doc(*chapters: tuple[str | None, str]) -> ParsedDocument:
    return ParsedDocument(
        title="Moby-Dick",
        author="Herman Melville",
        chapters=[ParsedChapter(title, text) for title, text in chapters],
    )


def test_removes_gutenberg_header_and_license() -> None:
    parsed = doc(
        (
            None,
            "The Project Gutenberg eBook of Moby-Dick\n*** START OF THE PROJECT GUTENBERG "
            "EBOOK MOBY-DICK; OR, THE WHALE ***",
        ),
        ("Loomings", "Call me Ishmael."),
        (
            "Epilogue",
            "The drama's done.\n*** END OF THE PROJECT GUTENBERG EBOOK MOBY-DICK ***\nmore",
        ),
        ("THE FULL PROJECT GUTENBERG LICENSE", "Please read this before you distribute."),
    )

    cleaned = strip_gutenberg_boilerplate(parsed)

    assert [(c.title, c.text) for c in cleaned.chapters] == [
        ("Loomings", "Call me Ishmael."),
        ("Epilogue", "The drama's done."),
    ]
    assert cleaned.title == "Moby-Dick"


def test_keeps_book_text_that_shares_a_chapter_with_the_header() -> None:
    parsed = doc(
        ("Start", "*** START OF THIS PROJECT GUTENBERG EBOOK X ***\nIt was a dark night."),
    )

    assert strip_gutenberg_boilerplate(parsed).chapters == [
        ParsedChapter("Start", "It was a dark night.")
    ]


def test_books_without_markers_are_unchanged() -> None:
    parsed = doc(("One", "Some text."), ("Two", "More text."))

    assert strip_gutenberg_boilerplate(parsed) == parsed
