"""Proxy rotation manager.

Reads proxy configuration from environment variables.  Supports:
- A single proxy URL (``PROXY_URL``)
- A file containing one proxy per line (``PROXY_LIST_FILE``)

When multiple proxies are available they are rotated round-robin and
unhealthy proxies are temporarily removed from the pool.
"""

from __future__ import annotations

import itertools
import logging
import os
import threading

import httpx

logger = logging.getLogger(__name__)

# Number of consecutive failures before a proxy is marked unhealthy
_MAX_FAILURES = 3


class ProxyManager:
    """Thread-safe proxy pool with round-robin rotation."""

    def __init__(self) -> None:
        self._proxies: list[str] = []
        self._failures: dict[str, int] = {}
        self._cycle: itertools.cycle[str] | None = None
        self._lock = threading.Lock()
        self._load()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _load(self) -> None:
        proxy_url = os.getenv("PROXY_URL", "").strip()
        proxy_file = os.getenv("PROXY_LIST_FILE", "").strip()

        if proxy_file and os.path.isfile(proxy_file):
            with open(proxy_file) as fh:
                self._proxies = [line.strip() for line in fh if line.strip()]
            logger.info("Loaded %d proxies from %s", len(self._proxies), proxy_file)
        elif proxy_url:
            self._proxies = [proxy_url]
            logger.info("Using single proxy from PROXY_URL")

        if self._proxies:
            self._cycle = itertools.cycle(self._proxies)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return bool(self._proxies)

    def get_proxy(self) -> str | None:
        """Return the next healthy proxy URL, or *None* if none available."""
        if not self._cycle:
            return None

        with self._lock:
            # Try up to len(proxies) times to find a healthy one
            for _ in range(len(self._proxies)):
                proxy = next(self._cycle)
                if self._failures.get(proxy, 0) < _MAX_FAILURES:
                    return proxy
        logger.warning("All proxies are unhealthy")
        return None

    def get_transport(self) -> httpx.AsyncHTTPTransport | None:
        """Return an httpx transport configured with the next proxy."""
        proxy = self.get_proxy()
        if proxy is None:
            return None
        return httpx.AsyncHTTPTransport(proxy=proxy)

    def report_success(self, proxy: str) -> None:
        with self._lock:
            self._failures[proxy] = 0

    def report_failure(self, proxy: str) -> None:
        with self._lock:
            self._failures[proxy] = self._failures.get(proxy, 0) + 1
            if self._failures[proxy] >= _MAX_FAILURES:
                logger.warning("Proxy marked unhealthy after %d failures: %s", _MAX_FAILURES, proxy[:30] + "…")
