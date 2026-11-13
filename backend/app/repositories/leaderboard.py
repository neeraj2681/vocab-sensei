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

    def answer_times_since(self, since: datetime) -> dict[int, list[datetime]]:
        """When each user gave real answers ("I know this" excluded) since `since`."""
        times: dict[int, list[datetime]] = {}
        rows = self._session.execute(
            select(QuizAnswer.user_id, QuizAnswer.answered_at).where(
                QuizAnswer.chosen_index.is_not(None), QuizAnswer.answered_at >= since
            )
        )
        for user_id, answered_at in rows:
            times.setdefault(user_id, []).append(answered_at)
        return times

    def first_learned_since(self, since: datetime) -> dict[int, int]:
        """Words each user learned for the first time since `since`."""
        rows = self._session.execute(
            select(UserWord.user_id, func.count())
            .where(UserWord.first_learned_at >= since)
            .group_by(UserWord.user_id)
        )
        return {user_id: int(count) for user_id, count in rows}

    def words_learned(self, user_id: int) -> int:
        count = self._session.scalar(
            select(func.count())
            .select_from(UserWord)
            .where(UserWord.user_id == user_id, UserWord.status == WordStatus.LEARNED)
        )
        return int(count or 0)

    def reading(self, user_id: int) -> list[Document]:
        """The books the user is reading, their first read first."""
        return list(
            self._session.scalars(
                select(Document)
                .join(CurrentReading, CurrentReading.document_id == Document.id)
                .where(CurrentReading.user_id == user_id)
                .order_by(CurrentReading.priority, Document.id)
            )
        )
