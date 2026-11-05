from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import QuestClaim
from app.services.recaps import months_before, weeks_before
from app.services.reminders import ReminderService
from tests.api.test_quiz import NOW, Clock, answer, book, clock, reader  # noqa: F401 (fixtures)
from tests.api.test_reminders import FakePushSender, configure, pusher  # noqa: F401 (fixtures)
from tests.conftest import FakeEmailSender

pytestmark = pytest.mark.usefixtures("book", "clock")

WEDNESDAY_BEFORE = NOW - timedelta(days=9)  # NOW is Friday 30 Oct; that week ran 19 to 25 Oct


@pytest.fixture
def time(request: pytest.FixtureRequest) -> Clock:
    found: Clock = request.getfixturevalue("clock")
    return found


def test_finished_weeks_and_months() -> None:
    friday = date(2026, 10, 30)

    assert weeks_before(friday, 2) == [
        (date(2026, 10, 19), date(2026, 10, 25)),
        (date(2026, 10, 12), date(2026, 10, 18)),
    ]
    assert months_before(friday, 2) == [
        (date(2026, 9, 1), date(2026, 9, 30)),
        (date(2026, 8, 1), date(2026, 8, 31)),
    ]


def test_last_weeks_recap(user_client: TestClient, session: Session, time: Clock) -> None:
    user = reader(session)
    user.created_at, user.daily_goal = WEDNESDAY_BEFORE, 2
    session.commit()
    time.now = WEDNESDAY_BEFORE
    for right in (True, True, True, False):
        answer(user_client, session, right=right)
    session.add(
        QuestClaim(user_id=reader(session).id, day=WEDNESDAY_BEFORE.date(), quest="q", coins=10)
    )
    session.commit()
    time.now = NOW

    recaps: dict[str, Any] = user_client.get("/api/recaps?tz=UTC").json()

    # This week, then last week from the day they joined; nothing from before.
    assert [(w["first"], w["current"]) for w in recaps["weeks"]] == [
        ("2026-10-26", True),
        ("2026-10-21", False),
    ]
    week = recaps["weeks"][1]
    assert week["last"] == "2026-10-25"
    assert (week["answers"], week["right"], week["coins"]) == (4, 3, 15)  # 3x5 - 10 + 10
    assert (week["goal_days"], week["days"]) == (1, 5)  # Wednesday to Sunday
    assert week["streak"] == 0  # Sunday was missed
    assert week["best_day"] == "2026-10-21"
    assert week["favourite_book"] == "Moby-Dick"
    assert week["toughest_word"] is not None
    assert [m["first"] for m in recaps["months"]] == ["2026-10-21"]


def test_this_week_counts_today_once_its_goal_is_met(
    user_client: TestClient, session: Session, time: Clock
) -> None:
    user = reader(session)
    user.created_at, user.daily_goal = NOW - timedelta(days=1), 2  # joined Thursday
    session.commit()
    time.now = NOW - timedelta(days=1)
    answer(user_client, session, right=True)
    answer(user_client, session, right=True)
    time.now = NOW

    week = user_client.get("/api/recaps?tz=UTC").json()["weeks"][0]
    assert (week["first"], week["current"]) == ("2026-10-29", True)
    assert (week["goal_days"], week["days"], week["streak"]) == (1, 1, 1)  # today not yet

    answer(user_client, session, right=True)
    answer(user_client, session, right=True)
    week = user_client.get("/api/recaps?tz=UTC").json()["weeks"][0]
    assert (week["goal_days"], week["days"], week["streak"]) == (2, 2, 2)


def test_the_recap_is_emailed_on_monday_at_the_reminder_time(
    user_client: TestClient,
    session: Session,
    settings: Settings,
    mailer: FakeEmailSender,
    pusher: FakePushSender,  # noqa: F811
) -> None:
    configure(user_client, time="09:00", timezone="UTC", push=False, email=True)
    reminders = ReminderService(session, settings, mailer, pusher)
    monday = datetime(2026, 11, 2, 8, 59, tzinfo=UTC)
    reader(session).created_at = datetime(2026, 10, 1, tzinfo=UTC)
    session.commit()
    before = len(mailer.outbox)

    assert reminders.send_recaps(monday) == 0  # before 9:00
    assert reminders.send_recaps(monday + timedelta(minutes=1)) == 1
    assert reminders.send_recaps(monday + timedelta(hours=3)) == 0  # once a day

    sent = mailer.outbox[before:]
    assert [m.subject for m in sent] == ["Your Vocab Sensei recap"]
    assert "Your week (26 Oct to 01 Nov)" in sent[0].body
    assert "Your month" not in sent[0].body  # 2 Nov isn't the 1st


def test_no_recap_email_for_a_week_before_joining(
    user_client: TestClient,
    session: Session,
    settings: Settings,
    mailer: FakeEmailSender,
    pusher: FakePushSender,  # noqa: F811
) -> None:
    configure(user_client, time="09:00", timezone="UTC", push=False, email=True)
    monday = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
    reader(session).created_at = monday - timedelta(hours=2)
    session.commit()

    assert ReminderService(session, settings, mailer, pusher).send_recaps(monday) == 0


def test_no_recap_email_midweek_or_without_email_reminders(
    user_client: TestClient,
    session: Session,
    settings: Settings,
    mailer: FakeEmailSender,
    pusher: FakePushSender,  # noqa: F811
) -> None:
    configure(user_client, time="09:00", timezone="UTC", push=True, email=False)
    reminders = ReminderService(session, settings, mailer, pusher)

    assert reminders.send_recaps(datetime(2026, 11, 2, 10, 0, tzinfo=UTC)) == 0  # no email
    configure(user_client, time="09:00", timezone="UTC", push=False, email=True)
    assert reminders.send_recaps(datetime(2026, 11, 4, 10, 0, tzinfo=UTC)) == 0  # a Wednesday
