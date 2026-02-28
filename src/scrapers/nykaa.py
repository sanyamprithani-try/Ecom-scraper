"""Nykaa (nykaa.com) scraper.

Strategy
--------
1. Primary: Hit Nykaa's internal search gateway API which returns JSON.
   Endpoint discovered from their SPA network requests:
   ``GET /gateway-api/search?q=…&page_no=1&count=…``
2. Fallback: Load the HTML search page and extract embedded JSON
   (``__NEXT_DATA__`` / inline script) or parse the product cards.

Selectors last verified: 2026-02-28
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from src.models.product import ProductResult
from src.scrapers.base import BaseScraper
from src.utils.exceptions import ParseError
from src.utils.headers import get_api_headers, get_headers
from src.utils.helpers import abs_url, encode_query, extract_next_data, first_attr, first_text, parse_price

logger = logging.getLogger(__name__)


class NykaaScraper(BaseScraper):
    SITE_NAME = "nykaa"
    BASE_URL = "https://www.nykaa.com"

    async def search(self, query: str) -> list[ProductResult]:
        # --- Strategy 1: internal JSON API ---
        try:
            return await self._search_api(query)
        except Exception:
            logger.debug("Nykaa API strategy failed, falling back to HTML", exc_info=True)

        # --- Strategy 2: HTML search page ---
        return await self._search_html(query)

    # ------------------------------------------------------------------
    # Strategy 1 – JSON API
    # ------------------------------------------------------------------

    async def _search_api(self, query: str) -> list[ProductResult]:
        url = f"{self.BASE_URL}/gateway-api/search"
        params = {"q": query, "page_no": "1", "count": str(self._max_results)}
        headers = get_api_headers(referer=f"{self.BASE_URL}/search/result/?q={encode_query(query)}")

        resp = await self._get(url, headers=headers, params=params)
        data = resp.json()

        products_raw = (
            data.get("response", {}).get("products")
            or data.get("products")
            or []
        )

        results: list[ProductResult] = []
        for item in products_raw[: self._max_results]:
            title = item.get("title") or item.get("name", "")
            price = item.get("price") or item.get("offer_price")
            mrp = item.get("mrp") or item.get("price")
            slug = item.get("slug") or item.get("actionUrl") or ""
            image = item.get("imageUrl") or item.get("image_url") or ""

            product_url = abs_url(self.BASE_URL, slug) or ""
            if not title or not product_url:
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
        url = f"{self.BASE_URL}/search/result/?q={encode_query(query)}"
        resp = await self._get(url, headers=get_headers(referer=self.BASE_URL))
        html = resp.text

        # Try __NEXT_DATA__ first
        next_data = extract_next_data(html)
        if next_data:
            try:
                return self._parse_next_data(next_data)
            except Exception:
                logger.debug("Nykaa __NEXT_DATA__ parsing failed", exc_info=True)

        # CSS selector fallback
        return self._parse_html_cards(html)

    def _parse_next_data(self, data: dict) -> list[ProductResult]:
        props = data.get("props", {}).get("pageProps", {})
        products_raw = (
            props.get("searchData", {}).get("products")
            or props.get("products")
            or []
        )
        results: list[ProductResult] = []
        for item in products_raw[: self._max_results]:
            title = item.get("title") or item.get("name", "")
            slug = item.get("slug") or item.get("actionUrl") or ""
            product_url = abs_url(self.BASE_URL, slug) or ""
            if not title:
                continue
            results.append(
                ProductResult(
                    product_name=title,
                    product_url=product_url,
                    image_url=item.get("imageUrl") or item.get("image_url"),
                    price=parse_price(str(item.get("price", ""))),
                    original_price=parse_price(str(item.get("mrp", ""))),
                    source=self.SITE_NAME,
                )
            )
        return results

    def _parse_html_cards(self, html: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "lxml")
        # Nykaa wraps each product in a card with class containing "productWrapper" or similar
        cards = soup.select('div[class*="product"]  a[href*="/p/"]')
        if not cards:
            cards = soup.select('a[href*="/p/"]')
        if not cards:
            raise ParseError(self.SITE_NAME, "No product cards found in HTML")

        results: list[ProductResult] = []
        seen: set[str] = set()
        for card in cards:
            href = first_attr(card, "href") or ""
            product_url = abs_url(self.BASE_URL, href) or ""
            if not product_url or product_url in seen:
                continue
            seen.add(product_url)

            title_tag = card.select_one('div[class*="title"], span[class*="title"], div[class*="name"]')
            price_tag = card.select_one('span[class*="price"], div[class*="price"]')
            img_tag = card.select_one("img")

            title = first_text(title_tag) or first_attr(card, "title") or ""
            if not title:
                continue

            results.append(
                ProductResult(
                    product_name=title,
                    product_url=product_url,
                    image_url=first_attr(img_tag, "src"),
                    price=parse_price(first_text(price_tag)),
                    source=self.SITE_NAME,
                )
            )
            if len(results) >= self._max_results:
                break
        return results
