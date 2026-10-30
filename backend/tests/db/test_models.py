from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.core.enums import DocumentFormat, QuestionType, WordStatus
from app.db.models import (
    AuthSession,
    Chapter,
    CurrentReading,
    Document,
    DocumentWord,
    Question,
    QuizAnswer,
    User,
    UserWord,
    Word,
)

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


def add_user(session: Session, email: str = "reader@example.com") -> User:
    user = User(email=email, password_hash="argon2-hash", display_name="Reader")
    session.add(user)
    session.flush()
    return user


def add_book(session: Session, owner: User) -> Document:
    book = Document(
        owner_user_id=owner.id,
        title="Moby-Dick",
        original_filename="moby.epub",
        file_path="uploads/1/moby.epub",
        format=DocumentFormat.EPUB,
        chapters=[Chapter(index=0, title="Loomings"), Chapter(index=1, title="The Carpet-Bag")],
    )
    session.add(book)
    session.flush()
    return book


def test_email_is_unique(session: Session) -> None:
    add_user(session)

    with pytest.raises(IntegrityError):
        add_user(session)


def test_datetimes_come_back_timezone_aware(session: Session) -> None:
    user = add_user(session)
    session.add(AuthSession(user_id=user.id, token_hash="a" * 64, expires_at=NOW))
    session.commit()
    session.expire_all()

    stored = session.scalars(select(AuthSession)).one()

    assert stored.expires_at == NOW
    assert stored.expires_at.tzinfo is not None


def test_naive_datetimes_are_rejected(session: Session) -> None:
    user = add_user(session)
    session.add(AuthSession(user_id=user.id, token_hash="b" * 64, expires_at=datetime(2026, 1, 1)))

    with pytest.raises(StatementError, match="naive datetime"):
        session.flush()


def test_enums_are_stored_as_their_values(session: Session) -> None:
    add_book(session, add_user(session))

    raw = session.execute(text("SELECT format, status FROM documents")).one()

    assert tuple(raw) == ("epub", "uploaded")


def test_deleting_a_user_deletes_their_data(session: Session) -> None:
    user = add_user(session)
    book = add_book(session, user)
    word = Word(lemma="lugubrious", zipf_frequency=1.9)
    session.add(word)
    session.flush()
    question = Question(
        user_id=user.id,
        word_id=word.id,
        type=QuestionType.DEFINITION_MCQ,
        prompt="lugubrious",
        options=["mournful", "cheerful", "slippery", "tiny"],
        correct_index=0,
        generator="wordnet-rules",
    )
    session.add_all(
        [
            AuthSession(user_id=user.id, token_hash="c" * 64, expires_at=NOW + timedelta(days=30)),
            DocumentWord(
                document_id=book.id,
                word_id=word.id,
                chapter_id=book.chapters[0].id,
                first_position=42,
            ),
            CurrentReading(user_id=user.id, document_id=book.id),
            UserWord(user_id=user.id, word_id=word.id, score=5, status=WordStatus.LEARNING),
            question,
        ]
    )
    session.flush()
    session.add(
        QuizAnswer(
            user_id=user.id,
            word_id=word.id,
            question_id=question.id,
            chosen_index=0,
            correct=True,
            score_delta=5,
        )
    )
    session.commit()

    session.execute(text("DELETE FROM users"))  # database-level cascade, as a raw delete would do
    session.commit()

    for table in ["auth_sessions", "documents", "chapters", "document_words", "current_readings"]:
        assert session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() == 0, table
    for table in ["user_words", "questions", "quiz_answers"]:
        assert session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() == 0, table
    # Shared data stays: words belong to no single user.
    assert session.scalars(select(Word)).one().lemma == "lugubrious"


def test_chapter_index_unique_per_document(session: Session) -> None:
    book = add_book(session, add_user(session))
    session.add(Chapter(document_id=book.id, index=0))

    with pytest.raises(IntegrityError):
        session.flush()
