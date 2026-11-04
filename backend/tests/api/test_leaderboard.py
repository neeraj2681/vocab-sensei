from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import QuestClaim, User
from tests.api.test_quiz import NOW, answer, book, clock, reader  # noqa: F401 (fixtures)
from tests.conftest import make_user

pytestmark = pytest.mark.usefixtures("book", "clock")


def friend(session: Session, email: str, name: str, coins: int, **extra: Any) -> User:
    """Another user, with `coins` earned today (from a quest, so no questions are needed)."""
    user = make_user(session, email)
    user.display_name = name
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
    assert own["books"] == [{"title": "Moby-Dick", "author": None}]
    assert theirs.status_code == 200
    assert theirs.json()["me"] is False
    assert theirs.json()["coins_today"] == 40
    assert "email" not in theirs.json()
    assert user_client.get(f"/api/profiles/{other.id}/avatar").status_code == 404  # no picture
    assert user_client.get("/api/profiles/99999?tz=UTC").status_code == 404
