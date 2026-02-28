"""Amazon India (amazon.in) scraper.

Strategy
--------
Amazon India is server-side rendered so the product data is available in
the initial HTML.  However Amazon is **aggressive with anti-bot detection**:
CAPTCHA pages, 503 throttles, and header fingerprinting.

1. Parse the search results HTML using well-known ``data-*`` attribute
   selectors that are relatively stable across Amazon redesigns.
2. Each result lives inside ``div[data-component-type="s-search-result"]``.

Anti-bot mitigations:
- Realistic Chrome headers with full sec-ch-ua suite
- Referrer set to Amazon homepage
- Cookie jar maintained by the shared httpx client

Selectors last verified: 2026-02-28
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from src.models.product import ProductResult
from src.scrapers.base import BaseScraper
from src.utils.headers import get_headers
from src.utils.helpers import abs_url, encode_query, first_attr, first_text, parse_price

logger = logging.getLogger(__name__)


class AmazonScraper(BaseScraper):
    SITE_NAME = "amazon"
    BASE_URL = "https://www.amazon.in"

    async def search(self, query: str) -> list[ProductResult]:
        encoded = encode_query(query)
        url = f"{self.BASE_URL}/s"
        # Add beauty category filter to improve relevance
        params = {"k": query, "i": "beauty"}
        headers = get_headers(referer=self.BASE_URL)

        resp = await self._get(url, headers=headers, params=params)
        html = resp.text

        # Check for CAPTCHA / bot detection page
        if "captcha" in html.lower() or "robot" in html.lower():
            logger.warning("Amazon returned CAPTCHA page — request likely blocked")
            # Fall back to a simpler URL without category filter
            resp = await self._get(
                f"{self.BASE_URL}/s?k={encoded}",
                headers=get_headers(referer=self.BASE_URL),
            )
            html = resp.text

        return self._parse_results(html)

    def _parse_results(self, html: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "lxml")

        # Primary: data-component-type is Amazon's most stable selector
        cards = soup.select('div[data-component-type="s-search-result"]')

        results: list[ProductResult] = []
        for card in cards:
            # Skip sponsored / ad placements
            if card.select_one('[data-component-type="sp-sponsored-result"]'):
                continue

            result = self._parse_card(card)
            if result:
                results.append(result)
            if len(results) >= self._max_results:
                break

        return results

    def _parse_card(self, card: BeautifulSoup) -> ProductResult | None:
        # --- Title & URL ---
        title_link = card.select_one(
            'h2 a.a-link-normal, '
            'h2 a[class*="a-text-normal"], '
            'a[class*="a-link-normal"][href*="/dp/"]'
        )
        if not title_link:
            return None

        title = first_text(title_link)
        href = first_attr(title_link, "href") or ""
        product_url = abs_url(self.BASE_URL, href) or ""
        if not title or not product_url:
            return None

        # Clean tracking params from URL — keep up to /dp/ASIN
        if "/dp/" in product_url:
            product_url = product_url.split("/ref=")[0]

        # --- Price ---
        # Amazon uses <span class="a-price"> with a <span class="a-offscreen">₹1,299</span>
        price_whole = card.select_one('span.a-price:not([data-a-strike]) span.a-price-whole')
        price_fraction = card.select_one('span.a-price:not([data-a-strike]) span.a-price-fraction')
        price = None
        if price_whole:
            p_text = first_text(price_whole) or "0"
            f_text = first_text(price_fraction) or "00"
            price = parse_price(f"{p_text}.{f_text}")

        # Alternative: offscreen price
        if price is None:
            offscreen = card.select_one('span.a-price:not([data-a-strike]) span.a-offscreen')
            price = parse_price(first_text(offscreen))

        # --- MRP (original / strike-through price) ---
        mrp_tag = card.select_one('span.a-price[data-a-strike] span.a-offscreen')
        original_price = parse_price(first_text(mrp_tag))

        # --- Image ---
        img = card.select_one("img.s-image")
        image_url = first_attr(img, "src")

        # --- In stock ---
        in_stock = True
        oos_tag = card.select_one('[class*="a-color-error"], [class*="out-of-stock"]')
        if oos_tag and "currently unavailable" in (first_text(oos_tag) or "").lower():
            in_stock = False

        return ProductResult(
            product_name=title,
            product_url=product_url,
            image_url=image_url,
            price=price,
            original_price=original_price,
            source=self.SITE_NAME,
            in_stock=in_stock,
        )
