"""Abstract base class for all site scrapers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from src.models.product import ProductResult
from src.utils.exceptions import BlockedError, NetworkError, RateLimitError
from src.utils.headers import get_headers
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Every site-specific scraper must subclass this and implement ``search``."""

    # Subclasses must set these
    SITE_NAME: str = ""
    BASE_URL: str = ""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        rate_limiter: RateLimiter,
        max_results: int = 3,
    ) -> None:
        self._client = client
        self._rate_limiter = rate_limiter
        self._max_results = max_results

    # ------------------------------------------------------------------
    # Abstract
    # ------------------------------------------------------------------

    @abstractmethod
    async def search(self, query: str) -> list[ProductResult]:
        """Search for *query* and return up to ``max_results`` products."""
        ...

    # ------------------------------------------------------------------
    # HTTP helpers available to subclasses
    # ------------------------------------------------------------------

    async def _get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        follow_redirects: bool = True,
    ) -> httpx.Response:
        """Rate-limited GET request with anti-detection headers and error mapping."""
        await self._rate_limiter.acquire(self.SITE_NAME)

        req_headers = headers or get_headers(referer=self.BASE_URL)
        try:
            resp = await self._client.get(
                url,
                headers=req_headers,
                params=params,
                follow_redirects=follow_redirects,
            )
        except httpx.TransportError as exc:
            raise NetworkError(self.SITE_NAME, str(exc)) from exc

        if resp.status_code == 429:
            raise RateLimitError(self.SITE_NAME, "429 Too Many Requests")
        if resp.status_code == 403:
            raise BlockedError(self.SITE_NAME, "403 Forbidden — likely blocked")
        if resp.status_code >= 400:
            raise NetworkError(self.SITE_NAME, f"HTTP {resp.status_code}")

        return resp
