import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_email_sender
from app.core.email import Email
from app.db.models import User
from tests.conftest import FakeEmailSender

EMAIL = "reader@example.com"
PASSWORD = "correct horse battery"


def token_from(mailer: FakeEmailSender) -> str:
    match = re.search(r"\?token=([\w-]+)", mailer.outbox[-1].body)
    assert match, mailer.outbox[-1].body
    return match.group(1)


def register(client: TestClient, email: str = EMAIL) -> None:
    response = client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD, "display_name": "Reader"}
    )
    assert response.status_code == 202


def register_and_verify(client: TestClient, mailer: FakeEmailSender) -> None:
    register(client)
    assert client.post("/api/auth/verify-email", json={"token": token_from(mailer)}).is_success


def login(client: TestClient, password: str = PASSWORD, email: str = EMAIL) -> int:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    status: int = response.status_code
    return status


def test_full_sign_up_and_login_flow(client: TestClient, mailer: FakeEmailSender) -> None:
    register(client)
    assert mailer.outbox[0].to == EMAIL
    assert "/verify-email?token=" in mailer.outbox[0].body

    assert login(client) == 403  # not verified yet

    assert client.post("/api/auth/verify-email", json={"token": token_from(mailer)}).is_success
    assert login(client) == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL
    assert me.json()["email_verified_at"] is not None


def test_session_cookie_is_http_only_and_same_site(
    client: TestClient, mailer: FakeEmailSender
) -> None:
    register_and_verify(client, mailer)

    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    cookie = response.headers["set-cookie"].lower()
    assert "vs_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/api" in cookie


def test_wrong_password_and_unknown_email_look_the_same(
    client: TestClient, mailer: FakeEmailSender
) -> None:
    register_and_verify(client, mailer)

    assert login(client, password="wrong password") == 401
    assert login(client, email="nobody@example.com") == 401


def test_email_is_case_insensitive(client: TestClient, mailer: FakeEmailSender) -> None:
    register(client, email="Reader@Example.COM")
    client.post("/api/auth/verify-email", json={"token": token_from(mailer)})

    assert login(client, email="READER@example.com") == 200


def test_me_requires_login(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_logout_ends_the_session(client: TestClient, mailer: FakeEmailSender) -> None:
    register_and_verify(client, mailer)
    login(client)
    token = client.cookies.get("vs_session")

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    client.cookies.set("vs_session", token or "", path="/api")  # replaying the old cookie fails
    assert client.get("/api/auth/me").status_code == 401


def test_registering_twice_does_not_reveal_the_account(
    client: TestClient, mailer: FakeEmailSender
) -> None:
    register(client)
    register(client)  # same 202 response

    assert len(mailer.outbox) == 2
    assert "already have" in mailer.outbox[1].body


def test_verification_link_works_once(client: TestClient, mailer: FakeEmailSender) -> None:
    register(client)
    token = token_from(mailer)

    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 204
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400


def test_resend_verification_invalidates_the_old_link(
    client: TestClient, mailer: FakeEmailSender
) -> None:
    register(client)
    old = token_from(mailer)

    assert client.post("/api/auth/resend-verification", json={"email": EMAIL}).status_code == 202
    new = token_from(mailer)

    assert client.post("/api/auth/verify-email", json={"token": old}).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": new}).status_code == 204


def test_password_reset_flow_logs_out_everywhere(
    client: TestClient, mailer: FakeEmailSender
) -> None:
    register_and_verify(client, mailer)
    login(client)

    assert client.post("/api/auth/forgot-password", json={"email": EMAIL}).status_code == 202
    token = token_from(mailer)
    assert "/reset-password?token=" in mailer.outbox[-1].body

    new_password = "a brand new passphrase"
    response = client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": new_password}
    )
    assert response.status_code == 204

    assert client.get("/api/auth/me").status_code == 401  # old session revoked
    assert login(client) == 401
    assert login(client, password=new_password) == 200


def test_forgot_password_for_unknown_email_sends_nothing(
    client: TestClient, mailer: FakeEmailSender
) -> None:
    response = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})

    assert response.status_code == 202
    assert mailer.outbox == []


def test_short_passwords_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register", json={"email": EMAIL, "password": "short", "display_name": "R"}
    )

    assert response.status_code == 422


def test_invalid_email_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": PASSWORD, "display_name": "R"},
    )

    assert response.status_code == 422


class BrokenEmailSender:
    def send(self, email: Email) -> None:
        raise ConnectionRefusedError("no mail server")


def test_sign_up_works_when_the_mail_server_is_down(
    client: TestClient, session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """The account is created; the email failure is logged instead of breaking the request."""
    app = client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_email_sender] = BrokenEmailSender

    register(client)  # asserts 202

    assert session.scalars(select(User).where(User.email == EMAIL)).one()
    assert "couldn't send the 'Verify your Vocab Sensei email' email" in caplog.text
    assert (
        client.post("/api/auth/forgot-password", json={"email": "x@example.com"}).status_code == 202
    )
