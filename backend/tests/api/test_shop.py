from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import QuestClaim
from tests.api.test_quiz import NOW, Clock, answer, book, clock, reader  # noqa: F401 (fixtures)

pytestmark = pytest.mark.usefixtures("book", "clock")

SUNDAY = NOW + timedelta(days=2)  # NOW is a Friday


@pytest.fixture
def time(request: pytest.FixtureRequest) -> Clock:
    """The test clock (test_quiz's `clock` fixture), to move to Sunday and beyond."""
    found: Clock = request.getfixturevalue("clock")
    return found


def give_coins(session: Session, coins: int) -> None:
    session.add(QuestClaim(user_id=reader(session).id, day=NOW.date(), quest="gift", coins=coins))
    session.commit()


def shop(client: TestClient) -> dict[str, Any]:
    body: dict[str, Any] = client.get("/api/shop?tz=UTC").json()
    return body


def stock(state: dict[str, Any], item: str) -> dict[str, Any]:
    found: dict[str, Any] = next(s for s in state["stock"] if s["item"] == item)
    return found


def test_closed_except_on_sundays(user_client: TestClient, session: Session, time: Clock) -> None:
    give_coins(session, 100_000)

    friday = shop(user_client)
    refused = user_client.post("/api/shop/buy/streak_freeze?tz=UTC")

    assert friday["open"] is False
    assert friday["opens_at"].startswith(SUNDAY.date().isoformat())
    assert refused.status_code == 409
    time.now = SUNDAY
    assert shop(user_client)["open"] is True


def test_buying_freezes_spends_coins_up_to_three(
    user_client: TestClient, session: Session, time: Clock
) -> None:
    time.now = SUNDAY
    give_coins(session, 5_000)

    for _ in range(3):
        assert user_client.post("/api/shop/buy/streak_freeze?tz=UTC").status_code == 200
    fourth = user_client.post("/api/shop/buy/streak_freeze?tz=UTC")

    state = shop(user_client)
    assert fourth.status_code == 409
    assert (stock(state, "streak_freeze")["owned"], state["coins"]) == (3, 500)
    assert user_client.get("/api/quiz/stats?tz=UTC").json()["total"] == 500
    too_dear = user_client.post("/api/shop/buy/double_coins?tz=UTC")  # 1,000 > 500
    assert (too_dear.status_code, too_dear.json()["detail"]) == (409, "Not enough coins yet")


def test_double_coins_double_right_answers_for_half_an_hour(
    user_client: TestClient, session: Session, time: Clock
) -> None:
    time.now = SUNDAY
    give_coins(session, 1_000)
    user_client.post("/api/shop/buy/double_coins?tz=UTC")
    assert user_client.post("/api/shop/buy/double_coins?tz=UTC").status_code == 409  # one at most

    used = user_client.post("/api/shop/use/double_coins?tz=UTC").json()

    assert stock(used, "double_coins")["owned"] == 0
    assert used["double_coins_until"] is not None
    points = [answer(user_client, session)["points"] for _ in range(6)]
    assert points == [10, 10, 10, 10, 10, 20]  # the sixth is in Ninja Mode too: 4x
    time.now = SUNDAY + timedelta(minutes=31)
    assert answer(user_client, session, right=False)["points"] == -5  # a miss is never doubled
    assert answer(user_client, session)["points"] == 5  # over
    assert user_client.post("/api/shop/use/double_coins?tz=UTC").status_code == 409


def test_a_streak_freeze_saves_a_missed_day(
    user_client: TestClient, session: Session, time: Clock
) -> None:
    time.now = SUNDAY
    give_coins(session, 1_500)
    user_client.post("/api/shop/buy/streak_freeze?tz=UTC")
    for _ in range(10):  # Sunday's goal (10) met
        answer(user_client, session)
    assert user_client.get("/api/quiz/stats?tz=UTC").json()["streak"] == 1

    time.now = SUNDAY + timedelta(days=2)  # Monday missed
    stats = user_client.get("/api/quiz/stats?tz=UTC").json()

    assert stats["streak"] == 2  # Sunday + the frozen Monday
    monday = stats["week"][-2]
    assert (monday["met"], monday["frozen"]) == (True, True)
    assert stock(shop(user_client), "streak_freeze")["owned"] == 0  # used up


def test_a_freeze_is_kept_while_the_goal_is_met(
    user_client: TestClient, session: Session, time: Clock
) -> None:
    time.now = SUNDAY
    give_coins(session, 1_500)
    user_client.post("/api/shop/buy/streak_freeze?tz=UTC")
    for days in (0, 1):
        time.now = SUNDAY + timedelta(days=days)
        for _ in range(10):
            answer(user_client, session)

    time.now = SUNDAY + timedelta(days=2)

    assert user_client.get("/api/quiz/stats?tz=UTC").json()["streak"] == 2
    assert stock(shop(user_client), "streak_freeze")["owned"] == 1  # carried over


def test_a_bought_name_change_allows_another_username_change(
    user_client: TestClient, session: Session, time: Clock
) -> None:
    time.now = SUNDAY
    give_coins(session, 5_000)
    assert user_client.patch("/api/auth/me/name", json={"display_name": "First"}).status_code == 200
    assert user_client.patch("/api/auth/me/name", json={"display_name": "Again"}).status_code == 409

    assert user_client.post("/api/shop/buy/name_change?tz=UTC").status_code == 200
    assert user_client.post("/api/shop/buy/name_change?tz=UTC").status_code == 409  # one at most
    changed = user_client.patch("/api/auth/me/name", json={"display_name": "Second"})

    assert changed.status_code == 200
    assert changed.json()["display_name"] == "Second"
    assert stock(shop(user_client), "name_change")["owned"] == 0  # used
    assert user_client.patch("/api/auth/me/name", json={"display_name": "Third"}).status_code == 409
