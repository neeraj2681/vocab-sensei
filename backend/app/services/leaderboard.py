"""The leaderboard (days this week with the goal met) and the profiles others can open from it."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import Gender
from app.db.models import User
from app.repositories.friends import FriendRepository
from app.repositories.leaderboard import LeaderboardRepository
from app.repositories.quiz import QuizRepository
from app.services.quiz import Day, HistoryPoint, daily_goal, quiz_stats


class ProfileNotFoundError(Exception):
    """No such user, or they keep themselves off the leaderboard."""


@dataclass(frozen=True)
class Row:
    user_id: int
    display_name: str
    gender: Gender
    has_avatar: bool
    goal_days: int  # days this week (so far) with the daily goal met
    new_words: int  # words learned for the first time this week
    me: bool


@dataclass(frozen=True)
class Book:
    id: int
    title: str
    author: str | None
    has_cover: bool


@dataclass(frozen=True)
class PublicProfile:
    """What anyone may see of a user: never their email, settings or uploads."""

    user_id: int
    display_name: str
    gender: Gender
    has_avatar: bool
    me: bool
    coins: int  # lifetime
    coins_today: int
    streak: int
    words_learned: int
    answers: int
    right: int
    week: list[Day]
    history: list[HistoryPoint]
    books: list[Book]  # empty when they keep them private (and it isn't you looking)
    books_hidden: bool


class LeaderboardService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = LeaderboardRepository(session)

    def today(
        self, viewer_id: int, now: datetime, tz: ZoneInfo, friends_only: bool = False
    ) -> list[Row]:
        """Everyone shown on the leaderboard (or just you and your friends) for the week so far
        (Monday to now, in the viewer's time zone): most days with the daily goal met first, then
        most words learned for the first time, then name."""
        today = now.astimezone(tz).date()
        monday = today - timedelta(days=today.weekday())
        since = datetime.combine(monday, time.min, tz)
        answer_times = self._repo.answer_times_since(since)
        new_words = self._repo.first_learned_since(since)
        friends = FriendRepository(self._session).friend_ids(viewer_id)
        rows = []
        for user in self._repo.users():
            if not (
                user.id == viewer_id
                or (user.id in friends if friends_only else user.show_on_leaderboard)
            ):
                continue
            per_day = Counter(t.astimezone(tz).date() for t in answer_times.get(user.id, []))
            goal = daily_goal(user, tz)
            days = (monday + timedelta(days=n) for n in range((today - monday).days + 1))
            rows.append(
                Row(
                    user_id=user.id,
                    display_name=user.display_name,
                    gender=user.gender,
                    has_avatar=user.has_avatar,
                    goal_days=sum(1 for day in days if per_day[day] >= goal.on(day)),
                    new_words=new_words.get(user.id, 0),
                    me=user.id == viewer_id,
                )
            )
        return sorted(
            rows, key=lambda r: (-r.goal_days, -r.new_words, r.display_name.lower(), r.user_id)
        )

    def profile(self, viewer_id: int, user_id: int, now: datetime, tz: ZoneInfo) -> PublicProfile:
        user = self._visible(viewer_id, user_id)
        quiz = QuizRepository(self._session)
        stats = quiz_stats(quiz, user, now, tz)
        day = now.astimezone(tz).date()
        coins_today = self._repo.coins_since(datetime.combine(day, time.min, tz), day)
        history: list[HistoryPoint] = []
        total = 0
        for number, answer in enumerate(quiz.answers(user.id), start=1):
            total += answer.points
            history.append(HistoryPoint(number, total, answer.correct, answer.answered_at))
        me = user.id == viewer_id
        hidden = not me and not user.show_books
        books = (
            []
            if hidden
            else [
                Book(d.id, d.title, d.author, d.cover_path is not None and (me or d.is_classic))
                for d in self._repo.reading(user.id)
            ]
        )
        return PublicProfile(
            user_id=user.id,
            display_name=user.display_name,
            gender=user.gender,
            has_avatar=user.has_avatar,
            me=user.id == viewer_id,
            coins=stats.total,
            coins_today=coins_today.get(user.id, 0),
            streak=stats.streak,
            words_learned=self._repo.words_learned(user.id),
            answers=len(history),
            right=sum(1 for point in history if point.correct),
            week=stats.week,
            history=history,
            books=books,
            books_hidden=hidden,
        )

    def avatar(self, viewer_id: int, user_id: int) -> Path | None:
        user = self._visible(viewer_id, user_id)
        if not user.avatar_path:
            return None
        path = self._settings.data_dir / user.avatar_path
        return path if path.is_file() else None

    def book_cover(self, viewer_id: int, user_id: int, document_id: int) -> Path | None:
        """The cover of a book on a profile: one they're reading, if they share their books. Others
        see covers of public-domain classics only, never of someone's own uploads (cover art
        belongs to its publisher)."""
        user = self._visible(viewer_id, user_id)
        if user.id != viewer_id and not user.show_books:
            raise ProfileNotFoundError("No such book")
        book = next((d for d in self._repo.reading(user.id) if d.id == document_id), None)
        if book is None:
            raise ProfileNotFoundError("No such book")
        if not book.cover_path or (user.id != viewer_id and not book.is_classic):
            return None
        path = self._settings.data_dir / book.cover_path
        return path if path.is_file() else None

    def _visible(self, viewer_id: int, user_id: int) -> User:
        user = self._session.get(User, user_id)
        if user is None or not user.is_active or user.email_verified_at is None:
            raise ProfileNotFoundError("No such profile")
        hidden = user.id != viewer_id and not user.show_on_leaderboard
        if hidden and user.id not in FriendRepository(self._session).friend_ids(viewer_id):
            raise ProfileNotFoundError("No such profile")  # friends still see it
        return user
