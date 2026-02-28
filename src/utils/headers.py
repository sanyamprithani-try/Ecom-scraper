"""Realistic browser header generation for anti-detection."""

import random

# Realistic Chrome user agents (keep updated periodically)
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
]

_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,hi;q=0.8",
    "en-IN,en;q=0.9,hi;q=0.8",
    "en-GB,en;q=0.9,en-US;q=0.8",
]


def get_headers(*, referer: str | None = None, accept: str | None = None) -> dict[str, str]:
    """Return a realistic set of browser headers.

    Args:
        referer: Optional Referer header (e.g. the site's homepage).
        accept: Override the Accept header (useful for API calls that expect JSON).
    """
    ua = random.choice(_USER_AGENTS)  # noqa: S311
    is_chrome = "Chrome" in ua

    headers: dict[str, str] = {
        "User-Agent": ua,
        "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": random.choice(_ACCEPT_LANGUAGES),  # noqa: S311
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    if is_chrome:
        # Chrome Client Hints — many sites check these
        chrome_ver = ua.split("Chrome/")[1].split(".")[0]
        headers.update(
            {
                "sec-ch-ua": f'"Chromium";v="{chrome_ver}", "Google Chrome";v="{chrome_ver}", "Not?A_Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"' if "Windows" in ua else '"macOS"',
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "none" if referer is None else "same-origin",
                "sec-fetch-user": "?1",
            }
        )

    if referer:
        headers["Referer"] = referer

    return headers


def get_api_headers(*, referer: str | None = None) -> dict[str, str]:
    """Headers suitable for internal API / XHR requests."""
    headers = get_headers(
        referer=referer,
        accept="application/json, text/plain, */*",
    )
    headers["X-Requested-With"] = "XMLHttpRequest"
    # Override sec-fetch for XHR
    if "sec-fetch-dest" in headers:
        headers["sec-fetch-dest"] = "empty"
        headers["sec-fetch-mode"] = "cors"
        headers["sec-fetch-site"] = "same-origin"
    return headers
