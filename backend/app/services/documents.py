"""Uploading books and turning them into chapters and word lists.

Upload only stores the file; parsing and word extraction run afterwards (`process`, called from a
background task) so large books don't hold up the request. A document ends as READY or FAILED,
never stuck processing.
"""

import logging
import uuid
from collections.abc import Callable
from pathlib import Path, PurePath
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import DocumentFormat, DocumentStatus
from app.db.models import Chapter, Document
from app.dictionary.types import Dictionary, DictionaryUnavailableError
from app.extraction.cleanup import strip_gutenberg_boilerplate
from app.extraction.registry import get_parser
from app.extraction.types import ParseError
from app.extraction.words import WordExtractor
from app.repositories.documents import DocumentRepository
from app.services.words import WordService

logger = logging.getLogger(__name__)

_FORMATS = {".epub": DocumentFormat.EPUB, ".pdf": DocumentFormat.PDF, ".txt": DocumentFormat.TXT}
_CHUNK = 1024 * 1024


class UploadError(Exception):
    """Base class for upload problems the API reports to the user."""


class UnsupportedFileError(UploadError):
    pass


class FileTooLargeError(UploadError):
    pass


class DocumentService:
    def __init__(
        self, session: Session, settings: Settings, dictionary: Callable[[], Dictionary]
    ) -> None:
        self._session = session
        self._settings = settings
        self._dictionary = dictionary  # loaded only when a book is processed
        self._documents = DocumentRepository(session)

    def create(self, owner_user_id: int, filename: str, content: BinaryIO) -> Document:
        name = PurePath(filename).name  # never trust a client-supplied path
        document_format = _FORMATS.get(PurePath(name).suffix.lower())
        if document_format is None:
            raise UnsupportedFileError("Upload an EPUB, PDF or TXT file")

        relative = Path("uploads", str(owner_user_id), f"{uuid.uuid4().hex}{document_format.ext}")
        self._save(content, self._settings.data_dir / relative)
        document = self._documents.add(
            Document(
                owner_user_id=owner_user_id,
                title=PurePath(name).stem[:500] or "Untitled",
                original_filename=name[:255],
                file_path=relative.as_posix(),
                format=document_format,
                status=DocumentStatus.UPLOADED,
            )
        )
        self._session.commit()
        return document

    def process(self, document_id: int) -> None:
        document = self._documents.get(document_id)
        if document is None:  # deleted before processing started
            return
        document.status = DocumentStatus.PROCESSING
        self._session.commit()

        try:
            parsed = get_parser(document.format).parse(self._path(document))
            parsed = strip_gutenberg_boilerplate(parsed)
            if not parsed.chapters:
                raise ParseError("no readable text left after removing boilerplate")
            words = WordExtractor(self._settings.extraction).extract(parsed.chapters)

            document.title = (parsed.title or document.title)[:500]
            document.author = parsed.author[:300] if parsed.author else None
            document.chapters = [
                Chapter(index=i, title=c.title[:500] if c.title else None)
                for i, c in enumerate(parsed.chapters)
            ]
            self._session.flush()  # chapter ids are needed for the word list
            WordService(self._session).save_for_document(document, words, self._dictionary())
            document.status = DocumentStatus.READY
            document.error = None
            self._session.commit()
        except ParseError as exc:
            self._fail(document, f"Couldn't read this file: {exc}")
        except DictionaryUnavailableError:
            logger.exception("processing document %s failed", document_id)
            self._fail(document, "The dictionary isn't installed on the server yet")
        except Exception:
            logger.exception("processing document %s failed", document_id)
            self._fail(document, "Something went wrong while reading this file")

    def list_for(self, owner_user_id: int) -> list[Document]:
        return self._documents.list_owned(owner_user_id)

    def get_for(self, user_id: int, document_id: int) -> Document | None:
        """A book the user may read: their own or a built-in classic."""
        return self._documents.get_readable(document_id, user_id)

    def get_owned(self, user_id: int, document_id: int) -> Document | None:
        """A book the user may change or delete (classics belong to nobody)."""
        return self._documents.get_owned(document_id, user_id)

    def list_classics(self) -> list[Document]:
        return self._documents.list_classics()

    def word_counts(self, documents: list[Document]) -> dict[int, int]:
        counts = self._documents.word_counts([d.id for d in documents])
        return {d.id: counts.get(d.id, 0) for d in documents}

    def delete(self, document: Document) -> None:
        path = self._path(document)
        self._documents.delete(document)
        self._session.commit()
        path.unlink(missing_ok=True)

    def _save(self, content: BinaryIO, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with path.open("wb") as out:
                while chunk := content.read(_CHUNK):
                    written += len(chunk)
                    if written > self._settings.upload.max_bytes:
                        raise FileTooLargeError(
                            f"Files can be at most {self._settings.upload.max_bytes // 2**20} MB"
                        )
                    out.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        if written == 0:
            path.unlink(missing_ok=True)
            raise UnsupportedFileError("The file is empty")

    def _path(self, document: Document) -> Path:
        return self._settings.data_dir / document.file_path

    def _fail(self, document: Document, message: str) -> None:
        self._session.rollback()  # drop anything half-written
        document.status = DocumentStatus.FAILED
        document.error = message
        document.chapters = []
        self._session.commit()
