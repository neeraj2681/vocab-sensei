import zipfile
from pathlib import Path

import pytest

from app.core.enums import DocumentFormat
from app.extraction import epub
from app.extraction.epub import EpubParser
from app.extraction.registry import UnsupportedFormatError, get_parser
from app.extraction.types import ParsedChapter, ParseError
from tests.extraction.epub_builder import Chapter, EpubSpec, build_epub

LONG = " Long enough to count as a real chapter of its own, rather than a lone heading at the top."
LOOMINGS = Chapter(
    "text/ch1.xhtml",
    "<h1>Chapter 1. Loomings.</h1><p>Call me   Ishmael.</p>\n\n<p>Some years ago…</p>"
    f"<p>{LONG}</p>",
    toc_title="Loomings",
)
CARPET_BAG = Chapter(
    "text/ch2.xhtml",
    f"<h2>Chapter 2.</h2><p>I stuffed a shirt or two into my old carpet-bag.{LONG}</p>",
    toc_title="The Carpet-Bag",
)


def parse(tmp_path: Path, spec: EpubSpec) -> list[ParsedChapter]:
    return EpubParser().parse(build_epub(tmp_path / "book.epub", spec)).chapters


def test_reads_metadata_and_chapters_in_spine_order(tmp_path: Path) -> None:
    book = EpubParser().parse(build_epub(tmp_path / "b.epub", EpubSpec([LOOMINGS, CARPET_BAG])))

    assert book.title == "Moby-Dick"
    assert book.author == "Herman Melville"
    assert [c.title for c in book.chapters] == ["Loomings", "The Carpet-Bag"]


def test_text_is_plain_with_one_paragraph_per_line(tmp_path: Path) -> None:
    first = parse(tmp_path, EpubSpec([LOOMINGS]))[0]

    assert first.text == f"Chapter 1. Loomings.\nCall me Ishmael.\nSome years ago…\n{LONG.strip()}"


def test_paragraphs_break_only_at_block_elements(tmp_path: Path) -> None:
    body = (
        "<p>The <i>Pequod</i> sailed\n   on a hard-wrapped\nline.</p>"
        "<div>Next<br/>line after a break.</div>"
        "<ul><li>First item</li><li>Second <b>bold</b> item</li></ul>"
    )
    chapter = Chapter("c.xhtml", body + f"<p>{LONG}</p>")

    lines = parse(tmp_path, EpubSpec([chapter]))[0].text.split("\n")

    assert lines == [
        "The Pequod sailed on a hard-wrapped line.",
        "Next",
        "line after a break.",
        "First item",
        "Second bold item",
        LONG.strip(),
    ]


def test_styles_and_scripts_are_not_text(tmp_path: Path) -> None:
    chapter = Chapter("c.xhtml", f"<script>alert(1)</script><p>Real words.{LONG}</p>")

    assert parse(tmp_path, EpubSpec([chapter]))[0].text == f"Real words.{LONG}"


def test_titles_from_epub2_ncx(tmp_path: Path) -> None:
    chapters = parse(tmp_path, EpubSpec([LOOMINGS, CARPET_BAG], toc="ncx"))

    assert [c.title for c in chapters] == ["Loomings", "The Carpet-Bag"]


def test_falls_back_to_first_heading_without_toc(tmp_path: Path) -> None:
    chapters = parse(tmp_path, EpubSpec([LOOMINGS, CARPET_BAG], toc="none"))

    assert [c.title for c in chapters] == ["Chapter 1. Loomings.", "Chapter 2."]


def test_untitled_chapter_has_no_title(tmp_path: Path) -> None:
    chapter = Chapter("c.xhtml", f"<p>No heading here.{LONG}</p>")

    assert parse(tmp_path, EpubSpec([chapter], toc="none"))[0].title is None


def test_skips_nav_document_non_linear_and_empty_items(tmp_path: Path) -> None:
    cover = Chapter("cover.xhtml", '<img src="cover.jpg"/>')
    notes = Chapter("notes.xhtml", f"<p>Publisher's notes.{LONG}</p>", linear=False)

    chapters = parse(tmp_path, EpubSpec([cover, LOOMINGS, notes]))

    assert [c.title for c in chapters] == ["Loomings"]


def test_handles_package_at_zip_root_and_encoded_hrefs(tmp_path: Path) -> None:
    chapter = Chapter("chapter%20one.xhtml", f"<p>Spaces in the name.{LONG}</p>", toc_title="One")

    chapters = parse(tmp_path, EpubSpec([chapter], opf_dir=""))

    assert chapters == [ParsedChapter(title="One", text=f"Spaces in the name.{LONG}")]


def test_ignores_non_html_manifest_items_in_spine(tmp_path: Path) -> None:
    spec = EpubSpec([LOOMINGS], extra_manifest=[("img", "cover.jpg", "image/jpeg")])

    assert len(parse(tmp_path, spec)) == 1


def test_splits_one_file_into_chapters_at_toc_anchors(tmp_path: Path) -> None:
    body = (
        f'<div id="ch1"><h2>Chapter 1</h2><p>First.{LONG}</p></div>'
        f'<div id="ch2"><h2>Chapter 2</h2><p>Second.{LONG}</p></div>'
    )
    spec = EpubSpec(
        [Chapter("book.xhtml", body)],
        toc_links=[("book.xhtml#ch1", "One"), ("book.xhtml#ch2", "Two")],
    )

    chapters = parse(tmp_path, spec)

    assert [c.title for c in chapters] == ["One", "Two"]
    assert chapters[0].text.startswith("Chapter 1\nFirst.")
    assert chapters[1].text.startswith("Chapter 2\nSecond.")


def test_files_without_toc_entry_continue_the_previous_chapter(tmp_path: Path) -> None:
    spec = EpubSpec(
        [
            Chapter("part1.xhtml", f"<p>Start of a long chapter.{LONG}</p>", toc_title="Long"),
            Chapter("part1_split.xhtml", "<p>…and its continuation.</p>"),
            Chapter("next.xhtml", f"<p>Next one.{LONG}</p>", toc_title="Next"),
        ]
    )

    chapters = parse(tmp_path, spec)

    assert [c.title for c in chapters] == ["Long", "Next"]
    assert chapters[0].text.endswith("…and its continuation.")


def test_front_matter_before_first_toc_entry_is_kept_untitled(tmp_path: Path) -> None:
    spec = EpubSpec([Chapter("front.xhtml", f"<p>Copyright notice.{LONG}</p>"), LOOMINGS])

    assert [c.title for c in parse(tmp_path, spec)] == [None, "Loomings"]


def test_heading_only_sections_merge_into_the_next_one(tmp_path: Path) -> None:
    spec = EpubSpec(
        [
            Chapter(
                "epilogue.xhtml", f'<h2 id="e">Epilogue</h2><p id="t">The drama is done.{LONG}</p>'
            )
        ],
        toc_links=[("epilogue.xhtml#e", "Epilogue"), ("epilogue.xhtml#t", "Job")],
    )

    chapters = parse(tmp_path, spec)

    assert len(chapters) == 1
    assert chapters[0].title == "Epilogue"
    assert chapters[0].text.startswith("Epilogue\nThe drama is done.")


def test_toc_anchor_missing_from_file_still_titles_it(tmp_path: Path) -> None:
    spec = EpubSpec(
        [Chapter("c.xhtml", f"<p>Text.{LONG}</p>")], toc_links=[("c.xhtml#gone", "Title")]
    )

    assert parse(tmp_path, spec)[0].title == "Title"


def test_not_a_zip_file(tmp_path: Path) -> None:
    path = tmp_path / "fake.epub"
    path.write_text("definitely not a zip")

    with pytest.raises(ParseError, match="not a valid EPUB"):
        EpubParser().parse(path)


def test_zip_without_container(tmp_path: Path) -> None:
    path = tmp_path / "empty.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")

    with pytest.raises(ParseError, match=r"missing META-INF/container\.xml"):
        EpubParser().parse(path)


def test_book_without_text(tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="no readable text"):
        parse(tmp_path, EpubSpec([Chapter("cover.xhtml", '<img src="c.jpg"/>')]))


def test_rejects_huge_uncompressed_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(epub, "MAX_UNCOMPRESSED_BYTES", 100)

    with pytest.raises(ParseError, match="too large"):
        parse(tmp_path, EpubSpec([LOOMINGS]))


def test_registry_returns_epub_parser() -> None:
    assert isinstance(get_parser(DocumentFormat.EPUB), EpubParser)


def test_registry_rejects_formats_not_built_yet() -> None:
    with pytest.raises(UnsupportedFormatError, match="pdf"):
        get_parser(DocumentFormat.PDF)
