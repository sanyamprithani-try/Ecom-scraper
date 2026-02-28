"""Tests for the Amazon scraper using fixture HTML."""

from __future__ import annotations

import pytest
import httpx
import respx

from src.scrapers.amazon import AmazonScraper
from src.utils.rate_limiter import RateLimiter

# Minimal Amazon-like search result HTML for offline testing
AMAZON_FIXTURE_HTML = """
<html><body>
<div data-component-type="s-search-result" data-asin="B09XYZ123">
  <h2>
    <a class="a-link-normal" href="/dp/B09XYZ123/ref=sr_1_1?keywords=lipstick">
      <span>Maybelline New York Super Stay Matte Ink Liquid Lipstick</span>
    </a>
  </h2>
  <span class="a-price" data-a-size="xl">
    <span class="a-offscreen">₹549</span>
    <span><span class="a-price-whole">549</span><span class="a-price-fraction">00</span></span>
  </span>
  <span class="a-price" data-a-strike="true">
    <span class="a-offscreen">₹699</span>
  </span>
  <img class="s-image" src="https://m.media-amazon.com/images/I/test.jpg" />
</div>
<div data-component-type="s-search-result" data-asin="B08ABC456">
  <h2>
    <a class="a-link-normal" href="/dp/B08ABC456/ref=sr_1_2?keywords=lipstick">
      <span>Lakme 9 to 5 Primer + Matte Lip Color</span>
    </a>
  </h2>
  <span class="a-price">
    <span class="a-offscreen">₹299</span>
    <span><span class="a-price-whole">299</span><span class="a-price-fraction">00</span></span>
  </span>
  <img class="s-image" src="https://m.media-amazon.com/images/I/test2.jpg" />
</div>
</body></html>
"""


@pytest.mark.asyncio()
async def test_amazon_parse_results() -> None:
    """Verify Amazon HTML parsing extracts products correctly."""
    rl = RateLimiter(delay_seconds=0)
    async with httpx.AsyncClient() as client:
        scraper = AmazonScraper(client=client, rate_limiter=rl, max_results=5)
        results = scraper._parse_results(AMAZON_FIXTURE_HTML)

    assert len(results) == 2

    first = results[0]
    assert "Maybelline" in first.product_name
    assert first.price == 549.0
    assert first.original_price == 699.0
    assert first.source == "amazon"
    assert "/dp/B09XYZ123" in first.product_url
    assert first.image_url is not None

    second = results[1]
    assert "Lakme" in second.product_name
    assert second.price == 299.0


@pytest.mark.asyncio()
async def test_amazon_search_integration(respx_mock: respx.MockRouter) -> None:
    """Test full search flow with mocked HTTP."""
    respx_mock.get("https://www.amazon.in/s").mock(
        return_value=httpx.Response(200, text=AMAZON_FIXTURE_HTML)
    )
    rl = RateLimiter(delay_seconds=0)
    async with httpx.AsyncClient() as client:
        scraper = AmazonScraper(client=client, rate_limiter=rl, max_results=5)
        results = await scraper.search("lipstick")

    assert len(results) == 2
    assert results[0].source == "amazon"
