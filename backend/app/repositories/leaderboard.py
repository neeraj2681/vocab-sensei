from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import WordStatus
from app.db.models import CurrentReading, Document, QuestClaim, QuizAnswer, User, UserWord


class LeaderboardRepository:
    """Who's on the leaderboard and what others may see of them."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def users(self) -> list[User]:
        return list(
            self._session.scalars(
                select(User).where(User.is_active.is_(True), User.email_verified_at.is_not(None))
            )
        )

    def coins_since(self, since: datetime, day: date) -> dict[int, int]:
        """Coins each user earned since `since` (answers) plus quest rewards claimed for `day`."""
        coins: dict[int, int] = {}
        answers = self._session.execute(
            select(QuizAnswer.user_id, func.sum(QuizAnswer.points))
            .where(QuizAnswer.answered_at >= since)
            .group_by(QuizAnswer.user_id)
        )
        quests = self._session.execute(
            select(QuestClaim.user_id, func.sum(QuestClaim.coins))
            .where(QuestClaim.day == day)
            .group_by(QuestClaim.user_id)
        )
        for user_id, total in [*answers, *quests]:
            coins[user_id] = coins.get(user_id, 0) + int(total or 0)
        return coins

    def words_learned(self, user_id: int) -> int:
        count = self._session.scalar(
            select(func.count())
            .select_from(UserWord)
            .where(UserWord.user_id == user_id, UserWord.status == WordStatus.LEARNED)
        )
        return int(count or 0)

    def reading(self, user_id: int) -> list[tuple[str, str | None]]:
        """Titles and authors of the books the user is reading, their first read first."""
        rows = self._session.execute(
            select(Document.title, Document.author)
            .join(CurrentReading, CurrentReading.document_id == Document.id)
            .where(CurrentReading.user_id == user_id)
            .order_by(CurrentReading.priority, Document.id)
        )
        return [(row[0], row[1]) for row in rows]
