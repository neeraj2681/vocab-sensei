"""Per-user learning state: current reads, word progress, quiz rounds, questions and answers."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String, Text
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
    current_chapter_index: Mapped[int] = mapped_column(default=0)
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
    last_reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class QuizSession(Base):
    """One round of questions."""

    __tablename__ = "quiz_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Question(Base):
    """A generated question, kept so answers can be traced to the generator that made it (§5.6)."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    type: Mapped[QuestionType] = mapped_column(str_enum(QuestionType))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list[Any]] = mapped_column(JSON)
    correct_index: Mapped[int]
    generator: Mapped[str] = mapped_column(String(50))  # e.g. "wordnet-rules", "llm"
    model: Mapped[str | None] = mapped_column(String(100))  # LLM model name, if any
    source_sentence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class QuizAnswer(Base):
    """Append-only answer log; scores can be recomputed from it if the rules change."""

    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    chosen_index: Mapped[int | None]  # None = "I know this" was pressed
    correct: Mapped[bool]
    score_delta: Mapped[int]
    answered_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
