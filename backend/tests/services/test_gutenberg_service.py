from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import DocumentFormat, DocumentStatus
from app.db.models import Document, ShelfBook
from app.db.types import utcnow
from app.services.catalogue import Catalogue
from app.services.gutenberg import (
    DailyLimitError,
    GutenbergService,
    NotInCatalogueError,
    format_author,
)
from tests.conftest import make_user

SAMPLE = Path(__file__).parent / "data" / "pg_catalog_sample.csv"


class Clock:
    def __init__(self) -> None:
        self.now = utcnow()

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def service(session: Session, settings: Settings, clock: Clock) -> GutenbergService:
    return GutenbergService(session, settings, Catalogue(SAMPLE), clock)


def test_a_new_book_is_created_and_shelved(service: GutenbergService, session: Session) -> None:
    user = make_user(session)
    document, fetch = service.add_to_shelf(user.id, 1342)

    assert fetch is True
    assert document.title == "Pride and Prejudice"
    assert document.author == "Jane Austen"
    assert document.slug == "pride-and-prejudice"
    assert document.added_by_user_id == user.id
    assert document.owner_user_id is None
    assert document.gutenberg_id == 1342
    assert document.original_filename == "gutenberg-1342.epub"
    assert document.file_path == "library/gutenberg-1342.epub"
    assert document.format == DocumentFormat.EPUB
    assert document.status == DocumentStatus.UPLOADED
    assert service.shelf(user.id) == [document]


def test_another_reader_gets_the_same_book_for_free(
    service: GutenbergService, session: Session
) -> None:
    first, second = make_user(session), make_user(session, "b@example.com")
    book, _ = service.add_to_shelf(first.id, 1342)
    other, fetch = service.add_to_shelf(second.id, 1342)
    later, _ = service.add_to_shelf(second.id, 158)  # still free to add a new one

    assert other.id == book.id
    assert fetch is False
    assert later.id != book.id
    assert len(session.scalars(select(Document)).all()) == 2


def test_adding_twice_is_harmless(service: GutenbergService, session: Session) -> None:
    user = make_user(session)
    service.add_to_shelf(user.id, 1342)
    document, fetch = service.add_to_shelf(user.id, 1342)

    assert fetch is False
    assert len(session.scalars(select(ShelfBook)).all()) == 1
    assert service.shelf(user.id) == [document]


def test_one_new_book_a_day(service: GutenbergService, session: Session, clock: Clock) -> None:
    user = make_user(session)
    service.add_to_shelf(user.id, 1342)

    with pytest.raises(DailyLimitError):
        service.add_to_shelf(user.id, 158)

    clock.now += timedelta(hours=24, seconds=1)
    document, fetch = service.add_to_shelf(user.id, 158)
    assert fetch is True
    assert document.gutenberg_id == 158


def test_a_failed_book_is_fetched_again_without_counting(
    service: GutenbergService, session: Session
) -> None:
    first, second = make_user(session), make_user(session, "b@example.com")
    book, _ = service.add_to_shelf(first.id, 1342)
    book.status = DocumentStatus.FAILED
    book.error = "Couldn't download this book from Project Gutenberg. Try again later."
    session.commit()
    service.add_to_shelf(second.id, 158)  # second's one new book today

    document, fetch = service.add_to_shelf(second.id, 1342)

    assert fetch is True
    assert document.id == book.id
    assert document.status == DocumentStatus.UPLOADED
    assert document.error is None


def test_a_book_not_in_the_catalogue(service: GutenbergService, session: Session) -> None:
    with pytest.raises(NotInCatalogueError):
        service.add_to_shelf(make_user(session).id, 999999)


def test_a_taken_slug_gets_a_number(service: GutenbergService, session: Session) -> None:
    user = make_user(session)
    session.add(
        Document(
            owner_user_id=None,
            title="Emma",
            original_filename="x.epub",
            file_path="library/x.epub",
            format=DocumentFormat.EPUB,
            slug="emma",
        )
    )
    session.commit()

    document, _ = service.add_to_shelf(user.id, 158)

    assert document.slug == "emma-2"


def test_removing_keeps_the_shared_book(service: GutenbergService, session: Session) -> None:
    user = make_user(session)
    document, _ = service.add_to_shelf(user.id, 1342)

    service.remove_from_shelf(user.id, document.id)

    assert service.shelf(user.id) == []
    assert session.get(Document, document.id) is not None


@pytest.mark.parametrize(
    ("authors", "expected"),
    [
        ("Austen, Jane, 1775-1817", "Jane Austen"),
        ("Gaiman, Neil, 1960-; Pratchett, Terry, 1948-2015", "Neil Gaiman"),
        ("A, B; C, D", "B A"),
        ("Smith, Anna", "Anna Smith"),
        ("Homer", "Homer"),
        ("", None),
    ],
)
def test_author_formatting(authors: str, expected: str | None) -> None:
    assert format_author(authors) == expected
