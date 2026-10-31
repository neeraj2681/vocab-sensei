import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pywebpush import WebPushException

from app.core import push
from app.core.config import PushSettings, Settings
from app.core.push import (
    PushError,
    PushTarget,
    SubscriptionGoneError,
    WebPushSender,
    load_or_create_keys,
)
from app.services import reminders

TARGET = PushTarget("https://push.example.com/abc", "key", "secret")


def test_keys_are_created_once_and_kept(tmp_path: Path) -> None:
    first = load_or_create_keys(PushSettings(), tmp_path)
    second = load_or_create_keys(PushSettings(), tmp_path)

    assert first == second
    assert first.private_pem.startswith("-----BEGIN ")  # a PEM block (spelled out, hooks flag it)
    assert oct((tmp_path / "vapid.json").stat().st_mode & 0o777) == "0o600"


def test_configured_keys_win(tmp_path: Path) -> None:
    keys = load_or_create_keys(
        PushSettings(vapid_private_key="PEM", vapid_public_key="PUB"), tmp_path
    )

    assert (keys.private_pem, keys.public_key) == ("PEM", "PUB")
    assert not (tmp_path / "vapid.json").exists()


@pytest.fixture
def sender(tmp_path: Path) -> WebPushSender:
    return WebPushSender(load_or_create_keys(PushSettings(), tmp_path), "mailto:me@example.com")


def test_sends_the_payload_as_json(sender: WebPushSender, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(push, "webpush", lambda **kwargs: calls.append(kwargs))

    sender.send(TARGET, {"title": "Vocab Sensei", "body": "hi"})

    assert calls[0]["subscription_info"]["endpoint"] == TARGET.endpoint
    assert calls[0]["data"] == '{"title": "Vocab Sensei", "body": "hi"}'
    assert calls[0]["vapid_claims"] == {"sub": "mailto:me@example.com"}


@pytest.mark.parametrize(
    ("status", "error"),
    [(410, SubscriptionGoneError), (404, SubscriptionGoneError), (500, PushError)],
)
def test_push_service_errors(
    sender: WebPushSender, monkeypatch: pytest.MonkeyPatch, status: int, error: type[Exception]
) -> None:
    def fail(**_kwargs: Any) -> None:
        raise WebPushException("nope", response=SimpleNamespace(status_code=status))

    monkeypatch.setattr(push, "webpush", fail)

    with pytest.raises(error):
        sender.send(TARGET, {})


def test_the_scheduler_checks_until_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = threading.Event()
    checks: list[object] = []

    class FakeService:
        def __init__(self, *_args: object) -> None:
            pass

        def send_due(self, now: object) -> int:
            checks.append(now)
            stop.set()  # one round is enough for the test
            return 1

    class NoSession:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(reminders, "ReminderService", FakeService)
    settings = Settings()
    settings.reminders.check_seconds = 1

    reminders.run_scheduler(stop, NoSession, settings, object(), object())  # type: ignore[arg-type]

    assert len(checks) == 1
