# CLAUDE.md — Ecom-scraper

This file provides guidance to AI assistants (Claude and others) working on the **Ecom-scraper** codebase. It covers project purpose, architecture, development workflows, conventions, and tooling.

---

## Project Overview

**Ecom-scraper** is a **real-time beauty product scraping API** that searches for products across 9 Indian e-commerce sites and returns structured data (product link, image, current price) via a FastAPI REST API.

### Supported Sites

| Site | Key | Anti-Bot Level | Strategy |
|---|---|---|---|
| Nykaa | `nykaa` | Moderate | Internal gateway API → `__NEXT_DATA__` → HTML |
| Tira Beauty | `tira` | Low | Internal API → `__NEXT_DATA__` → HTML |
| Purplle | `purplle` | Low | Internal API → HTML cards |
| Sephora India | `sephora` | Moderate | Search API → JSON-LD → HTML |
| Amazon India | `amazon` | **High** | HTML parsing with `data-*` selectors |
| Flipkart | `flipkart` | Moderate | HTML parsing with structural patterns |
| Meesho | `meesho` | Low | Internal API → `__NEXT_DATA__` → HTML |
| Myntra | `myntra` | Moderate | Gateway API → embedded JS state → HTML |
| Kindlife | `kindlife` | Low | Shopify `suggest.json` API → HTML |

### Key Design Decisions

- **Concurrent scraping**: All selected sites are scraped in parallel via `asyncio.gather` for lowest latency.
- **Multi-strategy extraction**: Each scraper tries the fastest method first (JSON API), then falls back to `__NEXT_DATA__`, then to CSS selector HTML parsing.
- **No Playwright by default**: Pure `httpx` + `BeautifulSoup` for speed. Playwright is listed as a dependency for future use on JS-heavy pages but is not used in the current scrapers.

---

## Repository Structure

```
Ecom-scraper/
├── CLAUDE.md                  # This file — AI assistant guidance
├── .gitignore
├── .env.example               # Environment variable template
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Project metadata, pytest/ruff/mypy config
│
├── src/                       # Main source code
│   ├── main.py                # FastAPI app entry-point (uvicorn)
│   ├── api/
│   │   └── routes.py          # GET/POST /api/search, GET /api/sites
│   ├── scrapers/
│   │   ├── base.py            # BaseScraper ABC with rate-limited _get()
│   │   ├── registry.py        # SCRAPERS dict mapping site keys → classes
│   │   ├── nykaa.py
│   │   ├── tira.py
│   │   ├── purplle.py
│   │   ├── sephora.py
│   │   ├── amazon.py
│   │   ├── flipkart.py
│   │   ├── meesho.py
│   │   ├── myntra.py
│   │   └── kindlife.py
│   ├── models/
│   │   └── product.py         # ProductResult, SearchRequest, SearchResponse
│   ├── proxies/
│   │   └── manager.py         # Round-robin proxy rotation with health tracking
│   └── utils/
│       ├── exceptions.py      # ScraperError, BlockedError, ParseError, etc.
│       ├── headers.py         # Realistic browser header generation
│       ├── helpers.py         # parse_price, extract_next_data, abs_url, etc.
│       └── rate_limiter.py    # Per-domain async rate limiter
│
├── tests/
│   ├── conftest.py            # Shared fixtures (rate_limiter, mock_client)
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_helpers.py
│   │   ├── test_rate_limiter.py
│   │   ├── test_api.py
│   │   └── scrapers/
│   │       ├── test_amazon.py   # Fixture HTML + respx mock tests
│   │       └── test_kindlife.py # Shopify JSON fixture tests
│   ├── integration/
│   └── fixtures/              # Sample HTML/JSON for offline testing
│
├── config/
│   └── settings.yaml          # Per-site config documentation
│
├── data/                      # Output data (gitignored)
│   ├── raw/
│   └── processed/
│
└── scripts/                   # Helper scripts
```

---

## Technology Stack

| Layer | Tool | Notes |
|---|---|---|
| Language | **Python 3.11+** | Required for `X \| Y` union syntax, `asyncio` improvements |
| API framework | **FastAPI** | Async, auto-generated OpenAPI docs at `/docs` |
| ASGI server | **uvicorn** | With `--reload` for development |
| HTTP client | **httpx** | Async, connection pooling, cookie jar support |
| HTML parsing | **BeautifulSoup4** + **lxml** | lxml parser for speed |
| Data models | **Pydantic v2** | Validation, serialisation, `BaseModel` |
| Config | **python-dotenv** + **PyYAML** | `.env` for secrets, YAML for site config |
| Testing | **pytest** + **pytest-asyncio** + **respx** | respx mocks httpx calls |
| Linting | **ruff** | Linting and formatting (replaces black + flake8) |
| Type checking | **mypy** | `ignore_missing_imports = true` |
| Browser automation | **Playwright** | Installed but reserved for future use |

---

## Development Setup

### Prerequisites

- Python 3.11 or higher
- `pip` (or `uv`)

### Installation

```bash
cd Ecom-scraper

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install all dependencies (including dev)
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### Environment Variables

| Variable | Description | Default | Required |
|---|---|---|---|
| `API_HOST` | Server bind address | `0.0.0.0` | No |
| `API_PORT` | Server port | `8000` | No |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` | `INFO` | No |
| `SCRAPE_DELAY_SECONDS` | Min delay between requests per domain | `1.0` | No |
| `REQUEST_TIMEOUT_SECONDS` | HTTP request timeout | `15.0` | No |
| `MAX_RESULTS_PER_SITE` | Default max products per site | `5` | No |
| `PROXY_URL` | Single proxy URL | _(empty)_ | No |
| `PROXY_API_KEY` | Proxy service API key | _(empty)_ | No |
| `DATABASE_URL` | For future persistence layer | _(empty)_ | No |

---

## Running the API

```bash
# Development (with auto-reload)
uvicorn src.main:app --reload

# Or via the module entry-point
python -m src.main

# The API is available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/sites` | List all supported site keys |
| `POST` | `/api/search` | Search products (JSON body) |
| `GET` | `/api/search?q=…` | Search products (query params) |

### Example Requests

```bash
# Search all 9 sites
curl "http://localhost:8000/api/search?q=Maybelline+Fit+Me+Foundation"

# Search specific sites only
curl "http://localhost:8000/api/search?q=MAC+lipstick&sites=nykaa,amazon,sephora&max_results=5"

# POST with JSON body
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Lakme 9 to 5 primer", "sites": ["nykaa", "flipkart"], "max_results": 3}'
```

### Response Format

```json
{
  "query": "Maybelline Fit Me Foundation",
  "results": {
    "nykaa": [
      {
        "product_name": "Maybelline New York Fit Me Matte+Poreless Foundation",
        "product_url": "https://www.nykaa.com/p/12345",
        "image_url": "https://images-static.nykaa.com/…",
        "price": 499.0,
        "original_price": 599.0,
        "currency": "INR",
        "source": "nykaa",
        "in_stock": true,
        "scraped_at": "2026-02-28T12:00:00Z"
      }
    ],
    "amazon": [ … ]
  },
  "errors": {
    "myntra": "[myntra] 403 Forbidden — likely blocked"
  },
  "duration_ms": 2345.6
}
```

---

## Running Tests

```bash
# All tests
pytest

# Verbose
pytest -v

# Unit tests only
pytest tests/unit/

# With coverage
pytest --cov=src --cov-report=term-missing
```

**Test conventions:**
- All unit tests use **fixture HTML/JSON** — never make real HTTP calls.
- Mock httpx with **respx** (not `responses` or `unittest.mock`).
- Tag integration tests with `pytest.mark.integration`.
- Each scraper should have a corresponding `tests/unit/scrapers/test_<site>.py`.
- Test files focus on a single module.

---

## Linting and Formatting

```bash
# Lint and auto-fix
ruff check src/ tests/ --fix

# Format
ruff format src/ tests/

# Type checking
mypy src/
```

Configuration is in `pyproject.toml`. Line length is 120. All PRs must pass ruff and mypy.

---

## Architecture and Key Conventions

### Scraper Design Pattern

Every site scraper inherits from `BaseScraper` and implements `search()`:

```python
class BaseScraper(ABC):
    SITE_NAME: str  # e.g. "nykaa"
    BASE_URL: str   # e.g. "https://www.nykaa.com"

    async def search(self, query: str) -> list[ProductResult]: ...
```

**Multi-strategy extraction** — each scraper tries methods in order:
1. **Internal JSON API** (fastest) — hit the site's own search gateway
2. **Embedded JSON** — parse `__NEXT_DATA__`, JSON-LD, or JS state variables
3. **HTML parsing** — CSS selector fallback for product cards

Scrapers never write to storage — they return `ProductResult` lists and the API layer handles the rest.

### Registering a New Scraper

1. Create `src/scrapers/<site_name>.py` inheriting from `BaseScraper`.
2. Add the import and entry to `SCRAPERS` dict in `src/scrapers/registry.py`.
3. Add HTML/JSON fixtures to `tests/fixtures/<site_name>/`.
4. Write unit tests in `tests/unit/scrapers/test_<site_name>.py`.
5. Document selectors and API endpoints in the scraper's docstring.
6. Add the site to `config/settings.yaml`.

### Anti-Detection / IP Block Prevention

- **Realistic headers**: `src/utils/headers.py` generates full Chrome-like header sets including `sec-ch-ua`, `sec-fetch-*`, and rotated `User-Agent` strings.
- **Per-domain rate limiting**: `src/utils/rate_limiter.py` enforces a configurable minimum gap between requests to the same domain.
- **Cookie persistence**: The shared `httpx.AsyncClient` maintains a cookie jar across requests.
- **Proxy rotation**: `src/proxies/manager.py` supports round-robin proxy rotation with automatic health tracking. Configure via `PROXY_URL` or `PROXY_LIST_FILE`.
- **Graceful degradation**: If a site blocks us (403/CAPTCHA), the error is logged and the other 8 sites still return results.

### Rate Limiting

- Enforce a minimum delay between requests per domain (configurable via `SCRAPE_DELAY_SECONDS`).
- Never hardcode delays — read from config or environment.
- `BaseScraper._get()` automatically calls `rate_limiter.acquire()` before every request.

### Data Models

- All models use **Pydantic v2 `BaseModel`**.
- Every `ProductResult` includes a UTC `scraped_at` timestamp.
- `SearchResponse.results` is keyed by site name; `SearchResponse.errors` tracks failures.

### Error Handling

- Custom exceptions in `src/utils/exceptions.py`: `ScraperError`, `BlockedError`, `ParseError`, `RateLimitError`, `NetworkError`.
- A single failing scraper does **not** abort the entire search — errors are collected in the response.
- `BaseScraper._get()` maps HTTP status codes to domain exceptions.

### Logging

- Use `logging.getLogger(__name__)` — no `print()`.
- `DEBUG`: HTML snippets, response details, fallback paths taken.
- `INFO`: Search queries, timing, result counts.
- `WARNING`: Blocked requests, unhealthy proxies, CAPTCHA detection.
- Never log credentials, proxy passwords, or PII.

---

## Git Workflow

### Branches

| Branch | Purpose |
|---|---|
| `main` | Production-ready code |
| `feature/<name>` | New features |
| `fix/<name>` | Bug fixes |
| `claude/<description>` | AI-assisted changes |

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scrapers): add Amazon product scraper
fix(proxies): handle 407 proxy auth error correctly
refactor(api): extract shared client factory
test(scrapers): add fixture for Kindlife Shopify suggest API
docs(claude): update CLAUDE.md with API endpoint docs
```

---

## AI Assistant Guidelines

### Always

- Read existing files before making changes — understand patterns in use.
- Follow the multi-strategy scraper pattern (API → embedded JSON → HTML).
- Use `BaseScraper._get()` for all HTTP requests (it handles rate limiting and error mapping).
- Add tests for any new scraper or utility.
- Use `respx` for mocking httpx in tests.
- Use `ruff` (not `black` or `flake8`).
- Add new env vars to `.env.example`.
- Use `async/await` consistently.

### Never

- Hardcode URLs, selectors, credentials, or delays.
- Commit `.env`, `data/`, `*.log`, or scraped output.
- Make real HTTP requests in unit tests.
- Use `time.sleep()` in async code — use `asyncio.sleep()`.
- Add dependencies without updating `requirements.txt`.
- Use bare `except:` — catch specific exceptions.

### When Modifying Selectors

CSS selectors break when sites redesign. When fixing:
1. Update the HTML fixture in `tests/fixtures/` to match new markup.
2. Update the selector in the scraper file.
3. Verify the unit test passes.
4. Add a `# Selectors last verified: YYYY-MM-DD` comment in the scraper docstring.

---

## Common Pitfalls

| Pitfall | Mitigation |
|---|---|
| IP bans from aggressive scraping | Per-domain rate limiter; proxy rotation |
| Amazon CAPTCHA pages | Detect "captcha" / "robot" in HTML; retry with simpler URL |
| Selector breakage after redesign | Multi-strategy approach; prefer API/JSON over CSS selectors |
| Flipkart dynamic class names | Use structural `href` patterns (`/p/itm…`) not class names |
| Myntra empty HTML shell | Must use gateway API or embedded JS state |
| Shopify price in cents | Kindlife scraper divides by 100 when price > 10000 |
| Timezone-naive timestamps | Always use `datetime.now(UTC)` |
| Async context manager misuse | Always use `async with` for httpx clients |

---

## Updating This File

Keep CLAUDE.md current as the project evolves:

- New scraper added → update the Supported Sites table and Repository Structure
- New dependency → update the Technology Stack table
- New convention → add to AI Assistant Guidelines
- New pitfall discovered → add to Common Pitfalls

Last updated: 2026-02-28
