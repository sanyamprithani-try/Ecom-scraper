"""FastAPI routes for the scraping API."""

from __future__ import annotations

import asyncio
import logging
import time

import httpx
from fastapi import APIRouter, Query

from src.models.product import ProductResult, SearchRequest, SearchResponse
from src.scrapers.base import BaseScraper
from src.scrapers.registry import ALL_SITE_KEYS, SCRAPERS
from src.utils.exceptions import ScraperError
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_site_key(raw: str) -> str | None:
    """Normalise a user-supplied site name to a registry key.

    Accepts any casing and handles multi-word display names (e.g. "Sephora India"
    → "sephora") by checking if the first token alone is a valid key.
    """
    lower = raw.lower().strip()
    if lower in SCRAPERS:
        return lower
    first_word = lower.split()[0] if lower else ""
    if first_word in SCRAPERS:
        return first_word
    return None

# Shared across requests for connection pooling and rate limiting
_rate_limiter = RateLimiter(delay_seconds=1.0)


def _build_client() -> httpx.AsyncClient:
    """Create a shared httpx client with sensible defaults."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(15.0, connect=10.0),
        follow_redirects=True,
        # Maintain cookies across requests (helps avoid bot detection)
        cookies=httpx.Cookies(),
    )


async def _run_scraper(
    scraper: BaseScraper,
    query: str,
) -> tuple[str, list[ProductResult] | None, str | None]:
    """Run a single scraper and return ``(site_key, results, error)``."""
    site = scraper.SITE_NAME
    try:
        results = await scraper.search(query)
        return site, results, None
    except ScraperError as exc:
        logger.warning("Scraper error for %s: %s", site, exc)
        return site, None, str(exc)
    except Exception as exc:
        logger.exception("Unexpected error in %s scraper", site)
        return site, None, f"Unexpected error: {exc}"


# ------------------------------------------------------------------
# POST /api/search
# ------------------------------------------------------------------
@router.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest) -> SearchResponse:
    """Search for a beauty product across configured e-commerce sites.

    All selected sites are scraped **concurrently** for lowest latency.
    """
    query = request.query.strip()
    max_results = request.max_results

    # Determine which sites to hit — normalise keys from user input
    raw_keys = request.sites or ALL_SITE_KEYS
    site_keys = [resolved for k in raw_keys if (resolved := _resolve_site_key(k)) is not None]
    if not site_keys:
        site_keys = ALL_SITE_KEYS

    start = time.perf_counter()

    async with _build_client() as client:
        scrapers = [
            SCRAPERS[key](
                client=client,
                rate_limiter=_rate_limiter,
                max_results=max_results,
            )
            for key in site_keys
        ]

        # Fire all scrapers concurrently
        tasks = [_run_scraper(s, query) for s in scrapers]
        outcomes = await asyncio.gather(*tasks)

    results: dict[str, list[ProductResult]] = {}
    errors: dict[str, str] = {}
    for site, products, error in outcomes:
        if error:
            errors[site] = error
        elif products:
            results[site] = products

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "Search for %r completed in %.0fms — %d sites returned results, %d errors",
        query,
        elapsed_ms,
        len(results),
        len(errors),
    )

    return SearchResponse(
        query=query,
        results=results,
        errors=errors,
        duration_ms=round(elapsed_ms, 1),
    )


# ------------------------------------------------------------------
# GET /api/search  (convenience — same logic)
# ------------------------------------------------------------------
@router.get("/search", response_model=SearchResponse)
async def search_products_get(
    q: str = Query(..., min_length=1, description="Product name to search for"),
    sites: str | None = Query(default=None, description="Comma-separated site keys (e.g. nykaa,amazon)"),
    max_results: int = Query(default=3, ge=1, le=20),
) -> SearchResponse:
    """GET endpoint for quick browser / curl testing."""
    site_list: list[str] | None = None
    if sites:
        resolved = [_resolve_site_key(s) for s in sites.split(",")]
        site_list = [k for k in resolved if k is not None] or None
    request = SearchRequest(query=q, sites=site_list, max_results=max_results)
    return await search_products(request)


# ------------------------------------------------------------------
# GET /api/sites  — list available scrapers
# ------------------------------------------------------------------
@router.get("/sites")
async def list_sites() -> dict[str, list[str]]:
    """Return the list of supported site keys."""
    return {"sites": ALL_SITE_KEYS}
