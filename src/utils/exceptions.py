"""Custom exceptions for the scraper."""


class ScraperError(Exception):
    """Base exception for all scraper errors."""

    def __init__(self, site: str, message: str) -> None:
        self.site = site
        super().__init__(f"[{site}] {message}")


class BlockedError(ScraperError):
    """Raised when the target site blocks our request (403, CAPTCHA, etc.)."""


class ParseError(ScraperError):
    """Raised when the HTML/JSON structure doesn't match expectations."""


class RateLimitError(ScraperError):
    """Raised when we receive a 429 Too Many Requests."""


class NetworkError(ScraperError):
    """Raised on transport-level failures (timeouts, DNS, connection reset)."""
