"""Meesho (meesho.com) scraper.

Strategy
--------
Meesho is a **fully client-side rendered React SPA**.  The HTML returned
by the server is an empty shell, so we must either:

1. Primary: Hit Meesho's internal search API that returns JSON.
   The React app fetches from ``/api/v1/products/search`` or similar
   gateway endpoints.
2. Fallback: Look for ``__NEXT_DATA__`` or inline state hydration JSON.

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


class MeeshoScraper(BaseScraper):
    SITE_NAME = "meesho"
    BASE_URL = "https://www.meesho.com"

    async def search(self, query: str) -> list[ProductResult]:
        # Strategy 1: internal API
        try:
            return await self._search_api(query)
        except Exception:
            logger.debug("Meesho API strategy failed", exc_info=True)

        # Strategy 2: HTML / __NEXT_DATA__
        return await self._search_html(query)

    # ------------------------------------------------------------------
    # Strategy 1 – JSON API
    # ------------------------------------------------------------------

    async def _search_api(self, query: str) -> list[ProductResult]:
        # Meesho's search API endpoint
        url = f"{self.BASE_URL}/api/v1/products/search"
        params = {"q": query, "page": "1", "limit": str(self._max_results)}
        headers = get_api_headers(referer=f"{self.BASE_URL}/search?q={encode_query(query)}")

        resp = await self._get(url, headers=headers, params=params)
        data = resp.json()

        catalogs = (
            data.get("catalogs")
            or data.get("products")
            or data.get("data", {}).get("catalogs", [])
        )

        results: list[ProductResult] = []
        for item in catalogs[: self._max_results]:
            title = item.get("name") or item.get("title", "")
            product_id = item.get("product_id") or item.get("id") or ""
            slug = item.get("slug") or ""

            if slug:
                product_url = abs_url(self.BASE_URL, slug) or ""
            elif product_id:
                product_url = f"{self.BASE_URL}/product/{product_id}"
            else:
                continue

            image = item.get("image") or item.get("images", [None])[0] or ""
            if isinstance(item.get("images"), list) and item["images"]:
                image = item["images"][0]

            price = item.get("min_catalog_price") or item.get("price")
            mrp = item.get("mrp") or item.get("product_mrp")

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
    # Strategy 2 – HTML / __NEXT_DATA__
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
                logger.debug("Meesho __NEXT_DATA__ parsing failed", exc_info=True)

        return self._parse_html_cards(html)

    def _parse_next_data(self, data: dict) -> list[ProductResult]:
        props = data.get("props", {}).get("pageProps", {})
        catalogs = (
            props.get("initialData", {}).get("catalogs")
            or props.get("catalogs")
            or props.get("products", [])
        )
        results: list[ProductResult] = []
        for item in catalogs[: self._max_results]:
            title = item.get("name") or item.get("title", "")
            product_id = item.get("product_id") or item.get("id") or ""
            product_url = f"{self.BASE_URL}/product/{product_id}" if product_id else ""
            images = item.get("images") or item.get("product_images") or []
            image = images[0] if images else None

            if not title:
                continue
            results.append(
                ProductResult(
                    product_name=title,
                    product_url=product_url,
                    image_url=image,
                    price=parse_price(str(item.get("min_catalog_price", item.get("price", "")))),
                    original_price=parse_price(str(item.get("mrp", ""))),
                    source=self.SITE_NAME,
                )
            )
        return results

    def _parse_html_cards(self, html: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select('div[class*="ProductCard"], div[class*="product-card"]')
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
                    image_url=first_attr(img, "src"),
                    price=parse_price(first_text(price_tag)),
                    source=self.SITE_NAME,
                )
            )
            if len(results) >= self._max_results:
                break
        return results
