"""Builds small text PDFs for tests with reportlab (BSD)."""

from pathlib import Path

from reportlab.lib.pagesizes import A5
from reportlab.pdfgen.canvas import Canvas


def build_pdf(
    path: Path,
    pages: list[list[str]],
    *,
    outline: dict[int, str] | None = None,  # page index -> top-level bookmark title
    title: str | None = "Moby-Dick",
    author: str | None = "Herman Melville",
) -> Path:
    canvas = Canvas(str(path), pagesize=A5)
    if title:
        canvas.setTitle(title)
    if author:
        canvas.setAuthor(author)
    for index, lines in enumerate(pages):
        if outline and index in outline:
            key = f"page{index}"
            canvas.bookmarkPage(key)
            canvas.addOutlineEntry(outline[index], key, level=0)
        y = 560
        for line in lines:
            canvas.drawString(36, y, line)
            y -= 14
        canvas.showPage()
    canvas.save()
    return path
