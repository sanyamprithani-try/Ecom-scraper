"""Scraper registry — maps site keys to scraper classes.

The registry is the single source of truth for which sites are
available.  Adding a new site only requires:
  1. Creating a scraper module in ``src/scrapers/``.
  2. Importing it and adding a single entry to ``SCRAPERS``.
"""

from __future__ import annotations

from src.scrapers.amazon import AmazonScraper
from src.scrapers.base import BaseScraper
from src.scrapers.flipkart import FlipkartScraper
from src.scrapers.kindlife import KindlifeScraper
from src.scrapers.meesho import MeeshoScraper
from src.scrapers.myntra import MyntraScraper
from src.scrapers.nykaa import NykaaScraper
from src.scrapers.purplle import PurplleScraper
from src.scrapers.sephora import SephoraScraper
from src.scrapers.tira import TiraScraper

# Map of site key → scraper class
SCRAPERS: dict[str, type[BaseScraper]] = {
    "nykaa": NykaaScraper,
    "tira": TiraScraper,
    "purplle": PurplleScraper,
    "sephora": SephoraScraper,
    "amazon": AmazonScraper,
    "flipkart": FlipkartScraper,
    "meesho": MeeshoScraper,
    "myntra": MyntraScraper,
    "kindlife": KindlifeScraper,
}

ALL_SITE_KEYS = list(SCRAPERS.keys())
