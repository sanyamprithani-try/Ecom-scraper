"""Flipkart (flipkart.com) scraper.

Strategy
--------
Flipkart's search page is largely **server-side rendered**, making it
amenable to direct HTML parsing.  The site uses dynamically generated
CSS class names (hashed), so we rely on structural patterns and
``data-*`` attributes rather than exact class names.

1. Parse HTML product grid from the search results page.
2. Identify product cards by their link structure (``/product-name/p/…``).

Anti-bot: Flipkart serves a login modal to some requests; we skip it
by setting appropriate headers and not following unnecessary redirects.

Selectors last verified: 2026-02-28
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup, Tag

from src.models.product import ProductResult
from src.scrapers.base import BaseScraper
from src.utils.headers import get_headers
from src.utils.helpers import abs_url, encode_query, first_attr, first_text, parse_price

logger = logging.getLogger(__name__)


class FlipkartScraper(BaseScraper):
    SITE_NAME = "flipkart"
    BASE_URL = "https://www.flipkart.com"

    async def search(self, query: str) -> list[ProductResult]:
        url = f"{self.BASE_URL}/search"
        params = {"q": query, "otracker": "search", "as-show": "on"}
        headers = get_headers(referer=self.BASE_URL)

        resp = await self._get(url, headers=headers, params=params)
        return self._parse_results(resp.text)

    def _parse_results(self, html: str) -> list[ProductResult]:
        soup = BeautifulSoup(html, "lxml")

        # Flipkart product links follow the pattern /product-slug/p/itm…
        # They sit inside <a> tags whose href contains "/p/itm"
        product_links = soup.select('a[href*="/p/itm"]')

        results: list[ProductResult] = []
        seen_urls: set[str] = set()

        for link in product_links:
            result = self._parse_product_link(link, soup)
            if result and result.product_url not in seen_urls:
                seen_urls.add(result.product_url)
                results.append(result)
            if len(results) >= self._max_results:
                break

        return results

    def _parse_product_link(self, link: Tag, soup: BeautifulSoup) -> ProductResult | None:
        href = first_attr(link, "href") or ""
        product_url = abs_url(self.BASE_URL, href) or ""
        if not product_url:
            return None

        # Strip query parameters for a cleaner URL
        product_url = product_url.split("?")[0] if "?" in product_url else product_url

        # The <a> tag is usually the product card container or its parent is.
        # Walk up to find the encompassing card div.
        card = link
        for _ in range(5):
            parent = card.parent
            if parent and parent.name == "div":
                card = parent
                # Stop when we've found a div that looks like a full card
                # (contains both a title element and a price element)
                if card.select_one('div[class], span[class]'):
                    break

        # --- Title ---
        # Flipkart uses various class names; try title attribute on link first
        title = first_attr(link, "title")
        if not title:
            # Look for the first text-heavy child of the card
            for tag in card.select("a[title], div[class] > div[class]"):
                text = first_text(tag)
                if text and len(text) > 5:
                    title = text
                    break
        if not title:
            title = first_text(link)
        if not title:
            return None

        # --- Price ---
        # Flipkart prices are typically in a <div> with ₹ symbol
        price = None
        original_price = None
        price_tags = card.select('div[class]')
        for pt in price_tags:
            text = first_text(pt)
            if not text:
                continue
            if "₹" in text and price is None:
                parsed = parse_price(text)
                if parsed:
                    price = parsed
            # Strike-through / MRP is often in a <span> with line-through style
            if pt.select_one('[style*="line-through"], s, strike, del'):
                parsed = parse_price(text)
                if parsed:
                    original_price = parsed

        # --- Image ---
        img = card.select_one("img[src*='rukminim']") or card.select_one("img")
        image_url = first_attr(img, "src") or first_attr(img, "data-src")

        return ProductResult(
            product_name=title,
            product_url=product_url,
            image_url=image_url,
            price=price,
            original_price=original_price,
            source=self.SITE_NAME,
        )
