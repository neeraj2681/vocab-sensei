"""Server-rendered, search-engine-friendly pages: the hardest words of public-domain books."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.api.deps import SettingsDep
from app.db.session import get_session
from app.services.public_pages import PublicPagesService

router = APIRouter(include_in_schema=False)

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True)
_CACHE = {"Cache-Control": "public, max-age=3600"}
_FOOTER_LINK_TEXT = "Vocab Sensei: learn the words of the books you read"


def _service(session: Annotated[Session, Depends(get_session)]) -> PublicPagesService:
    return PublicPagesService(session)


ServiceDep = Annotated[PublicPagesService, Depends(_service)]


def _render(template: str, status_code: int = 200, **context: Any) -> Response:
    html = _env.get_template(template).render(footer_link_text=_FOOTER_LINK_TEXT, **context)
    return Response(html, status_code=status_code, media_type="text/html", headers=_CACHE)


def _not_found(base: str) -> Response:
    return _render(
        "not_found.html",
        404,
        title="Book not found · Vocab Sensei",
        description="This book or chapter does not exist.",
        canonical=f"{base}/classics",
    )


def _base(settings: SettingsDep) -> str:
    return settings.email.app_base_url.rstrip("/")


def _marked(sentence: str | None, form: str | None) -> tuple[str, str, str] | None:
    """The sentence split around the first case-insensitive occurrence of `form`."""
    if not sentence or not form:
        return None
    at = sentence.lower().find(form.lower())
    if at < 0 or len(form.lower()) != len(sentence[at : at + len(form)].lower()):
        return None
    return sentence[:at], sentence[at : at + len(form)], sentence[at + len(form) :]


@router.get("/classics")
def books_page(service: ServiceDep, settings: SettingsDep) -> Response:
    base = _base(settings)
    return _render(
        "books.html",
        books=service.books(),
        title="Hard words in classic books · Vocab Sensei",
        description="The hardest words of public-domain books, chapter by chapter, with meanings.",
        canonical=f"{base}/classics",
    )


@router.get("/classics/{slug}")
def book_page(slug: str, service: ServiceDep, settings: SettingsDep) -> Response:
    base = _base(settings)
    book = service.book(slug)
    if book is None:
        return _not_found(base)
    return _render(
        "book.html",
        book=book,
        title=f"Hard words in {book.title}, chapter by chapter · Vocab Sensei",
        description=f"The hardest words of every chapter of {book.title}, with meanings.",
        canonical=f"{base}/classics/{book.slug}",
    )


@router.get("/classics/{slug}/chapter-{number}")
def chapter_page(slug: str, number: int, service: ServiceDep, settings: SettingsDep) -> Response:
    base = _base(settings)
    chapter = service.chapter(slug, number)
    if chapter is None:
        return _not_found(base)
    book = chapter.book
    words = [(w, _marked(w.sentence, w.form)) for w in chapter.words]
    last = len(book.chapters)
    return _render(
        "chapter.html",
        chapter=chapter,
        book=book,
        words=words,
        previous=number - 1 if number > 1 else None,
        next=number + 1 if number < last else None,
        title=f"Hard words in {book.title}, chapter {number} · Vocab Sensei",
        description=(
            f"The {len(words)} hardest words in chapter {number} of {book.title}, "
            "with meanings and the sentence from the book."
        ),
        canonical=f"{base}/classics/{book.slug}/chapter-{number}",
    )


@router.get("/sitemap.xml")
def sitemap(service: ServiceDep, settings: SettingsDep) -> Response:
    base = _base(settings)
    urls = [f"{base}/classics"]
    for summary in service.books():
        book = service.book(summary.slug)
        if book is None:
            continue
        urls.append(f"{base}/classics/{book.slug}")
        urls += [f"{base}/classics/{book.slug}/chapter-{c.number}" for c in book.chapters]
    xml = _env.get_template("sitemap.xml").render(urls=urls)
    return Response(xml, media_type="application/xml", headers=_CACHE)


@router.get("/robots.txt")
def robots(settings: SettingsDep) -> Response:
    text = f"User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: {_base(settings)}/sitemap.xml\n"
    return Response(text, media_type="text/plain", headers=_CACHE)
