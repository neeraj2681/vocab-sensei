from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.reminders import get_push_sender
from app.core.config import Settings
from app.core.enums import QuestionType
from app.core.push import PushError, PushTarget, SubscriptionGoneError
from app.db.models import PushSubscription, Question, QuizAnswer, User, Word
from app.services.quiz import Stats
from app.services.reminders import ReminderService, message
from tests.conftest import FakeEmailSender

KOLKATA = "Asia/Kolkata"  # UTC+5:30
ENDPOINT = "https://push.example.com/abc"
DEVICE = {"endpoint": ENDPOINT, "keys": {"p256dh": "key", "auth": "secret"}}


class FakePushSender:
    def __init__(self) -> None:
        self.sent: list[tuple[PushTarget, dict[str, str]]] = []
        self.gone: set[str] = set()
        self.failing: set[str] = set()

    def send(self, target: PushTarget, payload: dict[str, str]) -> None:
        if target.endpoint in self.gone:
            raise SubscriptionGoneError(target.endpoint)
        if target.endpoint in self.failing:
            raise PushError("push service down")
        self.sent.append((target, payload))


@pytest.fixture
def pusher(user_client: TestClient) -> FakePushSender:
    sender = FakePushSender()
    app = user_client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_push_sender] = lambda: sender
    return sender


def configure(client: TestClient, **changes: Any) -> dict[str, Any]:
    body = {"enabled": True, "time": "20:00", "timezone": KOLKATA, "channel": "push", **changes}
    response = client.put("/api/reminders", json=body)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def reader(session: Session) -> User:
    return session.scalars(select(User).where(User.email == "reader@example.com")).one()


def service(
    session: Session, settings: Settings, mailer: FakeEmailSender, pusher: FakePushSender
) -> ReminderService:
    return ReminderService(session, settings, mailer, pusher)


def at_kolkata(hour: int, minute: int, day: int = 31) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC) - timedelta(hours=5, minutes=30)


class TestSettings:
    def test_reminders_start_off(self, user_client: TestClient, pusher: FakePushSender) -> None:
        reminder = user_client.get("/api/reminders").json()

        assert {k: reminder[k] for k in ("enabled", "time", "timezone", "channel", "devices")} == {
            "enabled": False,
            "time": "20:00",
            "timezone": "UTC",
            "channel": "push",
            "devices": 0,
        }
        assert len(reminder["push_public_key"]) > 40  # base64url P-256 public key

    def test_settings_are_saved(self, user_client: TestClient, pusher: FakePushSender) -> None:
        configure(user_client, time="07:30", channel="email")

        reminder = user_client.get("/api/reminders").json()

        assert (reminder["enabled"], reminder["time"], reminder["channel"]) == (
            True,
            "07:30",
            "email",
        )
        assert reminder["timezone"] == KOLKATA

    @pytest.mark.parametrize(
        "change",
        [{"time": "25:00"}, {"time": "8pm"}, {"timezone": "Mars/Olympus"}, {"channel": "sms"}],
    )
    def test_invalid_settings_are_rejected(
        self, user_client: TestClient, pusher: FakePushSender, change: dict[str, str]
    ) -> None:
        body = {"enabled": True, "time": "20:00", "timezone": "UTC", "channel": "push", **change}

        assert user_client.put("/api/reminders", json=body).status_code == 422

    def test_devices_can_be_added_once_and_removed(
        self, user_client: TestClient, pusher: FakePushSender
    ) -> None:
        assert user_client.post("/api/reminders/devices", json=DEVICE).status_code == 204
        user_client.post("/api/reminders/devices", json=DEVICE)  # the same browser again
        assert user_client.get("/api/reminders").json()["devices"] == 1

        removed = user_client.request(
            "DELETE", "/api/reminders/devices", json={"endpoint": ENDPOINT}
        )

        assert removed.status_code == 204
        assert user_client.get("/api/reminders").json()["devices"] == 0

    def test_device_endpoints_must_be_https(
        self, user_client: TestClient, pusher: FakePushSender
    ) -> None:
        device = {**DEVICE, "endpoint": "http://evil.example.com"}

        assert user_client.post("/api/reminders/devices", json=device).status_code == 422

    def test_requires_login(self, client: TestClient) -> None:
        assert client.get("/api/reminders").status_code == 401


class TestSending:
    @pytest.fixture(autouse=True)
    def enabled(self, user_client: TestClient, pusher: FakePushSender) -> None:
        configure(user_client)
        user_client.post("/api/reminders/devices", json=DEVICE)

    def test_nothing_before_the_chosen_time(
        self, session: Session, settings: Settings, mailer: FakeEmailSender, pusher: FakePushSender
    ) -> None:
        assert service(session, settings, mailer, pusher).send_due(at_kolkata(19, 59)) == 0
        assert pusher.sent == []

    def test_a_push_at_the_chosen_time_then_not_again_that_day(
        self, session: Session, settings: Settings, mailer: FakeEmailSender, pusher: FakePushSender
    ) -> None:
        reminders = service(session, settings, mailer, pusher)

        assert reminders.send_due(at_kolkata(20, 1)) == 1
        assert reminders.send_due(at_kolkata(21, 0)) == 0
        assert reminders.send_due(at_kolkata(23, 59)) == 0  # still the same local day

        target, payload = pusher.sent[0]
        assert target.endpoint == ENDPOINT
        assert payload == {
            "title": "Vocab Sensei",
            "body": "0/10 today: 10 more answers reach today's goal.",
            "url": "/quiz",
        }

    def test_it_comes_back_the_next_day(
        self, session: Session, settings: Settings, mailer: FakeEmailSender, pusher: FakePushSender
    ) -> None:
        reminders = service(session, settings, mailer, pusher)
        reminders.send_due(at_kolkata(20, 1))

        assert reminders.send_due(at_kolkata(20, 1) + timedelta(days=1)) == 1

    def test_no_reminder_once_the_goal_is_met(
        self, session: Session, settings: Settings, mailer: FakeEmailSender, pusher: FakePushSender
    ) -> None:
        add_answers(session, 10, at_kolkata(9, 0))

        assert service(session, settings, mailer, pusher).send_due(at_kolkata(20, 1)) == 0

    def test_email_reminders(
        self,
        user_client: TestClient,
        session: Session,
        settings: Settings,
        mailer: FakeEmailSender,
        pusher: FakePushSender,
    ) -> None:
        configure(user_client, channel="email")

        assert service(session, settings, mailer, pusher).send_due(at_kolkata(20, 1)) == 1

        assert pusher.sent == []
        assert mailer.outbox[-1].to == "reader@example.com"
        assert "10 more answers" in mailer.outbox[-1].body
        assert mailer.outbox[-1].body.count("/quiz") == 1

    def test_unsubscribed_devices_are_forgotten(
        self, session: Session, settings: Settings, mailer: FakeEmailSender, pusher: FakePushSender
    ) -> None:
        pusher.gone.add(ENDPOINT)

        assert service(session, settings, mailer, pusher).send_due(at_kolkata(20, 1)) == 0

        assert session.scalars(select(PushSubscription)).all() == []

    def test_a_failing_push_service_is_logged_not_fatal(
        self,
        session: Session,
        settings: Settings,
        mailer: FakeEmailSender,
        pusher: FakePushSender,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        pusher.failing.add(ENDPOINT)

        assert service(session, settings, mailer, pusher).send_due(at_kolkata(20, 1)) == 0

        assert "push reminder failed" in caplog.text
        assert len(session.scalars(select(PushSubscription)).all()) == 1

    def test_disabled_reminders_stay_quiet(
        self,
        user_client: TestClient,
        session: Session,
        settings: Settings,
        mailer: FakeEmailSender,
        pusher: FakePushSender,
    ) -> None:
        configure(user_client, enabled=False)

        assert service(session, settings, mailer, pusher).send_due(at_kolkata(20, 1)) == 0

    def test_a_test_reminder_goes_out_now(
        self, user_client: TestClient, pusher: FakePushSender
    ) -> None:
        response = user_client.post("/api/reminders/test")

        assert response.json() == {"sent": True}
        assert len(pusher.sent) == 1


def test_a_test_reminder_needs_a_device_for_push(
    user_client: TestClient, pusher: FakePushSender
) -> None:
    assert user_client.post("/api/reminders/test").json() == {"sent": False}


@pytest.mark.parametrize(
    ("stats", "text"),
    [
        (
            Stats(total=0, today=3, daily_goal=10, streak=4),
            "3/10 today: 7 more answers keep your 🔥 4-day streak.",
        ),
        (
            Stats(total=0, today=0, daily_goal=10, streak=0),
            "0/10 today: 10 more answers reach today's goal.",
        ),
    ],
)
def test_the_message_mentions_the_streak_when_there_is_one(stats: Stats, text: str) -> None:
    assert message(stats) == text


def add_answers(session: Session, count: int, when: datetime) -> None:
    user = reader(session)
    word = Word(lemma="placeholder")
    session.add(word)
    session.flush()
    for _ in range(count):
        question = Question(
            user_id=user.id,
            word_id=word.id,
            type=QuestionType.DEFINITION_MCQ,
            prompt="placeholder",
            options=[],
            correct_index=0,
            generator="test",
        )
        session.add(question)
        session.flush()
        session.add(
            QuizAnswer(
                user_id=user.id,
                word_id=word.id,
                question_id=question.id,
                chosen_index=0,
                correct=True,
                score_delta=5,
                points=5,
                answered_at=when,
            )
        )
    session.commit()


class BrokenMailer:
    def send(self, email: object) -> None:
        raise ConnectionRefusedError("no mail server")


def test_a_failing_email_is_logged_not_fatal(
    user_client: TestClient,
    session: Session,
    settings: Settings,
    pusher: FakePushSender,
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure(user_client, channel="email")

    reminders = ReminderService(session, settings, BrokenMailer(), pusher)

    assert reminders.send_due(at_kolkata(20, 1)) == 0
    assert "reminder email failed" in caplog.text
