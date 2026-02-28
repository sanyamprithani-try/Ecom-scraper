"""Shared test fixtures."""

from __future__ import annotations

import pytest
import httpx

from src.utils.rate_limiter import RateLimiter


@pytest.fixture()
def rate_limiter() -> RateLimiter:
    """A rate limiter with zero delay for fast tests."""
    return RateLimiter(delay_seconds=0.0)


@pytest.fixture()
def mock_client(respx_mock) -> httpx.AsyncClient:  # noqa: ANN001
    """An httpx client wired to respx for mocking."""
    return httpx.AsyncClient()
