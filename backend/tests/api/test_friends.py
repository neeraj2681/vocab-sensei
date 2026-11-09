from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import User
from tests.api.test_quiz import book, clock, reader  # noqa: F401 (fixtures)
from tests.conftest import log_in, make_user

pytestmark = pytest.mark.usefixtures("book", "clock")


def person(session: Session, email: str, name: str, **extra: Any) -> User:
    user = make_user(session, email)
    user.display_name, user.show_on_leaderboard = name, True
    for key, value in extra.items():
        setattr(user, key, value)
    session.commit()
    return user


def test_search_finds_exact_usernames_and_emails_only(
    user_client: TestClient, session: Session
) -> None:
    asha = person(session, "asha@example.com", "Asha")
    person(session, "ashwin@example.com", "Ashwin")
    zed = person(session, "zed@example.com", "Zed", show_on_leaderboard=False)

    by_name = user_client.get("/api/friends/search?q=asha").json()
    by_email = user_client.get("/api/friends/search?q=ASHA@example.com").json()

    assert [(p["user_id"], p["relation"]) for p in by_name] == [(asha.id, "none")]
    assert [p["display_name"] for p in by_email] == ["Asha"]
    assert user_client.get("/api/friends/search?q=ash").json() == []  # no partial matches
    hidden = user_client.get("/api/friends/search?q=zed").json()  # off the board, still findable
    assert [p["user_id"] for p in hidden] == [zed.id]
    assert "email" not in by_name[0]


def test_a_request_accepted_makes_friends(
    user_client: TestClient, client: TestClient, session: Session
) -> None:
    asha = person(session, "asha@example.com", "Asha")
    me = reader(session)

    sent = user_client.post(f"/api/friends/{asha.id}")

    assert sent.json()["relation"] == "requested"
    assert [p["display_name"] for p in user_client.get("/api/friends").json()["requested"]] == [
        "Asha"
    ]
    log_in(client, "asha@example.com")
    assert [p["user_id"] for p in client.get("/api/friends").json()["asked_you"]] == [me.id]
    assert client.post(f"/api/friends/{me.id}/accept").status_code == 204
    assert [p["display_name"] for p in client.get("/api/friends").json()["friends"]] == ["Reader"]
    log_in(client, "reader@example.com")  # the same test browser, back as the reader
    assert user_client.get("/api/friends").json()["friends"][0]["relation"] == "friends"


def test_declining_or_removing_ends_it(user_client: TestClient, session: Session) -> None:
    asha = person(session, "asha@example.com", "Asha")
    user_client.post(f"/api/friends/{asha.id}")

    assert user_client.delete(f"/api/friends/{asha.id}").status_code == 204

    assert user_client.get("/api/friends").json() == {
        "friends": [],
        "asked_you": [],
        "requested": [],
    }


def test_the_friends_leaderboard_shows_just_you_and_your_friends(
    user_client: TestClient, client: TestClient, session: Session
) -> None:
    asha = person(session, "asha@example.com", "Asha", show_on_leaderboard=False)
    person(session, "bo@example.com", "Bo")
    me = reader(session)
    user_client.post(f"/api/friends/{asha.id}")
    log_in(client, "asha@example.com")
    client.post(f"/api/friends/{me.id}/accept")
    log_in(client, "reader@example.com")  # the same test browser, back as the reader

    friends = user_client.get("/api/leaderboard?tz=UTC&scope=friends").json()
    everyone = user_client.get("/api/leaderboard?tz=UTC").json()

    assert sorted(r["display_name"] for r in friends) == ["Asha", "Reader"]
    assert sorted(r["display_name"] for r in everyone) == ["Bo", "Reader"]  # Asha hides there
    assert user_client.get(f"/api/profiles/{asha.id}?tz=UTC").status_code == 200  # a friend
