"""Per-client request limits for endpoints that attract abuse (logins, sign-ups, email sending).

Counts live where `rate_limit.storage_uri` says: in memory for a single process (development,
tests), or in Valkey ("valkey://valkey:6379") when the API runs several worker processes, so they
all share one count instead of each allowing the full limit. Behind a proxy the visitor's address
is read from `CF-Connecting-IP` or `X-Forwarded-For`, but only when `rate_limit.trust_proxy` says
a proxy is really in front (otherwise anyone could send that header to dodge the limit).
"""

import math
import time
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from limits import parse
from limits.storage import Storage, storage_from_string
from limits.strategies import MovingWindowRateLimiter

from app.api.deps import SettingsDep
from app.core.config import RateLimitSettings

_storages: dict[str, Storage] = {}


def _limiter(storage_uri: str) -> MovingWindowRateLimiter:
    """One storage per address, connected on first use and kept for the life of the process."""
    if storage_uri not in _storages:
        storage = storage_from_string(storage_uri)
        if not isinstance(storage, Storage):  # "async+..." addresses give an asyncio storage
            raise ValueError(f"rate_limit.storage_uri needs a synchronous storage: {storage_uri}")
        _storages[storage_uri] = storage
    return MovingWindowRateLimiter(_storages[storage_uri])


def reset() -> None:
    """Forget all counts (tests start from a clean slate)."""
    for storage in _storages.values():
        storage.reset()


def client_address(request: Request, settings: RateLimitSettings) -> str:
    if settings.trust_proxy:
        forwarded = request.headers.get("cf-connecting-ip") or request.headers.get(
            "x-forwarded-for"
        )
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limited(name: str, limit: Callable[[RateLimitSettings], str]) -> object:
    """A dependency that allows `limit(settings)` (e.g. "10/minute") requests per client."""

    def check(request: Request, settings: SettingsDep) -> None:
        config = settings.rate_limit
        if not config.enabled:
            return
        item = parse(limit(config))
        key = client_address(request, config)
        limiter = _limiter(config.storage_uri)
        if not limiter.hit(item, name, key):
            reset_at = limiter.get_window_stats(item, name, key).reset_time
            wait = max(1, math.ceil(reset_at - time.time()))
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Too many attempts. Please wait {_describe(wait)} and try again.",
                headers={"Retry-After": str(wait)},
            )

    return Depends(check)


def _describe(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} seconds"
    minutes = math.ceil(seconds / 60)
    return "a minute" if minutes == 1 else f"{minutes} minutes"


LoginLimit = Annotated[None, rate_limited("login", lambda c: c.login)]
EmailLimit = Annotated[None, rate_limited("email", lambda c: c.email)]
