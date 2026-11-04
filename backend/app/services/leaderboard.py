"""The leaderboard (coins earned today) and the profiles others can open from it."""

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import Gender
from app.db.models import User
from app.repositories.leaderboard import LeaderboardRepository
from app.repositories.quiz import QuizRepository
from app.services.quiz import Day, HistoryPoint, quiz_stats


class ProfileNotFoundError(Exception):
    """No such user, or they keep themselves off the leaderboard."""


@dataclass(frozen=True)
class Row:
    user_id: int
    display_name: str
    gender: Gender
    has_avatar: bool
    coins_today: int
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

    def today(self, viewer_id: int, now: datetime, tz: ZoneInfo) -> list[Row]:
        """Everyone shown on the leaderboard, most coins today first (ties by name)."""
        day = now.astimezone(tz).date()
        coins = self._repo.coins_since(datetime.combine(day, time.min, tz), day)
        rows = [
            Row(
                user_id=user.id,
                display_name=user.display_name,
                gender=user.gender,
                has_avatar=user.has_avatar,
                coins_today=coins.get(user.id, 0),
                me=user.id == viewer_id,
            )
            for user in self._repo.users()
            if user.show_on_leaderboard or user.id == viewer_id
        ]
        return sorted(rows, key=lambda r: (-r.coins_today, r.display_name.lower(), r.user_id))

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
                Book(d.id, d.title, d.author, d.cover_path is not None)
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
        """The cover of a book on a profile: one they're reading, if they share their books."""
        user = self._visible(viewer_id, user_id)
        if user.id != viewer_id and not user.show_books:
            raise ProfileNotFoundError("No such book")
        book = next((d for d in self._repo.reading(user.id) if d.id == document_id), None)
        if book is None:
            raise ProfileNotFoundError("No such book")
        if not book.cover_path:
            return None
        path = self._settings.data_dir / book.cover_path
        return path if path.is_file() else None

    def _visible(self, viewer_id: int, user_id: int) -> User:
        user = self._session.get(User, user_id)
        if user is None or not user.is_active or user.email_verified_at is None:
            raise ProfileNotFoundError("No such profile")
        if user.id != viewer_id and not user.show_on_leaderboard:
            raise ProfileNotFoundError("No such profile")
        return user
