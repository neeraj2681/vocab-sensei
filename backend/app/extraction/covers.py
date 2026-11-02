"""A small cover picture for each book: the EPUB's own cover image, or a PDF's first page.

Books without one (plain text, or an EPUB that names no cover) get a generated cover in the browser.
"""

import io
import posixpath
import zipfile
from pathlib import Path

import pypdfium2
from bs4 import BeautifulSoup, Tag
from PIL import Image

from app.core.enums import DocumentFormat

THUMBNAIL_SIZE = (400, 600)  # largest width and height kept; shelves show ~150 px wide


def make_cover(path: Path, document_format: DocumentFormat) -> bytes | None:
    """A JPEG thumbnail for the book, or None if it has no usable cover."""
    try:
        if document_format is DocumentFormat.EPUB:
            image = _epub_cover(path)
        elif document_format is DocumentFormat.PDF:
            image = _pdf_first_page(path)
        else:
            return None
        return _thumbnail(image) if image is not None else None
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, pypdfium2.PdfiumError):
        return None  # a cover is a nicety: never let it break a book


def _epub_cover(path: Path) -> Image.Image | None:
    with zipfile.ZipFile(path) as archive:
        container = BeautifulSoup(archive.read("META-INF/container.xml"), "xml")
        rootfile = container.find("rootfile")
        if not isinstance(rootfile, Tag) or not rootfile.get("full-path"):
            return None
        opf_path = str(rootfile["full-path"])
        opf = BeautifulSoup(archive.read(opf_path), "xml")
        href = _cover_href(opf)
        if href is None:
            return None
        member = posixpath.normpath(posixpath.join(posixpath.dirname(opf_path), href))
        return Image.open(io.BytesIO(archive.read(member)))


def _cover_href(opf: BeautifulSoup) -> str | None:
    """EPUB 3 marks the cover image in the manifest; EPUB 2 names it in a <meta name="cover">."""
    images = [
        item
        for item in opf.find_all("item")
        if isinstance(item, Tag) and str(item.get("media-type", "")).startswith("image/")
    ]
    for item in images:
        if "cover-image" in str(item.get("properties", "")).split():
            return str(item["href"])
    meta = opf.find("meta", attrs={"name": "cover"})
    if isinstance(meta, Tag) and meta.get("content"):
        for item in images:
            if item.get("id") == meta["content"]:
                return str(item["href"])
    for item in images:  # last resort: an image called "cover"
        if "cover" in f"{item.get('id', '')} {item.get('href', '')}".lower():
            return str(item["href"])
    return None


def _pdf_first_page(path: Path) -> Image.Image | None:
    pdf = pypdfium2.PdfDocument(path)
    try:
        if len(pdf) == 0:
            return None
        page = pdf[0]
        scale = THUMBNAIL_SIZE[0] / page.get_width()  # PDF points to the thumbnail's width
        image: Image.Image = page.render(scale=scale).to_pil()
        return image
    finally:
        pdf.close()


def _thumbnail(image: Image.Image) -> bytes:
    image = image.convert("RGB")  # JPEG has no transparency or palette
    image.thumbnail(THUMBNAIL_SIZE)
    out = io.BytesIO()
    image.save(out, "JPEG", quality=82, optimize=True)
    return out.getvalue()
