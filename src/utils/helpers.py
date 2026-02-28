"""Shared helper functions for scrapers."""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def encode_query(query: str) -> str:
    """URL-encode a search query string."""
    return quote_plus(query.strip())


def parse_price(text: str | None) -> float | None:
    """Extract a numeric price from a string like '₹1,299.00' or 'Rs. 450'.

    Returns None if parsing fails.
    """
    if not text:
        return None
    # Remove currency symbols, commas, whitespace
    cleaned = re.sub(r"[₹$,\s]", "", text)
    cleaned = re.sub(r"^(rs\.?|inr)", "", cleaned, flags=re.IGNORECASE).strip()
    # Take first number-like substring (handles "1299.00 - 1599.00" → 1299.00)
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def extract_next_data(html: str) -> dict | None:
    """Extract the __NEXT_DATA__ JSON blob from a Next.js page.

    Many Indian e-commerce sites use Next.js and embed their page props
    in a <script id=\"__NEXT_DATA__\"> tag.
    """
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except json.JSONDecodeError:
            logger.debug("Failed to parse __NEXT_DATA__ JSON")
    return None


def first_text(tag: Tag | None) -> str | None:
    """Safely get stripped text from a BeautifulSoup Tag."""
    if tag is None:
        return None
    return tag.get_text(strip=True) or None


def first_attr(tag: Tag | None, attr: str) -> str | None:
    """Safely get an attribute value from a Tag."""
    if tag is None:
        return None
    val = tag.get(attr)
    if isinstance(val, list):
        return val[0] if val else None
    return val


def abs_url(base: str, path: str | None) -> str | None:
    """Make a relative URL absolute given a base domain."""
    if path is None:
        return None
    if path.startswith("http"):
        return path
    path = path.lstrip("/")
    base = base.rstrip("/")
    return f"{base}/{path}"


def safe_json_loads(text: str | None) -> dict | list | None:
    """Attempt to parse JSON; return None on failure."""
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
