"""Myntra (myntra.com) scraper.

Strategy
--------
Myntra is a **heavily JS-rendered React SPA**.  The server returns
a shell HTML page and all content is hydrated client-side.

1. Primary: Hit Myntra's internal search gateway API that returns JSON.
   ``GET /gateway/v2/search/<query>?p=1&rows=…&o=0``
2. Fallback: Load the search HTML and extract data from the embedded
   ``window.__myx`` or ``__PRELOADED_STATE__`` JavaScript variables.

Myntra has moderate anti-bot protections — rotating user agents and
realistic headers are usually sufficient.

Selectors last verified: 2026-02-28
"""

from __future__ import annotations

import json
import logging
import re

from bs4 import BeautifulSoup

from src.models.product import ProductResult
from src.scrapers.base import BaseScraper
from src.utils.headers import get_api_headers, get_headers
from src.utils.helpers import abs_url, encode_query, first_attr, first_text, parse_price

logger = logging.getLogger(__name__)


class MyntraScraper(BaseScraper):
    SITE_NAME = "myntra"
    BASE_URL = "https://www.myntra.com"

    async def search(self, query: str) -> list[ProductResult]:
        # Strategy 1: internal search API
        try:
            return await self._search_api(query)
        except Exception:
            logger.debug("Myntra API strategy failed", exc_info=True)

        # Strategy 2: HTML with embedded state
        return await self._search_html(query)

    # ------------------------------------------------------------------
    # Strategy 1 – internal search API
    # ------------------------------------------------------------------

    async def _search_api(self, query: str) -> list[ProductResult]:
        # Myntra's search gateway
        search_term = query.replace(" ", "-").lower()
        url = f"{self.BASE_URL}/gateway/v2/search/{search_term}"
        params = {"p": "1", "rows": str(self._max_results), "o": "0", "plaEnabled": "false"}
        headers = get_api_headers(referer=f"{self.BASE_URL}/{search_term}")

        resp = await self._get(url, headers=headers, params=params)
        data = resp.json()

        products_raw = data.get("products") or data.get("results") or []

        results: list[ProductResult] = []
        for item in products_raw[: self._max_results]:
            title = item.get("name") or item.get("productName", "")
            brand = item.get("brand") or ""
            full_title = f"{brand} {title}".strip() if brand else title
            product_id = item.get("productId") or item.get("id") or ""
            landing = item.get("landingPageUrl") or ""

            if landing:
                product_url = abs_url(self.BASE_URL, landing) or ""
            elif product_id:
                product_url = f"{self.BASE_URL}/{product_id}"
            else:
                continue

            # Myntra image URLs
            images = item.get("images") or item.get("searchImage") or ""
            if isinstance(images, list):
                image = images[0].get("src", "") if images else ""
            else:
                image = str(images)

            price = item.get("price") or item.get("discountedPrice")
            mrp = item.get("mrp") or item.get("strikedPrice")

            if not full_title:
                continue

            results.append(
                ProductResult(
                    product_name=full_title,
                    product_url=product_url,
                    image_url=image or None,
                    price=float(price) if price else None,
                    original_price=float(mrp) if mrp else None,
                    source=self.SITE_NAME,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Strategy 2 – HTML with embedded JS state
    # ------------------------------------------------------------------

    async def _search_html(self, query: str) -> list[ProductResult]:
        search_term = query.replace(" ", "-").lower()
        url = f"{self.BASE_URL}/{search_term}"
        resp = await self._get(url, headers=get_headers(referer=self.BASE_URL))
        html = resp.text
        return self._extract_from_html(html)

    def _extract_from_html(self, html: str) -> list[ProductResult]:
        """Extract product data from Myntra's embedded JavaScript state."""
        # Myntra often embeds search results in a window.__myx or
        # __PRELOADED_STATE__ variable
        patterns = [
            r'window\.__myx\s*=\s*(\{.*?\});',
            r'__PRELOADED_STATE__\s*=\s*(\{.*?\});',
            r'"searchData"\s*:\s*(\{.*?"products"\s*:\s*\[.*?\]\})',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    products = self._dig_products(data)
                    if products:
                        return products
                except (json.JSONDecodeError, KeyError):
                    continue

        # Final fallback — parse whatever HTML cards exist
        return self._parse_html_cards(html)

    def _dig_products(self, data: dict) -> list[ProductResult]:
        """Recursively find a 'products' array in the state object."""
        if "products" in data and isinstance(data["products"], list):
            raw = data["products"]
        elif "searchData" in data:
            raw = data["searchData"].get("products", [])
        else:
            return []

        results: list[ProductResult] = []
        for item in raw[: self._max_results]:
            title = item.get("name") or item.get("productName", "")
            brand = item.get("brand", "")
            full_title = f"{brand} {title}".strip() if brand else title
            landing = item.get("landingPageUrl") or ""
            product_url = abs_url(self.BASE_URL, landing) or ""
            image = item.get("searchImage") or ""

            if not full_title:
                continue
            results.append(
                ProductResult(
                    product_name=full_title,
                    product_url=product_url,
                    image_url=image or None,
                    price=parse_price(str(item.get("price", item.get("discountedPrice", "")))),
                    original_price=parse_price(str(item.get("mrp", ""))),
                    source=self.SITE_NAME,
                )
            )
        return results

    def _parse_html_cards(self, html: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select('li[class*="product"], div[class*="product-base"]')

        results: list[ProductResult] = []
        for card in cards:
            link = card.select_one("a[href]")
            href = first_attr(link, "href") or ""
            product_url = abs_url(self.BASE_URL, href) or ""
            if not product_url:
                continue

            title_tag = card.select_one('[class*="product-product"]')
            brand_tag = card.select_one('[class*="product-brand"]')
            price_tag = card.select_one('[class*="product-discountedPrice"]')
            mrp_tag = card.select_one('[class*="product-strike"]')
            img = card.select_one("img")

            brand = first_text(brand_tag) or ""
            title = first_text(title_tag) or ""
            full_title = f"{brand} {title}".strip()
            if not full_title:
                continue

            results.append(
                ProductResult(
                    product_name=full_title,
                    product_url=product_url,
                    image_url=first_attr(img, "src") or first_attr(img, "data-src"),
                    price=parse_price(first_text(price_tag)),
                    original_price=parse_price(first_text(mrp_tag)),
                    source=self.SITE_NAME,
                )
            )
            if len(results) >= self._max_results:
                break
        return results
