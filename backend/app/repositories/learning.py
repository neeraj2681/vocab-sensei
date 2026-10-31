from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import WordStatus
from app.db.models import Chapter, Document, DocumentWord, QuizAnswer, UserWord, Word


class LearningRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def new_words(
        self, user_id: int, document_id: int, from_chapter: int, limit: int
    ) -> list[tuple[DocumentWord, Word, Chapter]]:
        """A book's words the user hasn't started on, from `from_chapter` on, in reading order."""
        not_started = or_(UserWord.word_id.is_(None), UserWord.status == WordStatus.NEW)
        query = self._book_words(user_id, document_id, from_chapter, not_started).limit(limit)
        return [(dw, w, c) for dw, w, c in self._session.execute(query)]

    def new_words_in_chapter(
        self, user_id: int, document_id: int, chapter_index: int, limit: int
    ) -> list[tuple[DocumentWord, Word, Chapter]]:
        """Like `new_words`, but only words that first appear in that one chapter."""
        not_started = or_(UserWord.word_id.is_(None), UserWord.status == WordStatus.NEW)
        query = self._book_words(user_id, document_id, chapter_index, not_started)
        query = query.where(Chapter.index == chapter_index).limit(limit)
        return [(dw, w, c) for dw, w, c in self._session.execute(query)]

    def chapter_word_ids(self, document_id: int, chapter_index: int) -> set[int]:
        return set(
            self._session.scalars(
                select(DocumentWord.word_id)
                .join(Chapter, Chapter.id == DocumentWord.chapter_id)
                .where(DocumentWord.document_id == document_id, Chapter.index == chapter_index)
            )
        )

    def progress_by_chapter(
        self, user_id: int, document_id: int
    ) -> list[tuple[int, UserWord | None]]:
        """(chapter index, the user's progress or None) for every word of the book."""
        progress = and_(UserWord.word_id == DocumentWord.word_id, UserWord.user_id == user_id)
        rows = self._session.execute(
            select(Chapter.index, UserWord)
            .select_from(DocumentWord)
            .join(Chapter, Chapter.id == DocumentWord.chapter_id)
            .outerjoin(UserWord, progress)
            .where(DocumentWord.document_id == document_id)
        )
        return [(index, word) for index, word in rows]

    def unsorted_words(
        self, user_id: int, document_id: int, from_chapter: int, limit: int
    ) -> list[tuple[DocumentWord, Word, Chapter]]:
        """A book's words the user has never sorted, answered or marked, in reading order."""
        query = self._book_words(user_id, document_id, from_chapter, UserWord.word_id.is_(None))
        return [(dw, w, c) for dw, w, c in self._session.execute(query.limit(limit))]

    def unsorted_count(self, user_id: int, document_id: int, from_chapter: int) -> int:
        query = self._book_words(user_id, document_id, from_chapter, UserWord.word_id.is_(None))
        return self._session.scalar(select(func.count()).select_from(query.subquery())) or 0

    def _book_words(
        self, user_id: int, document_id: int, from_chapter: int, condition: ColumnElement[bool]
    ) -> Select[DocumentWord, Word, Chapter]:
        progress = and_(UserWord.word_id == DocumentWord.word_id, UserWord.user_id == user_id)
        return (
            select(DocumentWord, Word, Chapter)
            .join(Word, Word.id == DocumentWord.word_id)
            .join(Chapter, Chapter.id == DocumentWord.chapter_id)
            .outerjoin(UserWord, progress)
            .where(
                DocumentWord.document_id == document_id, Chapter.index >= from_chapter, condition
            )
            .order_by(Chapter.index, DocumentWord.first_position)
            .options(selectinload(Word.definitions))
        )

    def in_library(self, user_id: int, word_id: int) -> bool:
        """Whether one of the user's books uses the word."""
        return bool(
            self._session.scalar(
                select(
                    exists()
                    .where(DocumentWord.word_id == word_id)
                    .where(Document.id == DocumentWord.document_id)
                    .where(Document.owner_user_id == user_id)
                )
            )
        )

    def was_quizzed(self, user_id: int, word_id: int) -> bool:
        return bool(
            self._session.scalar(
                select(exists().where(QuizAnswer.user_id == user_id, QuizAnswer.word_id == word_id))
            )
        )

    def user_word(self, user_id: int, word_id: int) -> UserWord | None:
        return self._session.get(UserWord, (user_id, word_id))

    def add(self, word: UserWord) -> None:
        self._session.add(word)

    def delete(self, word: UserWord) -> None:
        self._session.delete(word)
