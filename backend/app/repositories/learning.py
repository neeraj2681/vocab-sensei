from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.core.enums import WordStatus
from app.db.models import (
    Chapter,
    ChapterWord,
    Document,
    DocumentWord,
    QuizAnswer,
    UserWord,
    Word,
)
from app.repositories.documents import readable_by

_NOT_STARTED = or_(UserWord.word_id.is_(None), UserWord.status == WordStatus.NEW)
_UNSORTED = UserWord.word_id.is_(None)


class LearningRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def new_words(
        self,
        user_id: int,
        document_id: int,
        from_chapter: int,
        limit: int,
        *,
        earlier: bool = False,
    ) -> list[tuple[ChapterWord, Word, Chapter]]:
        """A book's words the user hasn't started on, in reading order: from `from_chapter` on
        (each at its next appearance), or with `earlier`, those used only before it."""
        query = self._frontier(user_id, document_id, from_chapter, _NOT_STARTED, earlier=earlier)
        return [(cw, w, c) for cw, w, c in self._session.execute(query.limit(limit))]

    def new_words_in_chapter(
        self, user_id: int, document_id: int, chapter_index: int, limit: int
    ) -> list[tuple[ChapterWord, Word, Chapter]]:
        """Every word one chapter uses that the user hasn't started on, in the chapter's order."""
        query = (
            self._appearances(user_id, document_id, _NOT_STARTED)
            .where(Chapter.index == chapter_index)
            .order_by(ChapterWord.first_position)
            .limit(limit)
        )
        return [(cw, w, c) for cw, w, c in self._session.execute(query)]

    def chapter_word_ids(self, document_id: int, chapter_index: int) -> set[int]:
        """Every word the chapter uses, including ones first seen in an earlier chapter."""
        return set(
            self._session.scalars(
                select(ChapterWord.word_id)
                .join(Chapter, Chapter.id == ChapterWord.chapter_id)
                .where(ChapterWord.document_id == document_id, Chapter.index == chapter_index)
            )
        )

    def progress_by_chapter(
        self, user_id: int, document_id: int
    ) -> list[tuple[int, UserWord | None]]:
        """(chapter index, the user's progress or None) for every word each chapter uses."""
        progress = and_(UserWord.word_id == ChapterWord.word_id, UserWord.user_id == user_id)
        rows = self._session.execute(
            select(Chapter.index, UserWord)
            .select_from(ChapterWord)
            .join(Chapter, Chapter.id == ChapterWord.chapter_id)
            .outerjoin(UserWord, progress)
            .where(ChapterWord.document_id == document_id)
        )
        return [(index, word) for index, word in rows]

    def unsorted_words(
        self,
        user_id: int,
        document_id: int,
        from_chapter: int,
        limit: int,
        *,
        earlier: bool = False,
    ) -> list[tuple[ChapterWord, Word, Chapter]]:
        """A book's words the user has never sorted, answered or marked; like `new_words`."""
        query = self._frontier(user_id, document_id, from_chapter, _UNSORTED, earlier=earlier)
        return [(cw, w, c) for cw, w, c in self._session.execute(query.limit(limit))]

    def unsorted_count(self, user_id: int, document_id: int) -> int:
        """Unsorted words in the whole book, earlier chapters included."""
        progress = and_(UserWord.word_id == DocumentWord.word_id, UserWord.user_id == user_id)
        return (
            self._session.scalar(
                select(func.count())
                .select_from(DocumentWord)
                .outerjoin(UserWord, progress)
                .where(DocumentWord.document_id == document_id, UserWord.word_id.is_(None))
            )
            or 0
        )

    def _appearances(
        self, user_id: int, document_id: int, condition: ColumnElement[bool]
    ) -> Select[ChapterWord, Word, Chapter]:
        progress = and_(UserWord.word_id == ChapterWord.word_id, UserWord.user_id == user_id)
        return (
            select(ChapterWord, Word, Chapter)
            .join(Word, Word.id == ChapterWord.word_id)
            .join(Chapter, Chapter.id == ChapterWord.chapter_id)
            .outerjoin(UserWord, progress)
            .where(ChapterWord.document_id == document_id, condition)
            .options(selectinload(Word.definitions))
        )

    def _frontier(
        self,
        user_id: int,
        document_id: int,
        from_chapter: int,
        condition: ColumnElement[bool],
        *,
        earlier: bool,
    ) -> Select[ChapterWord, Word, Chapter]:
        """Each word once, at the chapter where the reader meets it next, in reading order.

        Ahead: its first appearance from `from_chapter` on. Earlier: words used only before
        `from_chapter`, at their first appearance.
        """
        other, other_chapter = aliased(ChapterWord), aliased(Chapter)
        same_word = (other.document_id == ChapterWord.document_id) & (
            other.word_id == ChapterWord.word_id
        )
        indexes = (
            select(func.min(other_chapter.index))
            .select_from(other)
            .join(other_chapter, other_chapter.id == other.chapter_id)
        )
        if earlier:
            first = indexes.where(same_word).scalar_subquery()
            later = (
                exists()
                .where(same_word, other_chapter.id == other.chapter_id)
                .where(other_chapter.index >= from_chapter)
            )
            placed = and_(Chapter.index == first, ~later)
        else:
            next_one = indexes.where(same_word, other_chapter.index >= from_chapter)
            placed = Chapter.index == next_one.scalar_subquery()
        return self._appearances(user_id, document_id, and_(condition, placed)).order_by(
            Chapter.index, ChapterWord.first_position
        )

    def in_library(self, user_id: int, word_id: int) -> bool:
        """Whether one of the user's books uses the word."""
        return bool(
            self._session.scalar(
                select(
                    exists()
                    .where(DocumentWord.word_id == word_id)
                    .where(Document.id == DocumentWord.document_id)
                    .where(readable_by(user_id))
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
