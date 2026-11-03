"""Daily quests: today's three, their progress, and claiming their coins (app/quiz/quests.py)."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import QuestClaim, User
from app.quiz.quests import CHEST, CHEST_REWARD, Activity, Book, Quest, daily_quests
from app.repositories.quests import QuestRepository
from app.repositories.quiz import QuizRepository
from app.services.quiz import daily_goal


class QuestError(Exception):
    """Base class for problems the API reports to the user."""


class UnknownQuestError(QuestError):
    pass


class QuestNotDoneError(QuestError):
    pass


class AlreadyClaimedError(QuestError):
    pass


@dataclass(frozen=True)
class QuestStatus:
    quest: Quest
    progress: int
    claimed: bool

    @property
    def done(self) -> bool:
        return self.progress >= self.quest.target


@dataclass(frozen=True)
class DailyQuests:
    day: date
    quests: list[QuestStatus]
    chest_reward: int
    chest_claimed: bool

    @property
    def chest_ready(self) -> bool:
        """All three claimed: the chest can be opened."""
        return all(q.claimed for q in self.quests) and not self.chest_claimed


class QuestService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = QuestRepository(session)

    def today(self, user_id: int, now: datetime, tz: ZoneInfo) -> DailyQuests:
        user = self._user(user_id)
        day = now.astimezone(tz).date()
        goal = daily_goal(user, tz).on(day)
        books = [Book(id, title) for id, title in self._repo.current_books(user_id)]
        quests = daily_quests(user_id, day, goal, books, self._settings.scoring.combo_after)
        activity = self._activity(user_id, day, goal, tz)
        claimed = self._repo.claimed(user_id, day)
        return DailyQuests(
            day=day,
            quests=[QuestStatus(q, q.progress(activity), q.key in claimed) for q in quests],
            chest_reward=CHEST_REWARD,
            chest_claimed=CHEST in claimed,
        )

    def claim(self, user_id: int, key: str, now: datetime, tz: ZoneInfo) -> int:
        """Adds a finished quest's coins (or the chest's, once all three are claimed)."""
        today = self.today(user_id, now, tz)
        if key == CHEST:
            if today.chest_claimed:
                raise AlreadyClaimedError("The chest is already open")
            if not today.chest_ready:
                raise QuestNotDoneError("Claim all three quests first")
            coins = today.chest_reward
        else:
            status = next((q for q in today.quests if q.quest.key == key), None)
            if status is None:
                raise UnknownQuestError("That isn't one of today's quests")
            if status.claimed:
                raise AlreadyClaimedError("Already claimed")
            if not status.done:
                raise QuestNotDoneError("Finish the quest first")
            coins = status.quest.reward
        self._repo.add_claim(QuestClaim(user_id=user_id, day=today.day, quest=key, coins=coins))
        self._session.commit()
        return coins

    def total(self, user_id: int) -> int:
        return QuizRepository(self._session).total_points(user_id)

    def _activity(self, user_id: int, day: date, goal: int, tz: ZoneInfo) -> Activity:
        start = datetime.combine(day, time.min, tz)
        noon = datetime.combine(day, time(12), tz)
        answers = self._repo.answers_since(user_id, start)
        run = best = before_noon = 0
        by_book: Counter[int] = Counter()
        for answer, book_id in answers:
            run = run + 1 if answer.correct else 0
            best = max(best, run)
            if book_id is not None:
                by_book[book_id] += 1
            if answer.answered_at < noon:
                before_noon += 1
        return Activity(
            answers=len(answers),
            right=sum(1 for answer, _ in answers if answer.correct),
            best_run=best,
            learned=self._repo.learned_since(user_id, start),
            by_book=dict(by_book),
            goal_before_noon=before_noon >= goal,
        )

    def _user(self, user_id: int) -> User:
        user = self._session.get(User, user_id)
        if user is None:
            raise LookupError(f"no user {user_id}")
        return user
