"""Per-user learning state: current reads, word progress, quiz rounds, questions and answers."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Date, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import QuestionType, WordStatus
from app.db.base import Base
from app.db.types import UTCDateTime, str_enum, utcnow

if TYPE_CHECKING:
    from app.db.models.library import Document


class CurrentReading(Base):
    __tablename__ = "current_readings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    current_chapter_index: Mapped[int] = mapped_column(default=0)  # the first chapter being read
    # The chapters being read (their words come first); empty: the current one and the next two.
    chapters: Mapped[list[int]] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    priority: Mapped[int] = mapped_column(default=0)  # 0 = highest
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    document: Mapped[Document] = relationship(lazy="joined")


class UserWord(Base):
    """A user's progress on one word. Columns mirror app.scoring.rules.WordProgress."""

    __tablename__ = "user_words"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[int] = mapped_column(default=0)
    status: Mapped[WordStatus] = mapped_column(str_enum(WordStatus), default=WordStatus.NEW)
    learned_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Learned at some point and not dropped to 50 since: misses cost more (see miss_penalty).
    was_learned: Mapped[bool] = mapped_column(default=False, server_default=sa_false())
    # Weeks between reviews once learned (see app.scoring.rules.WordProgress.interval_weeks).
    interval_weeks: Mapped[int] = mapped_column(default=1, server_default="1")
    last_reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Question(Base):
    """A question asked to a user; answers can be traced to the generator that made it (§5.6).

    The quiz never ends: the user's newest question without an answer is the one on screen.
    """

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int | None] = mapped_column(  # the book the word was taken from
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    type: Mapped[QuestionType] = mapped_column(str_enum(QuestionType))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list[Any]] = mapped_column(JSON)
    correct_index: Mapped[int]
    generator: Mapped[str] = mapped_column(String(50))  # e.g. "wordnet-rules", "llm"
    model: Mapped[str | None] = mapped_column(String(100))  # LLM model name, if any
    source_sentence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)  # when it was asked


class QuizAnswer(Base):
    """Append-only answer log; scores can be recomputed from it if the rules change."""

    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        unique=True,  # one answer per question
    )
    chosen_index: Mapped[int | None]  # None = "I know this" was pressed
    correct: Mapped[bool]
    score_delta: Mapped[int]  # change in the word's score
    points: Mapped[int] = mapped_column(server_default="0")  # change in the lifetime score
    answered_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class QuestClaim(Base):
    """A daily quest's coins, claimed (the quests themselves are worked out, not stored)."""

    __tablename__ = "quest_claims"
    __table_args__ = (UniqueConstraint("user_id", "day", "quest"),)  # each reward once

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)  # the quest's day, in the user's time zone
    quest: Mapped[str] = mapped_column(String(40))  # e.g. "answer-20", or "chest"
    coins: Mapped[int]
    claimed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ShopPurchase(Base):
    """Something bought in the Shop. It sits in the inventory until used: a streak freeze covers
    `used_for_day`, double coins start running at `used_at`."""

    __tablename__ = "shop_purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item: Mapped[str] = mapped_column(String(40))  # app.quiz.shop.Item
    coins: Mapped[int]  # what it cost
    bought_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    used_for_day: Mapped[date | None] = mapped_column(Date)  # the missed day a freeze covered
