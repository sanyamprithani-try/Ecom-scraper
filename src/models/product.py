from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl


class ProductResult(BaseModel):
    """A single product result from a scraper."""

    product_name: str
    product_url: str
    image_url: str | None = None
    price: float | None = None
    original_price: float | None = None  # MRP / strike-through price
    currency: str = "INR"
    source: str  # e.g. "nykaa", "amazon_in"
    in_stock: bool = True
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SearchRequest(BaseModel):
    """Incoming search request payload."""

    query: str = Field(..., min_length=1, max_length=300, description="Product name to search for")
    sites: list[str] | None = Field(
        default=None,
        description="Optional list of site keys to search. Searches all sites when omitted.",
    )
    max_results: int = Field(default=3, ge=1, le=20, description="Max results per site")


class SearchResponse(BaseModel):
    """Aggregated response returned by the API."""

    query: str
    results: dict[str, list[ProductResult]]  # keyed by site name
    errors: dict[str, str]  # site -> error message for failed scrapers
    duration_ms: float
