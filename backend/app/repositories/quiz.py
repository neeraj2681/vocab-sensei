from collections.abc import Collection
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.core.enums import WordStatus
from app.db.models import (
    Chapter,
    ChapterWord,
    CurrentReading,
    Definition,
    Document,
    DocumentWord,
    Question,
    QuizAnswer,
    UserWord,
    Word,
)
from app.repositories.documents import readable_by


class QuizRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # Questions and answers

    def pending_question(self, user_id: int) -> Question | None:
        """The user's newest question that hasn't been answered yet."""
        return self._session.scalars(
            select(Question)
            .outerjoin(QuizAnswer, QuizAnswer.question_id == Question.id)
            .where(Question.user_id == user_id, QuizAnswer.id.is_(None))
            .order_by(Question.id.desc())
            .limit(1)
        ).first()

    def question(self, user_id: int, question_id: int) -> Question | None:
        question = self._session.get(Question, question_id)
        return question if question and question.user_id == user_id else None

    def answer_for(self, question_id: int) -> QuizAnswer | None:
        return self._session.scalars(
            select(QuizAnswer).where(QuizAnswer.question_id == question_id)
        ).first()

    def recently_answered_word_ids(self, user_id: int, count: int) -> set[int]:
        """Words of the user's last `count` answers."""
        if count == 0:
            return set()
        return set(
            self._session.scalars(
                select(QuizAnswer.word_id)
                .where(QuizAnswer.user_id == user_id)
                .order_by(QuizAnswer.id.desc())
                .limit(count)
            )
        )

    def add(self, item: Question | QuizAnswer | UserWord) -> None:
        self._session.add(item)

    # Scores

    def total_points(self, user_id: int) -> int:
        total = self._session.scalar(
            select(func.sum(QuizAnswer.points)).where(QuizAnswer.user_id == user_id)
        )
        return int(total or 0)

    def answers(self, user_id: int, since: datetime | None = None) -> list[QuizAnswer]:
        """Real answers ("I know this" excluded), oldest first."""
        query = select(QuizAnswer).where(
            QuizAnswer.user_id == user_id, QuizAnswer.chosen_index.is_not(None)
        )
        if since is not None:
            query = query.where(QuizAnswer.answered_at >= since)
        return list(self._session.scalars(query.order_by(QuizAnswer.id)))

    # Word progress

    def user_word(self, user_id: int, word_id: int) -> UserWord | None:
        return self._session.get(UserWord, (user_id, word_id))

    def words_with_status(
        self,
        user_id: int,
        status: WordStatus,
        exclude: Collection[int],
        *,
        in_current_reads: bool = False,
    ) -> list[UserWord]:
        """Least recently reviewed first; optionally only words a current read of the user uses."""
        query = select(UserWord).where(
            UserWord.user_id == user_id,
            UserWord.status == status,
            UserWord.word_id.not_in(exclude),
        )
        if in_current_reads:
            query = query.where(
                exists()
                .where(DocumentWord.word_id == UserWord.word_id)
                .where(CurrentReading.document_id == DocumentWord.document_id)
                .where(CurrentReading.user_id == user_id)
            )
        return list(
            self._session.scalars(
                query.order_by(UserWord.last_reviewed_at.is_not(None), UserWord.last_reviewed_at)
            )
        )

    def practised_words(self, user_id: int) -> list[tuple[UserWord, Word]]:
        """Words the user has answered at least once and is learning or has learned."""
        rows = self._session.execute(
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .options(selectinload(Word.definitions))
            .where(
                UserWord.user_id == user_id,
                UserWord.status.in_((WordStatus.LEARNING, WordStatus.LEARNED)),
                UserWord.last_reviewed_at.is_not(None),
            )
        )
        return [(row[0], row[1]) for row in rows]

    # Building questions

    def word(self, word_id: int) -> Word | None:
        return self._session.get(Word, word_id)

    def occurrence(self, user_id: int, word_id: int) -> tuple[ChapterWord, Document] | None:
        """Where the user's books use the word: their current reads first, by priority, and in a
        book, the next chapter the reader meets it in (else its first appearance)."""
        current = func.coalesce(CurrentReading.current_chapter_index, 0)
        row = self._session.execute(
            select(ChapterWord, Document)
            .join(Document, Document.id == ChapterWord.document_id)
            .join(Chapter, Chapter.id == ChapterWord.chapter_id)
            .outerjoin(
                CurrentReading,
                (CurrentReading.document_id == Document.id) & (CurrentReading.user_id == user_id),
            )
            .where(readable_by(user_id), ChapterWord.word_id == word_id)
            .order_by(
                CurrentReading.priority.is_(None),
                CurrentReading.priority,
                Document.id,
                Chapter.index < current,  # chapters ahead of the reader first
                Chapter.index,
            )
            .limit(1)
        ).first()
        return (row[0], row[1]) if row else None

    def distractors(
        self, word_id: int, pos: str | None, zipf: float | None, window: float | None, limit: int
    ) -> list[tuple[str, str]]:
        """(lemma, definition) of other words, in random order; narrowed by part of speech and
        difficulty when given. Only each word's first sense of that part of speech is used."""
        query = (
            select(Word.lemma, Definition.text)
            .join(Definition, Definition.word_id == Word.id)
            .where(Word.id != word_id)
        )
        if pos is not None:
            query = query.where(Definition.pos == pos)
        if zipf is not None and window is not None:
            query = query.where(Word.zipf_frequency.between(zipf - window, zipf + window))
        other = aliased(Definition)
        first_sense = (
            select(func.min(other.sense_rank)).where(other.word_id == Word.id).correlate(Word)
        )
        if pos is not None:
            first_sense = first_sense.where(other.pos == pos)
        query = query.where(Definition.sense_rank == first_sense.scalar_subquery())
        rows = self._session.execute(query.order_by(func.random()).limit(limit))
        return [(lemma, text) for lemma, text in rows]
