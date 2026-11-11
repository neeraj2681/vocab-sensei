"""Adding Project Gutenberg books to a reader's shelf.

A book is downloaded and processed once, then shared: each reader's shelf (`ShelfBook`) lists the
ones they added. A reader may bring in one NEW book (not yet in the system) per 24 hours; books
someone else already added are free.
"""

import logging
import re
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import DocumentFormat, DocumentStatus
from app.core.slugs import slugify
from app.db.models import Document, ShelfBook
from app.db.types import utcnow
from app.dictionary.types import Dictionary
from app.repositories.documents import DocumentRepository
from app.services.catalogue import Catalogue, download
from app.services.documents import DocumentService

logger = logging.getLogger(__name__)

NEW_BOOK_INTERVAL = timedelta(hours=24)
DOWNLOAD_ERROR = "Couldn't download this book from Project Gutenberg. Try again later."


class DailyLimitError(Exception):
    """The reader already added a new book in the last 24 hours."""


class NotInCatalogueError(Exception):
    """No such book in Project Gutenberg's catalogue."""


def format_author(authors: str) -> str | None:
    """First author of "Austen, Jane, 1775-1817; Other, A" as "Jane Austen"; None if empty."""
    first = authors.split(";")[0]
    first = re.sub(r"\s*,?\s*\(?\d{0,4}\??\s*-\s*\d{0,4}\??\)?\s*$", "", first.strip())
    parts = [p.strip() for p in first.split(",") if p.strip()]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return f"{' '.join(parts[1:])} {parts[0]}"


class GutenbergService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        catalogue: Catalogue,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._session = session
        self._settings = settings
        self._catalogue = catalogue
        self._clock = clock

    def add_to_shelf(
        self, user_id: int, gutenberg_id: int, *, retry: bool = True
    ) -> tuple[Document, bool]:
        """(the book, True if it is new and must be fetched)."""
        book = self._catalogue.get(gutenberg_id)
        if book is None:
            raise NotInCatalogueError(gutenberg_id)
        document = self._session.scalars(
            select(Document).where(Document.gutenberg_id == gutenberg_id)
        ).first()
        if document is not None:
            self._shelve(user_id, document)
            fetch = document.status == DocumentStatus.FAILED
            if fetch:  # a retry is free
                document.status = DocumentStatus.UPLOADED
                document.error = None
            self._session.commit()
            return document, fetch

        cutoff = self._clock() - NEW_BOOK_INTERVAL
        recent = self._session.scalars(
            select(Document.id)
            .where(Document.added_by_user_id == user_id, Document.uploaded_at > cutoff)
            .limit(1)
        ).first()
        if recent is not None:
            raise DailyLimitError(user_id)
        filename = f"gutenberg-{gutenberg_id}.epub"
        document = Document(
            owner_user_id=None,
            title=book.title,
            author=format_author(book.authors),
            original_filename=filename,
            file_path=f"library/{filename}",
            format=DocumentFormat.EPUB,
            status=DocumentStatus.UPLOADED,
            gutenberg_id=gutenberg_id,
            slug=self._unique_slug(book.title),
            added_by_user_id=user_id,
            uploaded_at=self._clock(),
        )
        self._session.add(document)
        try:
            self._session.flush()
        except IntegrityError:  # someone added the same book (or slug) a moment ago
            self._session.rollback()
            if retry:
                return self.add_to_shelf(user_id, gutenberg_id, retry=False)
            raise
        self._shelve(user_id, document)
        self._session.commit()
        return document, True

    def remove_from_shelf(self, user_id: int, document_id: int) -> None:
        shelf_book = self._session.get(ShelfBook, (user_id, document_id))
        if shelf_book is not None:
            self._session.delete(shelf_book)
            self._session.commit()

    def shelf(self, user_id: int) -> list[Document]:
        return DocumentRepository(self._session).list_shelf(user_id)

    def _shelve(self, user_id: int, document: Document) -> None:
        if self._session.get(ShelfBook, (user_id, document.id)) is None:
            self._session.add(
                ShelfBook(user_id=user_id, document_id=document.id, added_at=self._clock())
            )

    def _unique_slug(self, title: str) -> str:
        base = slugify(title)
        slug, number = base, 1
        while self._session.scalars(select(Document.id).where(Document.slug == slug)).first():
            number += 1
            slug = f"{base}-{number}"
        return slug


def fetch_and_process(
    session: Session, settings: Settings, dictionary: Callable[[], Dictionary], document_id: int
) -> None:
    """Downloads a Gutenberg book's EPUB if it isn't on disk, then processes it like an upload.
    A failed download is stored on the document."""
    document = session.get(Document, document_id)
    if document is None:
        return
    path = settings.data_dir / document.file_path
    if not path.exists():
        url = f"https://www.gutenberg.org/ebooks/{document.gutenberg_id}.epub3.images"
        try:
            download(url, path)
        except OSError:
            logger.exception("downloading Gutenberg book %s failed", document.gutenberg_id)
            document.status = DocumentStatus.FAILED
            document.error = DOWNLOAD_ERROR
            session.commit()
            return
    DocumentService(session, settings, dictionary).process(document_id)
