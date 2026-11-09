"""Who gets the newsletter: only people who chose it, with a verified address."""

from fastapi.testclient import TestClient

from tests.api.test_auth import EMAIL, PASSWORD, login, register_and_verify, token_from
from tests.conftest import FakeEmailSender, FakeNewsletterList


def sign_up(client: TestClient, newsletter: bool) -> None:
    body = {
        "email": EMAIL,
        "password": PASSWORD,
        "display_name": "Reader",
        "newsletter": newsletter,
    }
    assert client.post("/api/auth/register", json=body).status_code == 202


def test_nobody_gets_it_without_choosing(
    client: TestClient, mailer: FakeEmailSender, newsletter: FakeNewsletterList
) -> None:
    register_and_verify(client, mailer)
    login(client)

    assert client.get("/api/auth/me").json()["newsletter"] is False
    assert newsletter.changes == []


def test_ticking_the_box_at_sign_up_subscribes_once_the_address_is_verified(
    client: TestClient, mailer: FakeEmailSender, newsletter: FakeNewsletterList
) -> None:
    sign_up(client, newsletter=True)
    assert newsletter.changes == []  # an unverified address never reaches the list

    assert client.post("/api/auth/verify-email", json={"token": token_from(mailer)}).is_success

    assert newsletter.changes == [("add", EMAIL, "Reader")]
    login(client)
    assert client.get("/api/auth/me").json()["newsletter"] is True


def test_the_settings_switch_subscribes_and_unsubscribes(
    client: TestClient, mailer: FakeEmailSender, newsletter: FakeNewsletterList
) -> None:
    register_and_verify(client, mailer)
    login(client)

    on = client.put("/api/auth/me/newsletter", json={"subscribe": True})
    again = client.put("/api/auth/me/newsletter", json={"subscribe": True})
    off = client.put("/api/auth/me/newsletter", json={"subscribe": False})

    assert on.json()["newsletter"] is True
    assert again.is_success
    assert off.json()["newsletter"] is False
    assert newsletter.changes == [("add", EMAIL, "Reader"), ("remove", EMAIL)]


def test_a_new_email_address_replaces_the_old_one_on_the_list(
    client: TestClient, mailer: FakeEmailSender, newsletter: FakeNewsletterList
) -> None:
    register_and_verify(client, mailer)
    login(client)
    client.put("/api/auth/me/newsletter", json={"subscribe": True})
    new = "new@example.com"
    body = {"email": new, "password": PASSWORD}
    assert client.post("/api/auth/me/email", json=body).status_code == 202

    assert client.post("/api/auth/confirm-email", json={"token": token_from(mailer)}).is_success

    assert newsletter.changes[-2:] == [("remove", EMAIL), ("add", new, "Reader")]


def test_deleting_the_account_removes_the_address(
    client: TestClient, mailer: FakeEmailSender, newsletter: FakeNewsletterList
) -> None:
    register_and_verify(client, mailer)
    login(client)

    response = client.request("DELETE", "/api/auth/me", json={"password": PASSWORD})

    assert response.status_code == 204
    assert newsletter.changes == [("remove", EMAIL)]
