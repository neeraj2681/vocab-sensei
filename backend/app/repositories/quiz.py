from collections.abc import Collection
from datetime import date, datetime

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.core.enums import WordStatus
from app.db.models import (
    Chapter,
    ChapterWord,
    CurrentReading,
    Definition,
    Document,
    DocumentWord,
    QuestClaim,
    Question,
    QuizAnswer,
    ShopPurchase,
    UserWord,
    Word,
)
from app.repositories.documents import readable_by


class QuizRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # Questions and answers

    def unanswered(self, user_id: int, limit: int = 2) -> list[Question]:
        """The user's questions not answered yet, oldest first: the one on screen, then the one
        kept ready after it."""
        return list(
            self._session.scalars(
                select(Question)
                .outerjoin(QuizAnswer, QuizAnswer.question_id == Question.id)
                .where(Question.user_id == user_id, QuizAnswer.id.is_(None))
                .order_by(Question.id)
                .limit(limit)
            )
        )

    def question(self, user_id: int, question_id: int) -> Question | None:
        question = self._session.get(Question, question_id)
        return question if question and question.user_id == user_id else None

    def answer_for(self, question_id: int) -> QuizAnswer | None:
        return self._session.scalars(
            select(QuizAnswer).where(QuizAnswer.question_id == question_id)
        ).first()

    def recent_answers(self, user_id: int, count: int) -> list[tuple[int, bool]]:
        """(word, answered right) for the user's last `count` answers, newest first. "I know this"
        counts as right."""
        if count == 0:
            return []
        rows = self._session.execute(
            select(QuizAnswer.word_id, QuizAnswer.correct, QuizAnswer.chosen_index)
            .where(QuizAnswer.user_id == user_id)
            .order_by(QuizAnswer.id.desc())
            .limit(count)
        )
        return [(word_id, correct or chosen is None) for word_id, correct, chosen in rows]

    def add(self, item: Question | QuizAnswer | UserWord) -> None:
        self._session.add(item)

    # Scores

    def total_points(self, user_id: int) -> int:
        """Coins to spend: every answer's points plus claimed quest rewards, minus Shop buys."""
        answers = self._session.scalar(
            select(func.sum(QuizAnswer.points)).where(QuizAnswer.user_id == user_id)
        )
        quests = self._session.scalar(
            select(func.sum(QuestClaim.coins)).where(QuestClaim.user_id == user_id)
        )
        spent = self._session.scalar(
            select(func.sum(ShopPurchase.coins)).where(ShopPurchase.user_id == user_id)
        )
        return int(answers or 0) + int(quests or 0) - int(spent or 0)

    def frozen_days(self, user_id: int) -> set[date]:
        """Missed days a streak freeze covered."""
        return set(
            self._session.scalars(
                select(ShopPurchase.used_for_day).where(
                    ShopPurchase.user_id == user_id, ShopPurchase.used_for_day.is_not(None)
                )
            )
        )

    def unused(self, user_id: int, item: str) -> list[ShopPurchase]:
        """Bought and still in the inventory, oldest first."""
        return list(
            self._session.scalars(
                select(ShopPurchase)
                .where(
                    ShopPurchase.user_id == user_id,
                    ShopPurchase.item == item,
                    ShopPurchase.used_at.is_(None),
                )
                .order_by(ShopPurchase.bought_at, ShopPurchase.id)
            )
        )

    def quest_coins_by_day(self, user_id: int, since: date) -> dict[date, int]:
        rows = self._session.execute(
            select(QuestClaim.day, func.sum(QuestClaim.coins))
            .where(QuestClaim.user_id == user_id, QuestClaim.day >= since)
            .group_by(QuestClaim.day)
        )
        return {day: int(coins) for day, coins in rows}

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

    def learned_since(self, user_id: int, since: datetime) -> int:
        count = self._session.scalar(
            select(func.count())
            .select_from(UserWord)
            .where(
                UserWord.user_id == user_id,
                UserWord.status == WordStatus.LEARNED,
                UserWord.learned_at >= since,
            )
        )
        return int(count or 0)

    def learning_by_book(self, user_id: int) -> list[tuple[int, UserWord]]:
        """(book id, word) for every word in progress that a current read uses, book by book in
        priority order, each book's closest to learned first. A word in two books comes twice."""
        rows = self._session.execute(
            select(CurrentReading.document_id, UserWord)
            .join(DocumentWord, DocumentWord.word_id == UserWord.word_id)
            .join(
                CurrentReading,
                (CurrentReading.document_id == DocumentWord.document_id)
                & (CurrentReading.user_id == UserWord.user_id),
            )
            .where(UserWord.user_id == user_id, UserWord.status == WordStatus.LEARNING)
            .order_by(CurrentReading.priority, UserWord.score.desc(), UserWord.word_id)
        )
        return [(document_id, user_word) for document_id, user_word in rows]

    def practised_words(self, user_id: int) -> list[tuple[UserWord, Word]]:
        """Words the user is learning or has learned (answered at least once), and every word they
        marked as already known (in the quiz or when sorting a chapter)."""
        rows = self._session.execute(
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .options(selectinload(Word.definitions))
            .where(
                UserWord.user_id == user_id,
                or_(
                    and_(
                        UserWord.status.in_((WordStatus.LEARNING, WordStatus.LEARNED)),
                        UserWord.last_reviewed_at.is_not(None),
                    ),
                    UserWord.status == WordStatus.KNOWN,
                ),
            )
        )
        return [(row[0], row[1]) for row in rows]

    # Building questions

    def word(self, word_id: int) -> Word | None:
        return self._session.get(Word, word_id)

    def word_by_lemma(self, lemma: str) -> Word | None:
        return self._session.scalars(select(Word).where(Word.lemma == lemma)).one_or_none()

    def current_read_titles(self, user_id: int) -> dict[int, list[str]]:
        """For each word in the user's current reads, those books' titles in priority order."""
        rows = self._session.execute(
            select(DocumentWord.word_id, Document.title)
            .join(Document, Document.id == DocumentWord.document_id)
            .join(
                CurrentReading,
                (CurrentReading.document_id == Document.id) & (CurrentReading.user_id == user_id),
            )
            .order_by(CurrentReading.priority)
        )
        titles: dict[int, list[str]] = {}
        for word_id, title in rows:
            titles.setdefault(word_id, []).append(title)
        return titles

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

    def word_for_definition(self, text: str, not_word_id: int) -> str | None:
        """The lemma of another word that has `text` as a definition, if any."""
        return self._session.scalar(
            select(Word.lemma)
            .join(Definition, Definition.word_id == Word.id)
            .where(Definition.text == text, Word.id != not_word_id)
            .order_by(Definition.sense_rank, Word.id)
            .limit(1)
        )

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
