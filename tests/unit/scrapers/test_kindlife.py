"""Tests for the Kindlife (Shopify) scraper using fixture data."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from src.scrapers.kindlife import KindlifeScraper
from src.utils.rate_limiter import RateLimiter

KINDLIFE_SUGGEST_JSON = {
    "resources": {
        "results": {
            "products": [
                {
                    "title": "The Derma Co Hyaluronic Sunscreen",
                    "handle": "derma-co-hyaluronic-sunscreen",
                    "url": "/products/derma-co-hyaluronic-sunscreen",
                    "image": "https://cdn.shopify.com/test.jpg",
                    "price": 499.0,
                    "compare_at_price": 599.0,
                },
                {
                    "title": "Plum Green Tea Face Wash",
                    "handle": "plum-green-tea-face-wash",
                    "url": "/products/plum-green-tea-face-wash",
                    "image": "https://cdn.shopify.com/test2.jpg",
                    "price": 345.0,
                    "compare_at_price": None,
                },
            ]
        }
    }
}


@pytest.mark.asyncio()
async def test_kindlife_suggest_api(respx_mock: respx.MockRouter) -> None:
    """Test Shopify suggest.json parsing."""
    respx_mock.get("https://kindlife.in/search/suggest.json").mock(
        return_value=httpx.Response(200, json=KINDLIFE_SUGGEST_JSON)
    )
    rl = RateLimiter(delay_seconds=0)
    async with httpx.AsyncClient() as client:
        scraper = KindlifeScraper(client=client, rate_limiter=rl, max_results=5)
        results = await scraper.search("sunscreen")

    assert len(results) == 2
    assert results[0].product_name == "The Derma Co Hyaluronic Sunscreen"
    assert results[0].price == 499.0
    assert results[0].original_price == 599.0
    assert results[0].source == "kindlife"
    assert "/products/derma-co-hyaluronic-sunscreen" in results[0].product_url
