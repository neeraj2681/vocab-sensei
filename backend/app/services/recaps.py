"""Weekly and monthly recaps: what a week (Monday to Sunday) or a month added up to."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models import User
from app.quiz.selection import streak
from app.repositories.quiz import QuizRepository
from app.repositories.recaps import RecapRepository
from app.services.quiz import daily_goal

_STREAK_DAYS = 400  # streaks are counted over at most this many days


class Period(StrEnum):
    WEEK = "week"
    MONTH = "month"


@dataclass(frozen=True)
class Recap:
    period: Period
    first: date  # the period's first day, or the day the user joined if later
    last: date  # inclusive
    words_learned: int
    coins: int  # earned: answers and quest rewards (spending isn't counted)
    answers: int
    right: int
    goal_days: int  # days the daily goal was met (or a streak freeze covered)
    days: int  # days so far: from `first` to `last` or yesterday (today too once its goal is met)
    best_day: tuple[date, int] | None  # the day with the most coins
    toughest_word: tuple[str, int] | None  # the word answered wrongly most often
    favourite_book: tuple[str, int] | None  # the book most answered from
    streak: int  # the day streak at the period's end (now, for the current period)
    current: bool  # the period is still running


def weeks_before(today: date, count: int) -> list[tuple[date, date]]:
    """The last `count` finished weeks (Monday to Sunday), newest first."""
    this_monday = today - timedelta(days=today.weekday())
    return [
        (this_monday - timedelta(weeks=n), this_monday - timedelta(weeks=n) + timedelta(days=6))
        for n in range(1, count + 1)
    ]


def this_week(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)


def this_month(today: date) -> tuple[date, date]:
    first = today.replace(day=1)
    return first, (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)


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
        """This week and the last 4 finished ones, this month and the last 3, newest first.

        Periods that ended before the user joined are left out.
        """
        today = now.astimezone(tz).date()
        weeks = [this_week(today), *weeks_before(today, 4)]
        months = [this_month(today), *months_before(today, 3)]
        joined = self.joined(user_id, tz)

        def recaps(period: Period, spans: list[tuple[date, date]]) -> list[Recap]:
            return [
                self.recap(user_id, period, first, last, now, tz)
                for first, last in spans
                if last >= joined
            ]

        return recaps(Period.WEEK, weeks), recaps(Period.MONTH, months)

    def joined(self, user_id: int, tz: ZoneInfo) -> date:
        """The day the user signed up (or first answered, for accounts restored from a backup)."""
        user = self._session.get(User, user_id)
        if user is None:
            raise LookupError(f"no user {user_id}")
        first = self._repo.first_answer_at(user_id)
        signed_up = user.created_at if first is None else min(user.created_at, first)
        return signed_up.astimezone(tz).date()

    def recap(
        self, user_id: int, period: Period, first: date, last: date, now: datetime, tz: ZoneInfo
    ) -> Recap:
        user = self._session.get(User, user_id)
        if user is None:
            raise LookupError(f"no user {user_id}")
        today = now.astimezone(tz).date()
        first = max(first, self.joined(user_id, tz))
        start = datetime.combine(first, time.min, tz)
        end = datetime.combine(last + timedelta(days=1), time.min, tz)
        answers = self._repo.answers(user_id, start, end)
        coins: Counter[date] = Counter(self._repo.quest_coins(user_id, first, last))
        wrong: Counter[str] = Counter()
        books: Counter[str] = Counter()
        for answer, lemma, book in answers:
            day = answer.answered_at.astimezone(tz).date()
            coins[day] += answer.points
            if not answer.correct:
                wrong[lemma] += 1
            if book:
                books[book] += 1
        quiz = QuizRepository(self._session)
        end_day = min(last, today)
        since = datetime.combine(end_day - timedelta(days=_STREAK_DAYS), time.min, tz)
        per_day: Counter[date] = Counter(
            a.answered_at.astimezone(tz).date() for a in quiz.answers(user_id, since)
        )
        goal = daily_goal(user, tz)
        frozen = quiz.frozen_days(user_id)

        def met(day: date) -> bool:
            return per_day[day] >= goal.on(day) or day in frozen

        # Today counts once its goal is met, so the morning doesn't read as a missed day.
        counted = [
            first + timedelta(days=n)
            for n in range((end_day - first).days + 1)
            if first + timedelta(days=n) < today or met(first + timedelta(days=n))
        ]
        upto = {day: n for day, n in per_day.items() if day <= end_day}
        best = max(coins.items(), key=lambda kv: (kv[1], kv[0]), default=None)
        return Recap(
            period=period,
            first=first,
            last=last,
            words_learned=self._repo.learned(user_id, start, end),
            coins=sum(coins.values()),
            answers=len(answers),
            right=sum(1 for answer, _, _ in answers if answer.correct),
            goal_days=sum(1 for day in counted if met(day)),
            days=len(counted),
            best_day=best if best and best[1] > 0 else None,
            toughest_word=wrong.most_common(1)[0] if wrong else None,
            favourite_book=books.most_common(1)[0] if books else None,
            # A finished period's streak ends on its last day: a miss then means 0.
            streak=streak(upto, end_day, goal, frozen) if last >= today or met(end_day) else 0,
            current=last >= today,
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
        f"- Day streak at the end of the {span}: {recap.streak}",
    ]
    if recap.best_day:
        lines.append(f"- Best day: {recap.best_day[0]:%A %d %b} (+{recap.best_day[1]:,} coins)")
    if recap.toughest_word:
        lines.append(f"- Toughest word: {recap.toughest_word[0]}")
    if recap.favourite_book:
        lines.append(f"- Favourite book: {recap.favourite_book[0]}")
    return "\n".join(lines)
