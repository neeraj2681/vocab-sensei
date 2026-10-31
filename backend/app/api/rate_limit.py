"""Per-client request limits for endpoints that attract abuse (logins, sign-ups, email sending).

Counts live in memory: fine for the single server process this app runs as. Behind Cloudflare
Tunnel every request arrives from the tunnel, so the visitor's address is read from
`CF-Connecting-IP`, but only when `rate_limit.trust_proxy` says a proxy is really in front
(otherwise anyone could send that header to dodge the limit).
"""

import math
import time
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.api.deps import SettingsDep
from app.core.config import RateLimitSettings

_storage = MemoryStorage()
_limiter = MovingWindowRateLimiter(_storage)


def reset() -> None:
    """Forget all counts (tests start from a clean slate)."""
    _storage.reset()


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
        if not _limiter.hit(item, name, key):
            reset_at = _limiter.get_window_stats(item, name, key).reset_time
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
