"""Books and words: documents, chapters, the global word list and where each word occurs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DocumentFormat, DocumentStatus, PartOfSpeech
from app.db.base import Base
from app.db.types import UTCDateTime, str_enum, utcnow


class Document(Base):
    """A book: one uploaded by a user (private to them), or a public-domain book without an owner
    (a built-in classic, or one added from Project Gutenberg) that anyone can read and nobody can
    delete. A Gutenberg book is extracted once and shared; each reader's shelf lists the ones they
    added (`ShelfBook`)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(  # None: a built-in classic
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str | None] = mapped_column(String(300))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024))  # relative to settings.data_dir
    cover_path: Mapped[str | None] = mapped_column(String(1024))  # a JPEG thumbnail, same base
    format: Mapped[DocumentFormat] = mapped_column(str_enum(DocumentFormat))
    status: Mapped[DocumentStatus] = mapped_column(
        str_enum(DocumentStatus), default=DocumentStatus.UPLOADED
    )
    error: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    gutenberg_id: Mapped[int | None] = mapped_column(unique=True)  # Project Gutenberg's number
    # The public pages' address (/books/<slug>); only for books without an owner.
    slug: Mapped[str | None] = mapped_column(String(120), unique=True)
    # Who asked for a Gutenberg book first (for the daily limit on new books); None for the rest.
    added_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    @property
    def is_classic(self) -> bool:
        return self.owner_user_id is None

    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Chapter.index",
    )


class ShelfBook(Base):
    """A Gutenberg book a user added: it shows on their Books shelf with the built-in classics."""

    __tablename__ = "shelf_books"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("document_id", "index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    index: Mapped[int]  # 0-based reading order
    title: Mapped[str | None] = mapped_column(String(500))

    document: Mapped[Document] = relationship(back_populates="chapters")


class Word(Base):
    """A lemma, shared by all users and books (stored once)."""

    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True)
    lemma: Mapped[str] = mapped_column(String(100), unique=True)
    zipf_frequency: Mapped[float | None]  # wordfreq score; lower = rarer

    definitions: Mapped[list[Definition]] = relationship(
        back_populates="word",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Definition.sense_rank",
    )


class Definition(Base):
    __tablename__ = "definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    pos: Mapped[str] = mapped_column(String(20))  # noun, verb, adjective, adverb
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50))  # e.g. "oewn-2024"
    sense_rank: Mapped[int] = mapped_column(default=0)  # 0 = most common sense

    word: Mapped[Word] = relationship(back_populates="definitions")


class DocumentWord(Base):
    """Where a word first appears in a book; drives the chapter-by-chapter learning order."""

    __tablename__ = "document_words"

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    first_position: Mapped[int]  # token offset inside the chapter
    occurrences: Mapped[int] = mapped_column(default=1)
    context_sentence: Mapped[str | None] = mapped_column(Text)
    context_form: Mapped[str | None] = mapped_column(String(100))  # the word as written there
    pos: Mapped[PartOfSpeech | None] = mapped_column(str_enum(PartOfSpeech))  # most common use
    # The sense_rank of the meaning this sentence uses, when best_sense picked one other than the
    # first for the part of speech; None: no clear winner, so the usual order applies.
    meaning_rank: Mapped[int | None]


class ChapterWord(Base):
    """Where a book uses a word, chapter by chapter: its first use in each chapter it appears in.

    `DocumentWord` keeps the book-level facts (first appearance, count, most common part of
    speech); these rows let a word that reappears later count for those chapters too.
    """

    __tablename__ = "chapter_words"

    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), primary_key=True
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    first_position: Mapped[int]  # token offset inside the chapter
    context_sentence: Mapped[str | None] = mapped_column(Text)
    context_form: Mapped[str | None] = mapped_column(String(100))  # the word as written there
    pos: Mapped[PartOfSpeech | None] = mapped_column(str_enum(PartOfSpeech))  # the book's, as above
    # The sense_rank of the meaning this sentence uses, when best_sense picked one other than the
    # first for the part of speech; None: no clear winner, so the usual order applies.
    meaning_rank: Mapped[int | None]
