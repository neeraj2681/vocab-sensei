from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CurrentReading, Document, QuestClaim, User
from tests.api.test_quiz import NOW, answer, book, clock, reader  # noqa: F401 (fixtures)
from tests.conftest import make_user

pytestmark = pytest.mark.usefixtures("book", "clock")


def friend(session: Session, email: str, name: str, coins: int, **extra: Any) -> User:
    """Another user on the board, with `coins` earned today (from a quest, so no questions are
    needed)."""
    user = make_user(session, email)
    user.display_name, user.show_on_leaderboard = name, True
    for key, value in extra.items():
        setattr(user, key, value)
    session.add(QuestClaim(user_id=user.id, day=NOW.date(), quest="answer-10", coins=coins))
    session.commit()
    return user


def board(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/api/leaderboard?tz=UTC")
    assert response.status_code == 200, response.text
    rows: list[dict[str, Any]] = response.json()
    return rows


def test_ranks_everyone_by_coins_earned_today(user_client: TestClient, session: Session) -> None:
    friend(session, "asha@example.com", "Asha", 40)
    friend(session, "bo@example.com", "Bo", 0)
    for _ in range(3):
        answer(user_client, session)  # 15 coins

    rows = board(user_client)

    assert [(r["display_name"], r["coins_today"], r["me"]) for r in rows] == [
        ("Asha", 40, False),
        ("Reader", 15, True),
        ("Bo", 0, False),
    ]
    assert "email" not in rows[0]


def test_people_can_hide_from_it(user_client: TestClient, session: Session) -> None:
    hidden = friend(session, "zed@example.com", "Zed", 99, show_on_leaderboard=False)

    assert "Zed" not in [r["display_name"] for r in board(user_client)]
    assert user_client.get(f"/api/profiles/{hidden.id}?tz=UTC").status_code == 404

    switched = user_client.put("/api/auth/me/leaderboard", json={"show": False})
    assert switched.json()["show_on_leaderboard"] is False
    assert [r["me"] for r in board(user_client)] == [True]  # still sees themselves


def test_a_profile_shows_stats_graphs_and_books_never_the_email(
    user_client: TestClient, session: Session
) -> None:
    other = friend(session, "asha@example.com", "Asha", 40)
    for right in (True, True, False):
        answer(user_client, session, right=right)
    me = reader(session)

    own = user_client.get(f"/api/profiles/{me.id}?tz=UTC").json()
    theirs = user_client.get(f"/api/profiles/{other.id}?tz=UTC")

    assert (own["me"], own["answers"], own["right"], own["coins"]) == (True, 3, 2, 0)
    assert len(own["history"]) == 3
    assert len(own["week"]) == 7
    assert [(b["title"], b["author"]) for b in own["books"]] == [("Moby-Dick", None)]
    assert theirs.status_code == 200
    assert theirs.json()["me"] is False
    assert theirs.json()["coins_today"] == 40
    assert "email" not in theirs.json()
    assert user_client.get(f"/api/profiles/{other.id}/avatar").status_code == 404  # no picture
    assert user_client.get("/api/profiles/99999?tz=UTC").status_code == 404


def test_books_can_be_kept_private(user_client: TestClient, session: Session) -> None:
    private = friend(session, "kai@example.com", "Kai", 5, show_books=False)
    me = reader(session)

    theirs = user_client.get(f"/api/profiles/{private.id}?tz=UTC").json()
    switched = user_client.put("/api/auth/me/books-visibility", json={"show": False})
    own = user_client.get(f"/api/profiles/{me.id}?tz=UTC").json()

    assert (theirs["books"], theirs["books_hidden"]) == ([], True)
    assert switched.json()["show_books"] is False
    assert ([b["title"] for b in own["books"]], own["books_hidden"]) == (["Moby-Dick"], False)


def test_book_covers_on_a_profile(user_client: TestClient, session: Session, settings: Any) -> None:
    moby = session.scalars(select(Document)).one()  # from the book fixture
    other = friend(session, "asha@example.com", "Asha", 0)
    session.add(CurrentReading(user_id=other.id, document_id=moby.id, priority=0))
    moby.cover_path = f"covers/{moby.id}.jpg"
    moby.owner_user_id = None  # a built-in classic: its cover may be shown to anyone
    cover = settings.data_dir / moby.cover_path
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"jpeg bytes")
    session.commit()

    listed = user_client.get(f"/api/profiles/{other.id}?tz=UTC").json()["books"]
    response = user_client.get(f"/api/profiles/{other.id}/books/{moby.id}/cover")

    assert [(b["id"], b["has_cover"]) for b in listed] == [(moby.id, True)]
    assert response.status_code == 200
    assert response.content == b"jpeg bytes"
    assert user_client.get(f"/api/profiles/{other.id}/books/99999/cover").status_code == 404
    other.show_books = False
    session.commit()
    assert user_client.get(f"/api/profiles/{other.id}/books/{moby.id}/cover").status_code == 404


def test_covers_of_someones_own_uploads_stay_private(
    user_client: TestClient, session: Session, settings: Any
) -> None:
    other = friend(session, "asha@example.com", "Asha", 0)
    upload = session.scalars(select(Document)).one()  # from the book fixture
    upload.owner_user_id, upload.cover_path = other.id, f"covers/{upload.id}.jpg"
    session.add(CurrentReading(user_id=other.id, document_id=upload.id, priority=0))
    cover = settings.data_dir / upload.cover_path
    cover.parent.mkdir(parents=True, exist_ok=True)
    cover.write_bytes(b"jpeg bytes")
    session.commit()

    listed = user_client.get(f"/api/profiles/{other.id}?tz=UTC").json()["books"]

    assert [(b["title"], b["has_cover"]) for b in listed] == [(upload.title, False)]  # title only
    assert user_client.get(f"/api/profiles/{other.id}/books/{upload.id}/cover").status_code == 404


def test_new_accounts_keep_off_the_board_until_they_choose(
    user_client: TestClient, session: Session
) -> None:
    newcomer = make_user(session, "new@example.com")

    assert newcomer.show_on_leaderboard is False
    assert all(row["user_id"] != newcomer.id for row in board(user_client))
