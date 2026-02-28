"""Sephora India (sephora.in) scraper.

Strategy
--------
Sephora globally uses **Algolia** as their search backend.  The Indian
site exposes a search API that returns JSON results.

1. Primary: Call the Sephora search API endpoint.
2. Fallback: Parse HTML search results page for product cards.

Selectors last verified: 2026-02-28
"""

from __future__ import annotations

import json
import logging

from bs4 import BeautifulSoup

from src.models.product import ProductResult
from src.scrapers.base import BaseScraper
from src.utils.headers import get_api_headers, get_headers
from src.utils.helpers import abs_url, encode_query, first_attr, first_text, parse_price

logger = logging.getLogger(__name__)


class SephoraScraper(BaseScraper):
    SITE_NAME = "sephora"
    BASE_URL = "https://www.sephora.in"

    async def search(self, query: str) -> list[ProductResult]:
        try:
            return await self._search_api(query)
        except Exception:
            logger.debug("Sephora API strategy failed, falling back to HTML", exc_info=True)
        return await self._search_html(query)

    # ------------------------------------------------------------------
    # Strategy 1 – search API
    # ------------------------------------------------------------------

    async def _search_api(self, query: str) -> list[ProductResult]:
        url = f"{self.BASE_URL}/api/v2/search"
        params = {"q": query, "page": "0", "size": str(self._max_results)}
        headers = get_api_headers(referer=f"{self.BASE_URL}/search?q={encode_query(query)}")

        resp = await self._get(url, headers=headers, params=params)
        data = resp.json()

        products_raw = (
            data.get("data", {}).get("products")
            or data.get("products")
            or data.get("hits", [])
        )

        results: list[ProductResult] = []
        for item in products_raw[: self._max_results]:
            title = item.get("name") or item.get("title") or item.get("productName", "")
            slug = item.get("url") or item.get("slug") or ""
            product_url = abs_url(self.BASE_URL, slug) or ""
            image = item.get("image") or item.get("imageUrl") or item.get("heroImage", "")

            price = item.get("price") or item.get("sellingPrice")
            mrp = item.get("mrp") or item.get("listPrice")

            if not title:
                continue

            results.append(
                ProductResult(
                    product_name=title,
                    product_url=product_url,
                    image_url=image or None,
                    price=float(price) if price else None,
                    original_price=float(mrp) if mrp else None,
                    source=self.SITE_NAME,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Strategy 2 – HTML parse
    # ------------------------------------------------------------------

    async def _search_html(self, query: str) -> list[ProductResult]:
        url = f"{self.BASE_URL}/search?q={encode_query(query)}"
        resp = await self._get(url, headers=get_headers(referer=self.BASE_URL))
        html = resp.text

        # Sephora often embeds JSON-LD or Algolia state in the page
        results = self._try_embedded_json(html)
        if results:
            return results

        return self._parse_html_cards(html)

    def _try_embedded_json(self, html: str) -> list[ProductResult]:
        """Try to extract product data from embedded JSON-LD or state scripts."""
        soup = BeautifulSoup(html, "lxml")
        results: list[ProductResult] = []

        # Look for JSON-LD product data
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for item in data:
                        result = self._json_ld_to_product(item)
                        if result:
                            results.append(result)
                elif isinstance(data, dict):
                    result = self._json_ld_to_product(data)
                    if result:
                        results.append(result)
            except json.JSONDecodeError:
                continue

        return results[: self._max_results]

    def _json_ld_to_product(self, data: dict) -> ProductResult | None:
        if data.get("@type") != "Product":
            return None
        title = data.get("name", "")
        url = data.get("url") or data.get("offers", {}).get("url", "")
        image = data.get("image", "")
        if isinstance(image, list):
            image = image[0] if image else ""
        offers = data.get("offers", {})
        price = offers.get("price") or offers.get("lowPrice")
        if not title:
            return None
        return ProductResult(
            product_name=title,
            product_url=abs_url(self.BASE_URL, url) or "",
            image_url=image or None,
            price=float(price) if price else None,
            source=self.SITE_NAME,
        )

    def _parse_html_cards(self, html: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select(
            'div[class*="product-card"], div[class*="ProductCard"], '
            'div[class*="product-tile"], a[class*="product"]'
        )
        if not cards:
            cards = soup.select('a[href*="/product/"]')

        results: list[ProductResult] = []
        seen: set[str] = set()
        for card in cards:
            link = card if card.name == "a" else card.select_one("a[href]")
            href = first_attr(link, "href") or ""
            product_url = abs_url(self.BASE_URL, href) or ""
            if not product_url or product_url in seen:
                continue
            seen.add(product_url)

            title_tag = card.select_one('[class*="name"], [class*="title"]')
            price_tag = card.select_one('[class*="price"]')
            img = card.select_one("img")

            title = first_text(title_tag) or ""
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
