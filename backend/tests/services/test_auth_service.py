"""Time-dependent rules, tested through the service with a controllable clock."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.email import Email
from app.services.auth import AuthService, InvalidTokenError
from tests.api.test_auth import EMAIL, PASSWORD
from tests.conftest import FakeEmailSender


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 24, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def service(session: Session, mailer: FakeEmailSender, clock: Clock) -> AuthService:
    return AuthService(session, mailer, Settings(), clock=clock)


def last_token(outbox: list[Email]) -> str:
    return outbox[-1].body.split("?token=")[1].split()[0]


def verified_user(service: AuthService, mailer: FakeEmailSender) -> None:
    service.register(EMAIL, PASSWORD, "Reader")
    service.verify_email(last_token(mailer.outbox))


def test_verification_link_expires_after_24_hours(
    service: AuthService, mailer: FakeEmailSender, clock: Clock
) -> None:
    service.register(EMAIL, PASSWORD, "Reader")
    clock.now += timedelta(hours=24)

    with pytest.raises(InvalidTokenError):
        service.verify_email(last_token(mailer.outbox))


def test_reset_link_expires_after_an_hour(
    service: AuthService, mailer: FakeEmailSender, clock: Clock
) -> None:
    verified_user(service, mailer)
    service.forgot_password(EMAIL)
    clock.now += timedelta(minutes=61)

    with pytest.raises(InvalidTokenError):
        service.reset_password(last_token(mailer.outbox), "another passphrase")


def test_verify_token_cannot_reset_password(service: AuthService, mailer: FakeEmailSender) -> None:
    service.register(EMAIL, PASSWORD, "Reader")

    with pytest.raises(InvalidTokenError):
        service.reset_password(last_token(mailer.outbox), "another passphrase")


def test_session_expires_after_30_days(
    service: AuthService, mailer: FakeEmailSender, clock: Clock
) -> None:
    verified_user(service, mailer)
    token = service.login(EMAIL, PASSWORD, user_agent="pytest").session_token

    clock.now += timedelta(days=29)
    assert service.user_for_session(token) is not None

    clock.now += timedelta(days=1)
    assert service.user_for_session(token) is None


def test_inactive_users_cannot_use_their_session(
    service: AuthService, mailer: FakeEmailSender
) -> None:
    verified_user(service, mailer)
    result = service.login(EMAIL, PASSWORD, user_agent=None)

    result.user.is_active = False

    assert service.user_for_session(result.session_token) is None


def test_password_is_stored_hashed(service: AuthService, mailer: FakeEmailSender) -> None:
    verified_user(service, mailer)
    user = service.login(EMAIL, PASSWORD, user_agent=None).user

    assert PASSWORD not in user.password_hash
    assert user.password_hash.startswith("$argon2id$")
