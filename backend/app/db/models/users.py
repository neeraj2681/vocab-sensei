"""Accounts and login: users, browser sessions, email verification / password reset tokens."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy import false as sa_false
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EmailTokenPurpose, Gender
from app.db.base import Base
from app.db.types import UTCDateTime, str_enum, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # stored lower-cased
    password_hash: Mapped[str] = mapped_column(String(255))  # Argon2; never the password itself
    display_name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)
    daily_goal: Mapped[int] = mapped_column(default=20, server_default="20")  # answers a day
    # Right answers in a row (Ninja Mode); kept between sessions until a wrong answer or the
    # player stops after a session.
    combo: Mapped[int] = mapped_column(default=0, server_default="0")
    # Listed on the leaderboard, with a profile others can open: off until turned on in Settings.
    show_on_leaderboard: Mapped[bool] = mapped_column(default=False, server_default=sa_false())
    show_books: Mapped[bool] = mapped_column(default=True, server_default=sa_true())  # on profile
    double_coins_until: Mapped[datetime | None] = mapped_column(UTCDateTime)  # from the Shop
    # "Can't speak right now": no "say this word" questions until then.
    speaking_paused_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    freezes_checked_through: Mapped[date | None] = mapped_column(Date)  # missed days looked at
    onboarded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # finished the tour
    name_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # one change allowed
    gender: Mapped[Gender] = mapped_column(
        str_enum(Gender), default=Gender.UNSPECIFIED, server_default=Gender.UNSPECIFIED.value
    )
    avatar_path: Mapped[str | None] = mapped_column(String(1024))  # relative to data_dir
    pending_email: Mapped[str | None] = mapped_column(String(320))  # until its link is opened
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    @property
    def has_avatar(self) -> bool:
        return self.avatar_path is not None

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    # Every goal the user has had and when it started, oldest first; none until the first change.
    goal_changes: Mapped[list[GoalChange]] = relationship(
        order_by=lambda: (GoalChange.since, GoalChange.id),
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GoalChange(Base):
    """The daily goal from `since` on, so past days keep being judged by the goal they had."""

    __tablename__ = "goal_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    goal: Mapped[int]
    since: Mapped[datetime] = mapped_column(UTCDateTime)


class AuthSession(Base):
    """A logged-in browser. The cookie holds a random token; only its SHA-256 hash is stored."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)

    user: Mapped[User] = relationship(back_populates="sessions")


class EmailToken(Base):
    """Single-use token sent by email (verify address, reset password). Only its hash is stored."""

    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[EmailTokenPurpose] = mapped_column(str_enum(EmailTokenPurpose))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Friendship(Base):
    """A friend request (`accepted_at` empty) or a friendship (both ways, whoever asked)."""

    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("requester_id", "addressee_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    addressee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
