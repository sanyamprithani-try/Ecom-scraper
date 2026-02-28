"""Purplle (purplle.com) scraper.

Strategy
--------
1. Primary: Hit Purplle's internal search API (``/api/search/…``).
2. Fallback: Parse HTML search results page.

Purplle is a dedicated beauty e-commerce platform.  Its search pages
are partially server-rendered and often contain structured data that
can be extracted from the HTML without JS execution.

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


class PurplleScraper(BaseScraper):
    SITE_NAME = "purplle"
    BASE_URL = "https://www.purplle.com"

    async def search(self, query: str) -> list[ProductResult]:
        try:
            return await self._search_api(query)
        except Exception:
            logger.debug("Purplle API strategy failed, falling back to HTML", exc_info=True)
        return await self._search_html(query)

    # ------------------------------------------------------------------
    # Strategy 1 – JSON API
    # ------------------------------------------------------------------

    async def _search_api(self, query: str) -> list[ProductResult]:
        url = f"{self.BASE_URL}/api/search"
        params = {"q": query, "page": "1", "limit": str(self._max_results)}
        headers = get_api_headers(referer=f"{self.BASE_URL}/search?q={encode_query(query)}")

        resp = await self._get(url, headers=headers, params=params)
        data = resp.json()

        products_raw = (
            data.get("data", {}).get("products")
            or data.get("products")
            or data.get("results", [])
        )

        results: list[ProductResult] = []
        for item in products_raw[: self._max_results]:
            title = item.get("name") or item.get("title", "")
            slug = item.get("url") or item.get("slug") or ""
            product_url = abs_url(self.BASE_URL, slug) or ""
            image = item.get("image") or item.get("image_url") or ""

            price = item.get("selling_price") or item.get("price")
            mrp = item.get("mrp") or item.get("original_price")

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
        return self._parse_html(html)

    def _parse_html(self, html: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "lxml")
        # Purplle product cards typically live inside structured divs
        cards = soup.select('div[class*="product-card"], div[class*="prd-card"], div[class*="productCard"]')
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

            title_tag = card.select_one('[class*="title"], [class*="name"], [class*="prd-name"]')
            price_tag = card.select_one('[class*="price"], [class*="offer"]')
            mrp_tag = card.select_one('[class*="mrp"], [class*="strike"], [class*="original"]')
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
                    original_price=parse_price(first_text(mrp_tag)),
                    source=self.SITE_NAME,
                )
            )
            if len(results) >= self._max_results:
                break
        return results
