import json

import httpx
import pytest

from app.core.config import NewsletterSettings, Settings
from app.core.newsletter import BrevoNewsletterList, NoNewsletterList, newsletter_list

API = "https://brevo.test/v3"


def brevo(status: int, seen: list[httpx.Request]) -> BrevoNewsletterList:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status)

    client = httpx.Client(transport=httpx.MockTransport(handle))
    return BrevoNewsletterList("secret-key", 7, API, client)


def test_adding_puts_the_contact_on_the_list() -> None:
    seen: list[httpx.Request] = []

    brevo(201, seen).add("reader@example.com", "Reader")

    [request] = seen
    assert (request.method, str(request.url)) == ("POST", f"{API}/contacts")
    assert request.headers["api-key"] == "secret-key"
    assert json.loads(request.content) == {
        "email": "reader@example.com",
        "attributes": {"FIRSTNAME": "Reader"},
        "listIds": [7],
        "updateEnabled": True,
        "emailBlacklisted": False,
    }


def test_removing_deletes_the_contact_and_a_missing_one_is_fine() -> None:
    seen: list[httpx.Request] = []

    brevo(404, seen).remove("a+b@example.com")

    [request] = seen
    assert (request.method, str(request.url)) == ("DELETE", f"{API}/contacts/a%2Bb%40example.com")


def test_brevo_errors_are_raised() -> None:
    with pytest.raises(httpx.HTTPStatusError):
        brevo(500, []).add("reader@example.com", "Reader")


def test_without_a_key_and_list_nothing_goes_to_brevo() -> None:
    assert isinstance(newsletter_list(NewsletterSettings()), NoNewsletterList)
    assert isinstance(newsletter_list(NewsletterSettings(brevo_api_key="k")), NoNewsletterList)
    configured = NewsletterSettings(brevo_api_key="k", brevo_list_id=3)
    assert isinstance(newsletter_list(configured), BrevoNewsletterList)


def test_empty_settings_in_the_env_file_mean_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOCAB_NEWSLETTER__BREVO_API_KEY", "")
    monkeypatch.setenv("VOCAB_NEWSLETTER__BREVO_LIST_ID", "")

    assert Settings().newsletter == NewsletterSettings()
