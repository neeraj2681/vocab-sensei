from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import WordStatus
from app.db.models import Document, UserWord, Word
from tests.api.test_quiz import LEMMAS, add_word, answer, reader
from tests.conftest import log_in, make_user


def batch(client: TestClient, document: Document, limit: int = 20) -> dict[str, Any]:
    response = client.get(f"/api/documents/{document.id}/sort?limit={limit}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def word_id(session: Session, lemma: str) -> int:
    return session.scalars(select(Word.id).where(Word.lemma == lemma)).one()


def sort(client: TestClient, session: Session, lemma: str, choice: str) -> dict[str, Any]:
    response = client.put(f"/api/words/{word_id(session, lemma)}/sort", json={"choice": choice})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_unsorted_words_come_in_reading_order(
    user_client: TestClient, two_chapter_book: Document
) -> None:
    result = batch(user_client, two_chapter_book, limit=3)

    assert result["remaining"] == 20
    assert result["from_chapter"] == 0
    assert result["words"][0] == {
        "word_id": result["words"][0]["word_id"],
        "lemma": "word00",
        "pos": "noun",
        "definition": "meaning of word00",
        "context_sentence": "A sentence with word00.",
        "chapter_index": 0,
        "chapter_title": "Loomings",
        "earlier": False,
    }
    assert [w["lemma"] for w in result["words"]] == ["word00", "word01", "word02"]


def test_starts_at_the_chapter_being_read(
    user_client: TestClient, two_chapter_book: Document
) -> None:
    user_client.patch(f"/api/readings/{two_chapter_book.id}", json={"current_chapter_index": 1})

    result = batch(user_client, two_chapter_book, limit=4)

    assert (result["remaining"], result["from_chapter"]) == (20, 1)  # the whole book
    assert [(w["lemma"], w["earlier"]) for w in result["words"]] == [
        ("word10", False),
        ("word11", False),
        ("word00", True),  # 1 in 4 cards from the chapter before
        ("word12", False),
    ]


@pytest.mark.parametrize(
    ("choice", "status", "score"),
    [("known", "known", 0), ("unsure", "learning", 50), ("new", "new", 0)],
)
def test_sorting_sets_the_starting_point(
    user_client: TestClient,
    session: Session,
    two_chapter_book: Document,
    choice: str,
    status: str,
    score: int,
) -> None:
    result = sort(user_client, session, "word00", choice)

    assert (result["status"], result["score"]) == (status, score)
    after = batch(user_client, two_chapter_book)
    assert after["remaining"] == 19
    assert "word00" not in [w["lemma"] for w in after["words"]]


def test_known_words_are_never_quizzed(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    for lemma in LEMMAS[:5]:
        sort(user_client, session, lemma, "known")

    asked = {answer(user_client, session)["word"] for _ in range(15)}

    assert not asked & set(LEMMAS[:5])


def test_words_sorted_as_new_stay_in_the_learning_list(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    sort(user_client, session, "word00", "new")
    sort(user_client, session, "word01", "unsure")

    lemmas = [w["lemma"] for w in user_client.get("/api/learning/next?count=3").json()]

    assert lemmas == ["word00", "word02", "word03"]  # unsure words are in progress, not new


def test_a_choice_can_be_changed_or_undone(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    sort(user_client, session, "word00", "known")

    assert sort(user_client, session, "word00", "unsure")["status"] == "learning"
    response = user_client.delete(f"/api/words/{word_id(session, 'word00')}/sort")

    assert response.status_code == 204
    assert batch(user_client, two_chapter_book, limit=1)["words"][0]["lemma"] == "word00"
    assert session.get(UserWord, (reader(session).id, word_id(session, "word00"))) is None


def test_answered_words_can_no_longer_be_sorted(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    lemma = answer(user_client, session)["word"]
    url = f"/api/words/{word_id(session, lemma)}/sort"

    assert user_client.put(url, json={"choice": "known"}).status_code == 409
    assert user_client.delete(url).status_code == 409
    progress = session.get(UserWord, (reader(session).id, word_id(session, lemma)))
    assert progress is not None
    assert progress.status == WordStatus.LEARNING


def test_only_words_from_your_books(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    stranger = add_word(session, "zeugma")
    session.commit()

    response = user_client.put(f"/api/words/{stranger.id}/sort", json={"choice": "known"})

    assert response.status_code == 404
    assert user_client.delete(f"/api/words/{stranger.id}/sort").status_code == 404


def test_other_users_books_are_hidden(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    log_in(user_client, make_user(session, "other@example.com").email)

    assert user_client.get(f"/api/documents/{two_chapter_book.id}/sort").status_code == 404


def test_choice_must_be_known_unsure_or_new(
    user_client: TestClient, session: Session, two_chapter_book: Document
) -> None:
    response = user_client.put(
        f"/api/words/{word_id(session, 'word00')}/sort", json={"choice": "maybe"}
    )

    assert response.status_code == 422


def test_limit_zero_only_counts(user_client: TestClient, two_chapter_book: Document) -> None:
    result = batch(user_client, two_chapter_book, limit=0)

    assert (result["remaining"], result["words"]) == (20, [])
