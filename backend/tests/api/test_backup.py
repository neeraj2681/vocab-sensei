from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import WordStatus
from app.db.models import User, UserWord, Word
from tests.api.test_quiz import LEMMAS, add_book, answer, reader
from tests.conftest import log_in, make_user


def export(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/backup")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def restore(client: TestClient, backup: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/backup", json=backup)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def progress_of(session: Session, user: User) -> dict[str, tuple[WordStatus, int]]:
    rows = session.execute(
        select(Word.lemma, UserWord.status, UserWord.score)
        .join(UserWord, UserWord.word_id == Word.id)
        .where(UserWord.user_id == user.id)
    )
    return {lemma: (status, score) for lemma, status, score in rows}


@pytest.fixture
def played(user_client: TestClient, session: Session) -> dict[str, Any]:
    """reader@example.com has read and answered a few questions; returns their backup."""
    add_book(session, reader(session), LEMMAS)
    for right in (True, True, False, True):
        answer(user_client, session, right=right)
    asked = user_client.get("/api/quiz/question").json()
    user_client.post(f"/api/quiz/questions/{asked['id']}/know")
    return export(user_client)


def test_export_has_progress_answers_and_reads(
    user_client: TestClient, played: dict[str, Any]
) -> None:
    assert played["version"] == 1
    assert len(played["words"]) == 5
    assert {w["status"] for w in played["words"]} == {"learning", "known"}
    assert [a["points"] for a in played["answers"]] == [5, 5, -10, 5, 0]
    assert played["answers"][-1]["knew_it"] is True
    assert played["readings"] == [{"title": "Moby-Dick", "priority": 0, "chapter_index": 0}]


def test_export_downloads_as_a_file(user_client: TestClient) -> None:
    response = user_client.get("/api/backup")

    assert response.headers["content-disposition"].startswith(
        'attachment; filename="vocab-sensei-backup-'
    )


def test_a_backup_restores_into_another_account(
    user_client: TestClient, session: Session, played: dict[str, Any]
) -> None:
    before = user_client.get("/api/quiz/history").json()
    other = make_user(session, "new@example.com")
    add_book(session, other, LEMMAS, reading=False)  # the same book, uploaded again
    log_in(user_client, other.email)

    summary = restore(user_client, played)

    assert summary == {
        "words_added": 5,
        "words_kept": 0,
        "answers_added": 5,
        "answers_skipped": 0,
        "readings_added": 1,
        "books_missing": [],
    }
    assert progress_of(session, other) == progress_of(session, reader(session))
    assert user_client.get("/api/quiz/history").json() == before
    assert user_client.get("/api/quiz/stats").json()["total"] == 5
    assert [r["document"]["title"] for r in user_client.get("/api/readings").json()] == [
        "Moby-Dick"
    ]


def test_restoring_twice_adds_nothing(
    user_client: TestClient, session: Session, played: dict[str, Any]
) -> None:
    summary = restore(user_client, played)  # into the same account it came from

    assert (summary["words_added"], summary["words_kept"]) == (0, 5)
    assert (summary["answers_added"], summary["answers_skipped"]) == (0, 5)
    assert summary["readings_added"] == 0
    assert len(user_client.get("/api/quiz/history").json()) == 4


def test_existing_progress_is_kept(
    user_client: TestClient, session: Session, played: dict[str, Any]
) -> None:
    played["words"][0]["score"] = 95

    restore(user_client, played)

    lemma = played["words"][0]["lemma"]
    assert progress_of(session, reader(session))[lemma][1] != 95


def test_missing_books_are_reported(user_client: TestClient, session: Session) -> None:
    backup = {
        "exported_at": "2026-10-30T12:00:00Z",
        "readings": [{"title": "Emma", "priority": 0, "chapter_index": 3}],
    }

    assert restore(user_client, backup)["books_missing"] == ["Emma"]


def test_unknown_words_are_kept_for_later(user_client: TestClient, session: Session) -> None:
    backup = {
        "exported_at": "2026-10-30T12:00:00Z",
        "words": [{"lemma": "zeugma", "status": "learning", "score": 40}],
    }

    restore(user_client, backup)

    assert progress_of(session, reader(session)) == {"zeugma": (WordStatus.LEARNING, 40)}


@pytest.mark.parametrize(
    "backup",
    [
        {"version": 2, "exported_at": "2026-10-30T12:00:00Z"},
        {"exported_at": "not a date"},
        {"exported_at": "2026-10-30T12:00:00Z", "words": [{"lemma": "x", "status": "?"}]},
    ],
)
def test_invalid_backups_are_rejected(user_client: TestClient, backup: dict[str, Any]) -> None:
    assert user_client.post("/api/backup", json=backup).status_code == 422


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/backup").status_code == 401
    assert client.post("/api/backup", json={}).status_code == 401
