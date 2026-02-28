"""Tests for data models."""

from datetime import UTC, datetime

from src.models.product import ProductResult, SearchRequest, SearchResponse


class TestProductResult:
    def test_defaults(self) -> None:
        p = ProductResult(
            product_name="Test Lipstick",
            product_url="https://example.com/product/1",
            source="nykaa",
        )
        assert p.currency == "INR"
        assert p.in_stock is True
        assert p.image_url is None
        assert p.price is None
        assert isinstance(p.scraped_at, datetime)
        assert p.scraped_at.tzinfo is not None  # must be tz-aware

    def test_full_construction(self) -> None:
        p = ProductResult(
            product_name="MAC Lipstick",
            product_url="https://nykaa.com/p/123",
            image_url="https://images.nykaa.com/123.jpg",
            price=1299.0,
            original_price=1500.0,
            source="nykaa",
            in_stock=True,
        )
        assert p.price == 1299.0
        assert p.original_price == 1500.0


class TestSearchRequest:
    def test_minimal(self) -> None:
        r = SearchRequest(query="foundation")
        assert r.query == "foundation"
        assert r.sites is None
        assert r.max_results == 3

    def test_with_sites(self) -> None:
        r = SearchRequest(query="lipstick", sites=["nykaa", "amazon"], max_results=5)
        assert r.sites == ["nykaa", "amazon"]
        assert r.max_results == 5


class TestSearchResponse:
    def test_construction(self) -> None:
        r = SearchResponse(
            query="serum",
            results={"nykaa": []},
            errors={"amazon": "blocked"},
            duration_ms=123.4,
        )
        assert r.query == "serum"
        assert "amazon" in r.errors
