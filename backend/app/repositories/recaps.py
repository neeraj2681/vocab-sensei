from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import WordStatus
from app.db.models import Document, QuestClaim, Question, QuizAnswer, UserWord, Word


class RecapRepository:
    """What a week's or a month's recap is made of."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def answers(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[tuple[QuizAnswer, str, str | None]]:
        """Real answers in [start, end), oldest first, with the word and the book's title."""
        rows = self._session.execute(
            select(QuizAnswer, Word.lemma, Document.title)
            .join(Word, Word.id == QuizAnswer.word_id)
            .join(Question, Question.id == QuizAnswer.question_id)
            .outerjoin(Document, Document.id == Question.document_id)
            .where(
                QuizAnswer.user_id == user_id,
                QuizAnswer.chosen_index.is_not(None),
                QuizAnswer.answered_at >= start,
                QuizAnswer.answered_at < end,
            )
            .order_by(QuizAnswer.id)
        )
        return [(row[0], row[1], row[2]) for row in rows]

    def learned(self, user_id: int, start: datetime, end: datetime) -> int:
        count = self._session.scalar(
            select(func.count())
            .select_from(UserWord)
            .where(
                UserWord.user_id == user_id,
                UserWord.status == WordStatus.LEARNED,
                UserWord.learned_at >= start,
                UserWord.learned_at < end,
            )
        )
        return int(count or 0)

    def first_answer_at(self, user_id: int) -> datetime | None:
        return self._session.scalar(
            select(func.min(QuizAnswer.answered_at)).where(QuizAnswer.user_id == user_id)
        )

    def quest_coins(self, user_id: int, first: date, last: date) -> dict[date, int]:
        rows = self._session.execute(
            select(QuestClaim.day, func.sum(QuestClaim.coins))
            .where(QuestClaim.user_id == user_id, QuestClaim.day >= first, QuestClaim.day <= last)
            .group_by(QuestClaim.day)
        )
        return {day: int(coins) for day, coins in rows}
