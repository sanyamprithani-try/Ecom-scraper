"""Kindlife (kindlife.in) scraper.

Strategy
--------
Kindlife is a **Shopify-based** clean beauty e-commerce platform.
Shopify stores expose a standard search suggest API:

    ``GET /search/suggest.json?q=…&resources[type]=product&resources[limit]=…``

This returns a JSON payload with product titles, URLs, images and prices
— no HTML parsing needed.

1. Primary: Shopify ``suggest.json`` API (fastest, most reliable).
2. Fallback: Shopify ``search?q=…&type=product`` HTML page with standard
   Shopify product-card markup.

Selectors last verified: 2026-02-28
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from src.models.product import ProductResult
from src.scrapers.base import BaseScraper
from src.utils.headers import get_api_headers, get_headers
from src.utils.helpers import abs_url, encode_query, first_attr, first_text, parse_price

logger = logging.getLogger(__name__)


class KindlifeScraper(BaseScraper):
    SITE_NAME = "kindlife"
    BASE_URL = "https://kindlife.in"

    async def search(self, query: str) -> list[ProductResult]:
        # Strategy 1: Shopify search suggest API
        try:
            return await self._search_suggest(query)
        except Exception:
            logger.debug("Kindlife suggest API failed, falling back to HTML", exc_info=True)

        # Strategy 2: HTML search page
        return await self._search_html(query)

    # ------------------------------------------------------------------
    # Strategy 1 – Shopify suggest.json
    # ------------------------------------------------------------------

    async def _search_suggest(self, query: str) -> list[ProductResult]:
        url = f"{self.BASE_URL}/search/suggest.json"
        params = {
            "q": query,
            "resources[type]": "product",
            "resources[limit]": str(self._max_results),
            "resources[options][unavailable_products]": "last",
        }
        headers = get_api_headers(referer=f"{self.BASE_URL}/search?q={encode_query(query)}")

        resp = await self._get(url, headers=headers, params=params)
        data = resp.json()

        products_raw = (
            data.get("resources", {}).get("results", {}).get("products", [])
        )

        results: list[ProductResult] = []
        for item in products_raw[: self._max_results]:
            title = item.get("title", "")
            handle = item.get("handle") or item.get("url") or ""
            product_url = abs_url(self.BASE_URL, f"/products/{handle}") if handle and not handle.startswith("/") else abs_url(self.BASE_URL, handle)
            product_url = product_url or ""

            image = item.get("image") or item.get("featured_image", {}).get("url", "")
            # Shopify featured_image can be a dict or a string
            if isinstance(image, dict):
                image = image.get("url") or image.get("src") or ""

            price = item.get("price")
            # Shopify prices are in cents in some locales
            if isinstance(price, (int, float)) and price > 10000:
                price = price / 100
            compare_price = item.get("compare_at_price")
            if isinstance(compare_price, (int, float)) and compare_price > 10000:
                compare_price = compare_price / 100

            if not title:
                continue

            results.append(
                ProductResult(
                    product_name=title,
                    product_url=product_url,
                    image_url=image or None,
                    price=float(price) if price else None,
                    original_price=float(compare_price) if compare_price else None,
                    source=self.SITE_NAME,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Strategy 2 – HTML search page
    # ------------------------------------------------------------------

    async def _search_html(self, query: str) -> list[ProductResult]:
        url = f"{self.BASE_URL}/search"
        params = {"q": query, "type": "product"}
        resp = await self._get(url, headers=get_headers(referer=self.BASE_URL), params=params)
        return self._parse_html(resp.text)

    def _parse_html(self, html: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "lxml")
        # Standard Shopify product card selectors
        cards = soup.select(
            'div.product-card, '
            'div[class*="product-card"], '
            'div[class*="grid-product"], '
            'li[class*="product"]'
        )
        if not cards:
            cards = soup.select('a[href*="/products/"]')

        results: list[ProductResult] = []
        seen: set[str] = set()
        for card in cards:
            link = card if card.name == "a" else card.select_one('a[href*="/products/"]')
            href = first_attr(link, "href") or ""
            product_url = abs_url(self.BASE_URL, href) or ""
            if not product_url or product_url in seen:
                continue
            seen.add(product_url)

            title_tag = card.select_one(
                '[class*="product-card__title"], '
                '[class*="product-title"], '
                '[class*="grid-product__title"], '
                'h3, h2'
            )
            price_tag = card.select_one('[class*="price"], [class*="Price"]')
            img = card.select_one("img")

            title = first_text(title_tag) or first_attr(link, "title") or ""
            if not title:
                continue

            results.append(
                ProductResult(
                    product_name=title,
                    product_url=product_url,
                    image_url=first_attr(img, "src") or first_attr(img, "data-src"),
                    price=parse_price(first_text(price_tag)),
                    source=self.SITE_NAME,
                )
            )
            if len(results) >= self._max_results:
                break
        return results
