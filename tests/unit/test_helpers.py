"""Tests for src.utils.helpers."""

from src.utils.helpers import abs_url, encode_query, parse_price


class TestParsePrice:
    def test_rupee_symbol(self) -> None:
        assert parse_price("₹1,299.00") == 1299.0

    def test_rs_prefix(self) -> None:
        assert parse_price("Rs. 450") == 450.0

    def test_plain_number(self) -> None:
        assert parse_price("999") == 999.0

    def test_range_takes_first(self) -> None:
        assert parse_price("₹1,299 - ₹1,599") == 1299.0

    def test_none_input(self) -> None:
        assert parse_price(None) is None

    def test_empty_string(self) -> None:
        assert parse_price("") is None

    def test_no_number(self) -> None:
        assert parse_price("Price not available") is None


class TestEncodeQuery:
    def test_spaces(self) -> None:
        assert encode_query("mac lipstick") == "mac+lipstick"

    def test_strips_whitespace(self) -> None:
        assert encode_query("  hello  ") == "hello"


class TestAbsUrl:
    def test_relative_path(self) -> None:
        assert abs_url("https://nykaa.com", "/p/123") == "https://nykaa.com/p/123"

    def test_already_absolute(self) -> None:
        assert abs_url("https://nykaa.com", "https://cdn.nykaa.com/img.jpg") == "https://cdn.nykaa.com/img.jpg"

    def test_none_path(self) -> None:
        assert abs_url("https://nykaa.com", None) is None
