"""Weekly and monthly recaps: what a finished week (Monday to Sunday) or month added up to."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models import User
from app.repositories.quiz import QuizRepository
from app.repositories.recaps import RecapRepository
from app.services.quiz import daily_goal, quiz_stats


class Period(StrEnum):
    WEEK = "week"
    MONTH = "month"


@dataclass(frozen=True)
class Recap:
    period: Period
    first: date
    last: date  # inclusive
    words_learned: int
    coins: int  # earned: answers and quest rewards (spending isn't counted)
    answers: int
    right: int
    goal_days: int  # days the daily goal was met
    days: int  # days in the period
    best_day: tuple[date, int] | None  # the day with the most coins
    toughest_word: tuple[str, int] | None  # the word answered wrongly most often
    favourite_book: tuple[str, int] | None  # the book most answered from
    streak: int  # the day streak now


def weeks_before(today: date, count: int) -> list[tuple[date, date]]:
    """The last `count` finished weeks (Monday to Sunday), newest first."""
    this_monday = today - timedelta(days=today.weekday())
    return [
        (this_monday - timedelta(weeks=n), this_monday - timedelta(weeks=n) + timedelta(days=6))
        for n in range(1, count + 1)
    ]


def months_before(today: date, count: int) -> list[tuple[date, date]]:
    """The last `count` finished calendar months, newest first."""
    periods = []
    first = today.replace(day=1)
    for _ in range(count):
        last = first - timedelta(days=1)
        first = last.replace(day=1)
        periods.append((first, last))
    return periods


class RecapService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = RecapRepository(session)

    def recent(self, user_id: int, now: datetime, tz: ZoneInfo) -> tuple[list[Recap], list[Recap]]:
        """The last 4 weeks and last 3 months, newest first."""
        today = now.astimezone(tz).date()
        weeks = [self.recap(user_id, Period.WEEK, a, b, now, tz) for a, b in weeks_before(today, 4)]
        months = [
            self.recap(user_id, Period.MONTH, a, b, now, tz) for a, b in months_before(today, 3)
        ]
        return weeks, months

    def recap(
        self, user_id: int, period: Period, first: date, last: date, now: datetime, tz: ZoneInfo
    ) -> Recap:
        user = self._session.get(User, user_id)
        if user is None:
            raise LookupError(f"no user {user_id}")
        start = datetime.combine(first, time.min, tz)
        end = datetime.combine(last + timedelta(days=1), time.min, tz)
        answers = self._repo.answers(user_id, start, end)
        per_day: Counter[date] = Counter()
        coins: Counter[date] = Counter(self._repo.quest_coins(user_id, first, last))
        wrong: Counter[str] = Counter()
        books: Counter[str] = Counter()
        for answer, lemma, book in answers:
            day = answer.answered_at.astimezone(tz).date()
            per_day[day] += 1
            coins[day] += answer.points
            if not answer.correct:
                wrong[lemma] += 1
            if book:
                books[book] += 1
        goal = daily_goal(user, tz)
        days = (last - first).days + 1
        best = max(coins.items(), key=lambda kv: (kv[1], kv[0]), default=None)
        return Recap(
            period=period,
            first=first,
            last=last,
            words_learned=self._repo.learned(user_id, start, end),
            coins=sum(coins.values()),
            answers=len(answers),
            right=sum(1 for answer, _, _ in answers if answer.correct),
            goal_days=sum(
                1
                for n in range(days)
                if per_day[first + timedelta(days=n)] >= goal.on(first + timedelta(days=n))
            ),
            days=days,
            best_day=best if best and best[1] > 0 else None,
            toughest_word=wrong.most_common(1)[0] if wrong else None,
            favourite_book=books.most_common(1)[0] if books else None,
            streak=quiz_stats(QuizRepository(self._session), user, now, tz).streak,
        )


def recap_text(recap: Recap) -> str:
    """The recap as plain text, for email."""
    span = "week" if recap.period is Period.WEEK else "month"
    accuracy = f"{round(100 * recap.right / recap.answers)}%" if recap.answers else "-"
    lines = [
        f"Your {span} ({recap.first:%d %b} to {recap.last:%d %b}):",
        f"- Words learned: {recap.words_learned}",
        f"- Coins earned: {recap.coins:,}",
        f"- Questions answered: {recap.answers:,} ({accuracy} right)",
        f"- Daily goal met on {recap.goal_days} of {recap.days} days",
        f"- Day streak now: {recap.streak}",
    ]
    if recap.best_day:
        lines.append(f"- Best day: {recap.best_day[0]:%A %d %b} (+{recap.best_day[1]:,} coins)")
    if recap.toughest_word:
        lines.append(f"- Toughest word: {recap.toughest_word[0]}")
    if recap.favourite_book:
        lines.append(f"- Favourite book: {recap.favourite_book[0]}")
    return "\n".join(lines)
