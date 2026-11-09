"""The books a user is reading right now, in priority order, and the chapter they're on.

Quizzes draw words from these books (at most `MAX_READING`), in turns, starting at the current
chapter.
"""

from sqlalchemy.orm import Session

from app.core.enums import DocumentStatus
from app.db.models import CurrentReading, Document
from app.quiz.learning_list import MAX_READING, reading_chapters, suggested_chapters
from app.repositories.readings import ReadingRepository


class ReadingError(Exception):
    """A request the API rejects with the message as the reason."""


class ReadingService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._readings = ReadingRepository(session)

    def list_for(self, user_id: int) -> list[CurrentReading]:
        return self._readings.list_for(user_id)

    def get(self, user_id: int, document_id: int) -> CurrentReading | None:
        return self._readings.get(user_id, document_id)

    def start(self, user_id: int, document: Document) -> CurrentReading:
        """Adds the book at the lowest priority, from its first chapter."""
        if document.status != DocumentStatus.READY:
            raise ReadingError("This book isn't ready yet")
        if self._readings.get(user_id, document.id):
            raise ReadingError("You're already reading this book")
        reading_now = len(self._readings.list_for(user_id))
        if reading_now >= MAX_READING:
            raise ReadingError(
                f"You're reading {MAX_READING} books. Stop reading one of them first: "
                "its progress is kept."
            )
        reading = CurrentReading(
            user_id=user_id,
            document_id=document.id,
            priority=reading_now,
            current_chapter_index=0,
            chapters=suggested_chapters(0, len(document.chapters)),
        )
        self._readings.add(reading)
        self._session.commit()
        return reading

    def set_chapter(self, reading: CurrentReading, index: int) -> None:
        chapters = len(reading.document.chapters)
        if not 0 <= index < chapters:
            raise ReadingError(f"This book has chapters 0 to {chapters - 1}")
        reading.current_chapter_index = index
        reading.chapters = suggested_chapters(index, chapters)
        self._session.commit()

    def chapters(self, reading: CurrentReading) -> list[int]:
        """The chapters being read, in order."""
        return reading_chapters(
            reading.chapters, reading.current_chapter_index, len(reading.document.chapters)
        )

    def set_chapters(self, reading: CurrentReading, indexes: list[int]) -> None:
        """Marks exactly these chapters as being read; their words come first."""
        total = len(reading.document.chapters)
        if not indexes:
            raise ReadingError("Pick at least one chapter")
        if any(not 0 <= index < total for index in indexes):
            raise ReadingError(f"This book has chapters 0 to {total - 1}")
        chosen = sorted(set(indexes))
        reading.chapters = chosen  # a new list, so the change is saved
        reading.current_chapter_index = chosen[0]
        self._session.commit()

    def reorder(self, user_id: int, document_ids: list[int]) -> list[CurrentReading]:
        """Sets priorities from `document_ids`, which must list each current read exactly once."""
        readings = {r.document_id: r for r in self._readings.list_for(user_id)}
        if sorted(document_ids) != sorted(readings):
            raise ReadingError("List every book you're reading exactly once")
        for priority, document_id in enumerate(document_ids):
            readings[document_id].priority = priority
        self._session.commit()
        return self._readings.list_for(user_id)

    def stop(self, reading: CurrentReading) -> None:
        user_id = reading.user_id
        self._readings.delete(reading)
        self._session.flush()
        for priority, remaining in enumerate(self._readings.list_for(user_id)):
            remaining.priority = priority  # keep priorities 0..n-1 without gaps
        self._session.commit()
