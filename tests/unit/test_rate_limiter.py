"""Tests for the per-domain rate limiter."""

from __future__ import annotations

import asyncio
import time

import pytest

from src.utils.rate_limiter import RateLimiter


@pytest.mark.asyncio()
async def test_rate_limiter_enforces_delay() -> None:
    rl = RateLimiter(delay_seconds=0.2)

    start = time.monotonic()
    await rl.acquire("example.com")
    await rl.acquire("example.com")
    elapsed = time.monotonic() - start

    # Second acquire should have waited ~0.2s
    assert elapsed >= 0.15


@pytest.mark.asyncio()
async def test_different_domains_not_blocked() -> None:
    rl = RateLimiter(delay_seconds=0.5)

    start = time.monotonic()
    await rl.acquire("site-a.com")
    await rl.acquire("site-b.com")
    elapsed = time.monotonic() - start

    # Different domains should not block each other
    assert elapsed < 0.3
