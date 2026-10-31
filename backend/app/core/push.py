"""Sending Web Push notifications. Services depend on the PushSender protocol, so tests can swap
in a fake.

Browsers deliver notifications through their vendor's push service; our server proves who it is
with a VAPID key pair. If no keys are configured, one is created once and kept in the data
directory (`vapid.json`), so subscriptions keep working across restarts.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid, b64urlencode
from pywebpush import WebPushException, webpush

from app.core.config import PushSettings


class SubscriptionGoneError(Exception):
    """The browser unsubscribed or the subscription expired; forget it."""


class PushError(Exception):
    pass


@dataclass(frozen=True)
class PushTarget:
    endpoint: str
    p256dh: str
    auth: str


@dataclass(frozen=True)
class VapidKeys:
    private_pem: str
    public_key: str  # base64url, what the browser needs as `applicationServerKey`


def load_or_create_keys(settings: PushSettings, data_dir: Path) -> VapidKeys:
    if settings.vapid_private_key and settings.vapid_public_key:
        return VapidKeys(settings.vapid_private_key, settings.vapid_public_key)
    path = data_dir / "vapid.json"
    if path.exists():
        stored = json.loads(path.read_text())
        return VapidKeys(stored["private_pem"], stored["public_key"])
    vapid = Vapid()
    vapid.generate_keys()
    public = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    keys = VapidKeys(vapid.private_pem().decode(), b64urlencode(public))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"private_pem": keys.private_pem, "public_key": keys.public_key}))
    path.chmod(0o600)
    return keys


class PushSender(Protocol):
    def send(self, target: PushTarget, payload: dict[str, str]) -> None: ...


class WebPushSender:
    def __init__(self, keys: VapidKeys, subject: str) -> None:
        self._keys = keys
        self._subject = subject

    def send(self, target: PushTarget, payload: dict[str, str]) -> None:
        try:
            webpush(
                subscription_info={
                    "endpoint": target.endpoint,
                    "keys": {"p256dh": target.p256dh, "auth": target.auth},
                },
                data=json.dumps(payload),
                vapid_private_key=self._keys.private_pem,
                vapid_claims={"sub": self._subject},
                timeout=10,
                ttl=12 * 3600,  # a reminder older than half a day is pointless
            )
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                raise SubscriptionGoneError(target.endpoint) from None
            raise PushError(str(exc)) from None
