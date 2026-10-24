from __future__ import annotations

import smtplib
from email.message import EmailMessage
from types import TracebackType
from typing import ClassVar, Self

import pytest

from app.core.config import EmailSettings
from app.core.email import Email, SmtpEmailSender


class FakeSMTP:
    instances: ClassVar[list[FakeSMTP]] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port = host, port
        self.started_tls = False
        self.logged_in_as: str | None = None
        self.sent: list[EmailMessage] = []
        FakeSMTP.instances.append(self)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: type[BaseException] | BaseException | TracebackType | None) -> None:
        pass

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, _password: str) -> None:
        self.logged_in_as = username

    def send_message(self, message: EmailMessage) -> None:
        self.sent.append(message)


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)


def test_sends_plain_message_to_mailpit_by_default() -> None:
    SmtpEmailSender(EmailSettings()).send(Email(to="a@example.com", subject="Hi", body="Hello"))

    smtp = FakeSMTP.instances[0]
    assert (smtp.host, smtp.port) == ("localhost", 1025)
    assert not smtp.started_tls
    assert smtp.logged_in_as is None
    message = smtp.sent[0]
    assert message["To"] == "a@example.com"
    assert message["Subject"] == "Hi"
    assert message.get_content().strip() == "Hello"


def test_uses_starttls_and_login_when_configured() -> None:
    settings = EmailSettings(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_starttls=True,
        smtp_username="me",
        smtp_password="app-password",
    )

    SmtpEmailSender(settings).send(Email(to="a@example.com", subject="Hi", body="Hello"))

    smtp = FakeSMTP.instances[0]
    assert smtp.started_tls
    assert smtp.logged_in_as == "me"
