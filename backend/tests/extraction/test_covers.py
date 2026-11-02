import io
from pathlib import Path

from PIL import Image

from app.core.enums import DocumentFormat
from app.extraction.covers import make_cover
from tests.extraction.epub_builder import Chapter, EpubSpec, build_epub
from tests.extraction.pdf_builder import build_pdf

CHAPTERS = [Chapter("c1.xhtml", "<p>Call me Ishmael.</p>")]


def png(width: int, height: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", (width, height), (40, 120, 80, 255)).save(out, "PNG")
    return out.getvalue()


def size(jpeg: bytes) -> tuple[int, int]:
    image = Image.open(io.BytesIO(jpeg))
    assert image.format == "JPEG"
    return image.size


def test_an_epub3_cover_becomes_a_small_jpeg(tmp_path: Path) -> None:
    book = build_epub(tmp_path / "b.epub", EpubSpec(CHAPTERS, cover=png(1200, 1800)))

    cover = make_cover(book, DocumentFormat.EPUB)

    assert cover is not None
    assert size(cover) == (400, 600)  # scaled down, shape kept


def test_an_epub2_cover_named_in_the_metadata_is_found(tmp_path: Path) -> None:
    spec = EpubSpec(CHAPTERS, cover=png(300, 450), cover_style="epub2")
    book = build_epub(tmp_path / "b.epub", spec)

    cover = make_cover(book, DocumentFormat.EPUB)

    assert cover is not None
    assert size(cover) == (300, 450)  # small covers aren't enlarged


def test_an_epub_without_a_cover_has_none(tmp_path: Path) -> None:
    book = build_epub(tmp_path / "b.epub", EpubSpec(CHAPTERS))

    assert make_cover(book, DocumentFormat.EPUB) is None


def test_a_pdf_cover_is_its_first_page(tmp_path: Path) -> None:
    book = build_pdf(tmp_path / "b.pdf", [["CHAPTER 1.", "Call me Ishmael."]])

    cover = make_cover(book, DocumentFormat.PDF)

    assert cover is not None
    assert size(cover)[0] == 400


def test_text_books_and_broken_files_have_none(tmp_path: Path) -> None:
    text = tmp_path / "b.txt"
    text.write_text("Call me Ishmael.")
    broken = tmp_path / "b.epub"
    broken.write_bytes(b"not a zip")

    assert make_cover(text, DocumentFormat.TXT) is None
    assert make_cover(broken, DocumentFormat.EPUB) is None
