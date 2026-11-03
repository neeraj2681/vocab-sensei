from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import QuestClaim
from tests.api.test_quiz import NOW, answer, book, clock, reader  # noqa: F401 (fixtures)

pytestmark = pytest.mark.usefixtures("book", "clock")


def quests(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/quests?tz=UTC")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_three_quests_with_progress_from_todays_answers(
    user_client: TestClient, session: Session
) -> None:
    before = quests(user_client)
    assert [q["tier"] for q in before["quests"]] == ["easy", "medium", "hard"]
    assert all(q["progress"] == 0 and not q["claimed"] for q in before["quests"])

    for _ in range(3):
        answer(user_client, session)

    easy = quests(user_client)["quests"][0]
    assert easy["progress"] == min(3, easy["target"])


def test_claiming_a_finished_quest_adds_its_coins_once(
    user_client: TestClient, session: Session
) -> None:
    for _ in range(
        6
    ):  # finishes any easy quest when the goal is 10 (5 answers / 5 right / 3 in a row)
        answer(user_client, session)
    easy = quests(user_client)["quests"][0]
    total = user_client.get("/api/quiz/stats?tz=UTC").json()["total"]

    claimed = user_client.post(f"/api/quests/{easy['key']}/claim?tz=UTC")

    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["coins"] == 10
    assert claimed.json()["total"] == total + 10
    assert claimed.json()["quests"]["quests"][0]["claimed"] is True
    assert user_client.get("/api/quiz/stats?tz=UTC").json()["total"] == total + 10
    week = user_client.get("/api/quiz/stats?tz=UTC").json()["week"]
    assert week[-1]["points"] == total + 10  # quest coins count on the home graph too
    again = user_client.post(f"/api/quests/{easy['key']}/claim?tz=UTC")
    assert again.status_code == 409


def test_unfinished_and_unknown_quests_cannot_be_claimed(user_client: TestClient) -> None:
    hard = quests(user_client)["quests"][2]

    assert user_client.post(f"/api/quests/{hard['key']}/claim?tz=UTC").status_code == 409
    assert user_client.post("/api/quests/answer-999/claim?tz=UTC").status_code == 404


def test_the_chest_opens_once_all_three_are_claimed(
    user_client: TestClient, session: Session
) -> None:
    assert user_client.post("/api/quests/chest/claim?tz=UTC").status_code == 409
    for quest in quests(user_client)["quests"]:  # as if all three were finished and claimed
        claim = QuestClaim(user_id=reader(session).id, day=NOW.date(), quest=quest["key"], coins=0)
        session.add(claim)
    session.commit()
    assert quests(user_client)["chest_ready"] is True

    opened = user_client.post("/api/quests/chest/claim?tz=UTC")

    assert opened.status_code == 200, opened.text
    assert opened.json()["coins"] == 25
    assert opened.json()["quests"]["chest_claimed"] is True
    assert user_client.post("/api/quests/chest/claim?tz=UTC").status_code == 409
