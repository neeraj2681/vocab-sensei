"""The newsletter's mailing list, kept in Brevo.

Newsletters are written and sent in Brevo (its campaign editor adds the unsubscribe link). The app
only keeps Brevo's list matching who has subscribed: signed-in users whose address is verified.
Without a Brevo API key and list (development, tests) nothing leaves the app.
"""

import logging
from typing import Protocol
from urllib.parse import quote

import httpx

from app.core.config import NewsletterSettings

logger = logging.getLogger(__name__)


class NewsletterList(Protocol):
    def add(self, email: str, name: str) -> None:
        """Subscribes the address (or updates its name); re-subscribes it if it had left."""
        ...

    def remove(self, email: str) -> None:
        """Forgets the address entirely; nothing happens if it isn't there."""
        ...


class NoNewsletterList:
    """Used when Brevo isn't set up: the change is logged and goes nowhere else."""

    def add(self, email: str, name: str) -> None:
        logger.info("newsletter not set up: would add %s", email)

    def remove(self, email: str) -> None:
        logger.info("newsletter not set up: would remove %s", email)


class BrevoNewsletterList:
    def __init__(
        self, api_key: str, list_id: int, api_url: str, client: httpx.Client | None = None
    ) -> None:
        self._list_id = list_id
        self._client = client or httpx.Client(timeout=10)
        self._url = api_url.rstrip("/")
        self._headers = {"api-key": api_key, "accept": "application/json"}

    def add(self, email: str, name: str) -> None:
        response = self._client.post(
            f"{self._url}/contacts",
            headers=self._headers,
            json={
                "email": email,
                "attributes": {"FIRSTNAME": name},
                "listIds": [self._list_id],
                "updateEnabled": True,  # already a contact: update it instead of failing
                "emailBlacklisted": False,  # subscribing again after unsubscribing in an email
            },
        )
        response.raise_for_status()

    def remove(self, email: str) -> None:
        response = self._client.delete(
            f"{self._url}/contacts/{quote(email, safe='')}", headers=self._headers
        )
        if response.status_code != httpx.codes.NOT_FOUND:
            response.raise_for_status()


def newsletter_list(settings: NewsletterSettings) -> NewsletterList:
    if settings.brevo_api_key and settings.brevo_list_id:
        return BrevoNewsletterList(
            settings.brevo_api_key, settings.brevo_list_id, settings.brevo_api_url
        )
    return NoNewsletterList()
