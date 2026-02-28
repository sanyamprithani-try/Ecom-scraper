"""Per-domain async rate limiter."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple per-domain token-bucket rate limiter.

    Ensures a minimum gap of ``delay_seconds`` between consecutive
    requests to the same domain.
    """

    def __init__(self, delay_seconds: float = 1.0) -> None:
        self._delay = delay_seconds
        self._last_request: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, domain: str) -> None:
        """Wait until the rate limit window has passed for *domain*."""
        async with self._locks[domain]:
            elapsed = time.monotonic() - self._last_request[domain]
            wait = self._delay - elapsed
            if wait > 0:
                logger.debug("Rate-limiting %s — sleeping %.2fs", domain, wait)
                await asyncio.sleep(wait)
            self._last_request[domain] = time.monotonic()
