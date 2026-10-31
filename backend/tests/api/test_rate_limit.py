import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings

LOGIN = {"email": "nobody@example.com", "password": "wrong password!"}


def test_too_many_logins_are_refused_for_a_while(client: TestClient, settings: Settings) -> None:
    settings.rate_limit.login = "3/minute"

    codes = [client.post("/api/auth/login", json=LOGIN).status_code for _ in range(4)]

    assert codes == [401, 401, 401, 429]
    refused = client.post("/api/auth/login", json=LOGIN)
    assert refused.json()["detail"].startswith("Too many attempts. Please wait")
    assert 0 < int(refused.headers["retry-after"]) <= 60


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (
            "/api/auth/register",
            {"email": "a@example.com", "password": "x" * 12, "display_name": "A"},
        ),
        ("/api/auth/resend-verification", {"email": "a@example.com"}),
        ("/api/auth/forgot-password", {"email": "a@example.com"}),
    ],
)
def test_emails_are_limited(
    client: TestClient, settings: Settings, path: str, body: dict[str, str]
) -> None:
    settings.rate_limit.email = "2/hour"

    codes = [client.post(path, json=body).status_code for _ in range(3)]

    assert codes == [202, 202, 429]


def test_limits_count_per_client(client: TestClient, settings: Settings) -> None:
    settings.rate_limit.login = "1/minute"
    settings.rate_limit.trust_proxy = True

    first = client.post("/api/auth/login", json=LOGIN, headers={"CF-Connecting-IP": "203.0.113.1"})
    other = client.post("/api/auth/login", json=LOGIN, headers={"CF-Connecting-IP": "203.0.113.2"})
    again = client.post("/api/auth/login", json=LOGIN, headers={"CF-Connecting-IP": "203.0.113.1"})

    assert (first.status_code, other.status_code, again.status_code) == (401, 401, 429)


def test_proxy_headers_are_ignored_unless_trusted(client: TestClient, settings: Settings) -> None:
    settings.rate_limit.login = "1/minute"

    client.post("/api/auth/login", json=LOGIN, headers={"CF-Connecting-IP": "203.0.113.1"})
    dodged = client.post("/api/auth/login", json=LOGIN, headers={"CF-Connecting-IP": "203.0.113.9"})

    assert dodged.status_code == 429  # a made-up header doesn't give a fresh allowance


def test_limits_can_be_switched_off(client: TestClient, settings: Settings) -> None:
    settings.rate_limit.login = "1/minute"
    settings.rate_limit.enabled = False

    codes = {client.post("/api/auth/login", json=LOGIN).status_code for _ in range(3)}

    assert codes == {401}
