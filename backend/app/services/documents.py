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
from app.extraction.cleanup import remove_nul_characters, strip_gutenberg_boilerplate
from app.extraction.covers import make_cover
from app.extraction.registry import get_parser
from app.extraction.types import ParsedDocument, ParseError
from app.extraction.words import WordExtractor
from app.repositories.documents import DocumentRepository
from app.services.library import CLASSICS
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

    def _extractor(self) -> WordExtractor:
        cache: dict[str, bool] = {}  # one book asks about the same rare token many times

        def known(lemma: str) -> bool:
            if lemma not in cache:
                try:  # loaded on the first unseen word only
                    cache[lemma] = bool(self._dictionary().senses(lemma))
                except DictionaryUnavailableError:
                    cache[lemma] = False  # no dictionary: keep today's behaviour
            return cache[lemma]

        return WordExtractor(self._settings.extraction, known=known)

    def process(self, document_id: int) -> None:
        document = self._documents.get(document_id)
        if document is None:  # deleted before processing started
            return
        document.status = DocumentStatus.PROCESSING
        self._session.commit()

        try:
            parsed = self._parse(document)
            if not parsed.chapters:
                raise ParseError("no readable text left after removing boilerplate")
            words = self._extractor().extract(parsed.chapters)

            document.title = (parsed.title or document.title)[:500]
            document.author = parsed.author[:300] if parsed.author else None
            document.chapters = [
                Chapter(index=i, title=c.title[:500] if c.title else None)
                for i, c in enumerate(parsed.chapters)
            ]
            self._session.flush()  # chapter ids are needed for the word list
            WordService(self._session).save_for_document(document, words, self._dictionary())
            self._save_cover(document)
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
        finally:
            self.discard_upload(document)

    def discard_upload(self, document: Document) -> bool:
        """Deletes an uploaded book's file once it has been read: only the word list, chapter
        titles, a short sentence per word and the cover thumbnail are kept, never the book itself.
        Built-in classics (public domain) keep theirs. True if a file was deleted."""
        if document.is_classic:
            return False
        path = self._path(document)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def reindex_chapters(self, document_id: int) -> bool:
        """Re-reads a ready book to record every chapter its words appear in (for books processed
        before that was stored). Its word list and everyone's progress are untouched."""
        document = self._documents.get(document_id)
        if document is None or document.status != DocumentStatus.READY:
            return False
        if not self._path(document).is_file():  # uploads are deleted once read
            return False
        try:
            parsed = self._parse(document)
        except (ParseError, OSError):
            logger.exception("couldn't re-read document %s", document_id)
            return False
        if len(parsed.chapters) != len(document.chapters):  # the parser changed since; skip it
            logger.warning("document %s now parses into different chapters", document_id)
            return False
        words = self._extractor().extract(parsed.chapters)
        WordService(self._session).reindex_chapters(document, words)
        self._session.commit()
        return True

    def list_for(self, owner_user_id: int) -> list[Document]:
        return self._documents.list_owned(owner_user_id)

    def get_for(self, user_id: int, document_id: int) -> Document | None:
        """A book the user may read: their own or a built-in classic."""
        return self._documents.get_readable(document_id, user_id)

    def get_owned(self, user_id: int, document_id: int) -> Document | None:
        """A book the user may change or delete (classics belong to nobody)."""
        return self._documents.get_owned(document_id, user_id)

    def list_classics(self) -> list[Document]:
        """The built-in classics only (not Gutenberg books readers added)."""
        return self._documents.list_classics({c.gutenberg_id for c in CLASSICS})

    def list_shelf(self, user_id: int) -> list[Document]:
        return self._documents.list_shelf(user_id)

    def word_counts(self, documents: list[Document]) -> dict[int, int]:
        counts = self._documents.word_counts([d.id for d in documents])
        return {d.id: counts.get(d.id, 0) for d in documents}

    def delete(self, document: Document) -> None:
        paths = [self._path(document), *self._cover_file(document)]
        self._documents.delete(document)
        self._session.commit()
        for path in paths:
            path.unlink(missing_ok=True)

    def cover_file(self, document: Document) -> Path | None:
        """The book's cover thumbnail on disk, if it has one."""
        found = self._cover_file(document)
        return found[0] if found and found[0].is_file() else None

    def add_missing_cover(self, document_id: int) -> bool:
        """Makes a cover for a ready book processed before covers existed. True if one was made."""
        document = self._documents.get(document_id)
        if document is None or document.status != DocumentStatus.READY or document.cover_path:
            return False
        if not self._path(document).is_file():  # uploads are deleted once read
            return False
        self._save_cover(document)
        self._session.commit()
        return document.cover_path is not None

    def _save_cover(self, document: Document) -> None:
        cover = make_cover(self._path(document), document.format)
        if cover is None:
            return
        relative = Path("covers", f"{document.id}.jpg")
        path = self._settings.data_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(cover)
        document.cover_path = relative.as_posix()

    def _cover_file(self, document: Document) -> list[Path]:
        return [self._settings.data_dir / document.cover_path] if document.cover_path else []

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

    def _parse(self, document: Document) -> ParsedDocument:
        parsed = get_parser(document.format).parse(self._path(document))
        return strip_gutenberg_boilerplate(remove_nul_characters(parsed))

    def _path(self, document: Document) -> Path:
        return self._settings.data_dir / document.file_path

    def _fail(self, document: Document, message: str) -> None:
        self._session.rollback()  # drop anything half-written
        document.status = DocumentStatus.FAILED
        document.error = message
        document.chapters = []
        self._session.commit()
