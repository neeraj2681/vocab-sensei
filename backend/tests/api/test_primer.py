from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import WordStatus
from app.db.models import Document, UserWord, Word
from app.db.types import utcnow
from tests.api.test_quiz import LEMMAS, answer, question, reader
from tests.conftest import log_in, make_user


def set_progress(
    session: Session, lemma: str, status: WordStatus, score: int, learned_at: datetime | None = None
) -> None:
    word = session.scalars(select(Word).where(Word.lemma == lemma)).one()
    session.add(
        UserWord(
            user_id=reader(session).id,
            word_id=word.id,
            status=status,
            score=score,
            learned_at=learned_at,
        )
    )
    session.commit()


def test_readiness_is_the_average_progress_of_a_chapters_words(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    set_progress(session, "word00", WordStatus.KNOWN, 0)
    set_progress(session, "word01", WordStatus.LEARNING, 40)
    set_progress(session, "word02", WordStatus.LEARNED, 100, learned_at=utcnow())
    set_progress(
        session, "word03", WordStatus.LEARNED, 100, learned_at=utcnow() - timedelta(weeks=3)
    )

    chapters = user_client.get(f"/api/documents/{two_chapter_book.id}/readiness").json()

    assert chapters[0] == {
        "index": 0,
        "title": "Loomings",
        "words": 10,
        "done": 2,  # known + learned (the decayed one is back in progress at 85)
        "in_progress": 2,
        "new": 6,
        "readiness": 32,  # (100 + 40 + 100 + 85) / 10, rounded
    }
    assert chapters[1]["readiness"] == 0


def test_current_reads_show_how_ready_their_chapter_is(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    set_progress(session, "word00", WordStatus.KNOWN, 0)

    reading = user_client.get("/api/readings").json()[0]

    assert reading["current_chapter_readiness"] == 10


def test_study_mode_only_asks_the_chapters_words(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    asked = set()
    for _ in range(12):
        url = f"/api/quiz/question?document_id={two_chapter_book.id}&chapter=1"
        asked.add(user_client.get(url).json()["prompt"])
        answer(user_client, session)  # answers the pending question just fetched

    assert asked <= set(LEMMAS[10:])


def test_a_finished_chapter_says_it_is_ready(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    for lemma in LEMMAS[10:]:
        set_progress(session, lemma, WordStatus.KNOWN, 0)

    response = user_client.get(f"/api/quiz/question?document_id={two_chapter_book.id}&chapter=1")

    assert response.status_code == 409
    assert response.json()["detail"].startswith("Chapter ready!")
    assert question(user_client)["prompt"] in LEMMAS[:10]  # the normal quiz carries on


def test_study_mode_needs_both_parameters(
    user_client: TestClient, two_chapter_book: Document
) -> None:
    response = user_client.get(f"/api/quiz/question?document_id={two_chapter_book.id}")

    assert response.status_code == 422


def test_study_mode_only_for_your_books(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    log_in(user_client, make_user(session, "other@example.com").email)

    response = user_client.get(f"/api/quiz/question?document_id={two_chapter_book.id}&chapter=0")

    assert response.status_code == 404
    assert user_client.get(f"/api/documents/{two_chapter_book.id}/readiness").status_code == 404
