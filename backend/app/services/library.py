"""Built-in classics: public-domain books from Project Gutenberg that every user can read.

They are documents without an owner (see `Document.is_classic`), added by
`python -m app.commands.seed_classics`. A brand-new user is started on one automatically, so the
quiz has words before they upload anything.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import DocumentStatus
from app.db.models import CurrentReading, Document, QuizAnswer
from app.repositories.documents import DocumentRepository
from app.services.readings import ReadingService


@dataclass(frozen=True)
class Classic:
    gutenberg_id: int
    title: str

    @property
    def filename(self) -> str:
        return f"gutenberg-{self.gutenberg_id}.epub"

    @property
    def url(self) -> str:
        return f"https://www.gutenberg.org/ebooks/{self.gutenberg_id}.epub3.images"


# Easier to harder vocabulary, roughly.
CLASSICS = [
    Classic(11, "Alice's Adventures in Wonderland"),
    Classic(1661, "The Adventures of Sherlock Holmes"),
    Classic(1342, "Pride and Prejudice"),
    Classic(84, "Frankenstein"),
    Classic(174, "The Picture of Dorian Gray"),
    Classic(345, "Dracula"),
    Classic(1260, "Jane Eyre"),
    Classic(2701, "Moby-Dick"),
]


class LibraryService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._documents = DocumentRepository(session)

    def default_classic(self) -> Document | None:
        filename = Classic(self._settings.library.default_classic, "").filename
        document = self._documents.classic_by_filename(filename)
        return document if document and document.status == DocumentStatus.READY else None

    def start_default_if_new(self, user_id: int) -> CurrentReading | None:
        """Puts a user who has no current reads and has never answered on the default classic."""
        readings = ReadingService(self._session)
        if readings.list_for(user_id):
            return None
        answered = self._session.scalar(
            select(QuizAnswer.id).where(QuizAnswer.user_id == user_id).limit(1)
        )
        document = self.default_classic()
        if answered is not None or document is None:
            return None
        return readings.start(user_id, document)
