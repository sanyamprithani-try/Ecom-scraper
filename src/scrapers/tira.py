"""Tira Beauty (tirabeauty.com) scraper.

Strategy
--------
1. Primary: Hit Tira's internal search API (React SPA with JSON backend).
2. Fallback: Parse the HTML search page for ``__NEXT_DATA__`` or product cards.

Tira is a Reliance Retail beauty platform. It typically uses a
Next.js frontend with JSON payloads embedded in the initial HTML
or fetched via XHR to an internal gateway.

Selectors last verified: 2026-02-28
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from src.models.product import ProductResult
from src.scrapers.base import BaseScraper
from src.utils.headers import get_api_headers, get_headers
from src.utils.helpers import abs_url, encode_query, extract_next_data, first_attr, first_text, parse_price

logger = logging.getLogger(__name__)


class TiraScraper(BaseScraper):
    SITE_NAME = "tira"
    BASE_URL = "https://www.tirabeauty.com"

    async def search(self, query: str) -> list[ProductResult]:
        try:
            return await self._search_api(query)
        except Exception:
            logger.debug("Tira API strategy failed, falling back to HTML", exc_info=True)
        return await self._search_html(query)

    # ------------------------------------------------------------------
    # Strategy 1 – internal API
    # ------------------------------------------------------------------

    async def _search_api(self, query: str) -> list[ProductResult]:
        url = f"{self.BASE_URL}/api/search"
        params = {"q": query, "page": "1", "size": str(self._max_results)}
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
            image = item.get("image") or item.get("imageUrl") or ""

            price = item.get("sellingPrice") or item.get("price")
            mrp = item.get("mrp") or item.get("originalPrice")

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

        next_data = extract_next_data(html)
        if next_data:
            try:
                return self._parse_next_data(next_data)
            except Exception:
                logger.debug("Tira __NEXT_DATA__ parsing failed", exc_info=True)

        return self._parse_html_cards(html)

    def _parse_next_data(self, data: dict) -> list[ProductResult]:
        props = data.get("props", {}).get("pageProps", {})
        products_raw = (
            props.get("searchResult", {}).get("products")
            or props.get("products")
            or props.get("data", {}).get("products", [])
        )
        results: list[ProductResult] = []
        for item in products_raw[: self._max_results]:
            title = item.get("name") or item.get("title", "")
            slug = item.get("url") or item.get("slug") or ""
            product_url = abs_url(self.BASE_URL, slug) or ""
            if not title:
                continue
            results.append(
                ProductResult(
                    product_name=title,
                    product_url=product_url,
                    image_url=item.get("image") or item.get("imageUrl"),
                    price=parse_price(str(item.get("sellingPrice", item.get("price", "")))),
                    original_price=parse_price(str(item.get("mrp", ""))),
                    source=self.SITE_NAME,
                )
            )
        return results

    def _parse_html_cards(self, html: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select('div[class*="product-card"], div[class*="ProductCard"], a[class*="product"]')
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

            title_tag = card.select_one('[class*="title"], [class*="name"], [class*="brand"]')
            price_tag = card.select_one('[class*="price"], [class*="Price"]')
            img = card.select_one("img")

            title = first_text(title_tag) or first_attr(card, "title") or ""
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
