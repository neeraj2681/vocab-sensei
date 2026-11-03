from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import WordStatus
from app.db.models import CurrentReading, Document, QuestClaim, Question, QuizAnswer, UserWord


class QuestRepository:
    """What daily quests are worked out from, and the rewards already claimed."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def answers_since(self, user_id: int, since: datetime) -> list[tuple[QuizAnswer, int | None]]:
        """Real answers ("I know this" excluded) since `since`, oldest first, with their book."""
        rows = self._session.execute(
            select(QuizAnswer, Question.document_id)
            .join(Question, Question.id == QuizAnswer.question_id)
            .where(
                QuizAnswer.user_id == user_id,
                QuizAnswer.chosen_index.is_not(None),
                QuizAnswer.answered_at >= since,
            )
            .order_by(QuizAnswer.id)
        )
        return [(row[0], row[1]) for row in rows]

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

    def current_books(self, user_id: int) -> list[tuple[int, str]]:
        rows = self._session.execute(
            select(Document.id, Document.title)
            .join(CurrentReading, CurrentReading.document_id == Document.id)
            .where(CurrentReading.user_id == user_id)
            .order_by(CurrentReading.priority, Document.id)
        )
        return [(row[0], row[1]) for row in rows]

    def claimed(self, user_id: int, day: date) -> set[str]:
        return set(
            self._session.scalars(
                select(QuestClaim.quest).where(QuestClaim.user_id == user_id, QuestClaim.day == day)
            )
        )

    def add_claim(self, claim: QuestClaim) -> None:
        self._session.add(claim)
