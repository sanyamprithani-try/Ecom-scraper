# CLAUDE.md — Ecom-scraper

This file provides guidance to AI assistants (Claude and others) working on the **Ecom-scraper** codebase. It covers project purpose, architecture, development workflows, conventions, and tooling.

---

## Project Overview

**Ecom-scraper** is a web scraping tool designed to extract product data (prices, titles, ratings, availability, images, etc.) from e-commerce websites. Its primary use cases include:

- Price monitoring and comparison across multiple stores
- Product catalogue aggregation
- Market research and trend analysis
- Stock and availability tracking

> **Note:** This repository was initialized empty. Update this section once the initial technology choices and architecture are established.

---

## Repository Structure

```
Ecom-scraper/
├── CLAUDE.md                  # This file
├── README.md                  # Project documentation for humans
├── .env.example               # Environment variable template (never commit .env)
├── .gitignore
│
├── src/                       # Main source code
│   ├── scrapers/              # Site-specific scraper implementations
│   │   └── base.py            # Base scraper class / interface
│   ├── models/                # Data models / schemas
│   ├── storage/               # Data persistence layer (DB, CSV, JSON)
│   ├── proxies/               # Proxy rotation and management
│   ├── utils/                 # Shared utilities (rate limiting, retries, etc.)
│   └── main.py                # Entry point
│
├── tests/                     # Test suite
│   ├── unit/
│   ├── integration/
│   └── fixtures/              # Sample HTML pages for offline testing
│
├── config/                    # Configuration files
│   └── settings.yaml          # Scraper settings (selectors, URLs, intervals)
│
├── data/                      # Output data (gitignored)
│   ├── raw/
│   └── processed/
│
└── scripts/                   # Helper scripts (setup, DB migrations, etc.)
```

> The structure above is the intended convention. Update this section to reflect the actual layout as the project evolves.

---

## Technology Stack

| Layer | Likely Tool | Notes |
|---|---|---|
| Language | Python 3.11+ | Preferred for scraping ecosystem |
| HTTP | `httpx` / `aiohttp` | Async HTTP clients |
| Parsing | `BeautifulSoup4` / `lxml` | HTML parsing |
| Browser automation | `Playwright` | For JS-heavy sites |
| Orchestration | `Scrapy` (optional) | If scale demands a framework |
| Storage | `SQLite` / `PostgreSQL` | Via SQLAlchemy or raw psycopg2 |
| Queue / scheduling | `APScheduler` / `Celery` | For periodic jobs |
| Config | `python-dotenv` + YAML | Environment + settings files |
| Testing | `pytest` + `pytest-asyncio` | With VCR cassettes / fixtures |
| Linting | `ruff` | Linting and formatting |
| Type checking | `mypy` | Static analysis |

> Update this table once the `requirements.txt` / `pyproject.toml` is committed.

---

## Development Setup

### Prerequisites

- Python 3.11 or higher
- `pip` or `uv` (preferred package manager)
- (Optional) Docker for running services (DB, Redis)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd Ecom-scraper

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# or with uv:
uv pip install -r requirements.txt

# Install Playwright browsers (if used)
playwright install chromium

# Copy environment template and fill in values
cp .env.example .env
```

### Environment Variables

All secrets and environment-specific settings go in `.env` (never committed).

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection string | Yes |
| `PROXY_URL` | Proxy endpoint for scraping | No |
| `PROXY_API_KEY` | API key for proxy service | No |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) | No |
| `SCRAPE_DELAY_SECONDS` | Minimum delay between requests | No |
| `USER_AGENT` | Custom User-Agent header string | No |

---

## Running the Scraper

```bash
# Run all configured scrapers
python src/main.py

# Run a specific scraper target
python src/main.py --target <site-name>

# Dry run (no data written to storage)
python src/main.py --dry-run
```

---

## Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests (may require network / DB)
pytest tests/integration/

# With coverage report
pytest --cov=src --cov-report=term-missing

# Watch mode during development
pytest --watch
```

**Test conventions:**
- Use `fixtures/` HTML files for offline HTML parsing tests — never make real HTTP calls from unit tests.
- Mock all external HTTP calls using `respx` (httpx) or `responses` (requests).
- Use `pytest.mark.integration` to tag tests that require a live database or network.
- Keep each test file focused on a single module.

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

All PRs must pass `ruff` and `mypy` with no errors before merging.

---

## Architecture and Key Conventions

### Scraper Design Pattern

- Every site-specific scraper **must** inherit from the `BaseScraper` class.
- Scrapers must implement a `scrape()` method that returns a list of `Product` model instances.
- Scrapers must not write to storage directly — return data and let the orchestrator handle persistence.

```python
class BaseScraper:
    async def scrape(self, url: str) -> list[Product]:
        raise NotImplementedError
```

### Rate Limiting

- Always respect `robots.txt` unless explicitly overridden for authorized research.
- Enforce a minimum delay between requests (configurable via `SCRAPE_DELAY_SECONDS`).
- Implement exponential backoff with jitter on 429 / 5xx responses.
- Never hardcode delays — read them from configuration.

### Proxy Usage

- Rotate proxies using the proxy manager in `src/proxies/`.
- Never embed proxy credentials in source code; read them from environment variables.
- Mark a proxy as failed after N consecutive errors and remove it from rotation.

### Data Models

- Use `dataclasses` or `pydantic` `BaseModel` for all data structures.
- Always include a `scraped_at` UTC timestamp on every record.
- Validate data at the boundary (right after parsing HTML), not at storage time.

### Storage Layer

- The storage layer must be abstracted behind an interface so backends (SQLite, Postgres, CSV) are swappable.
- Upsert by a unique key (e.g., product URL + store) to avoid duplicates on re-runs.
- Never truncate or delete existing data without explicit user confirmation.

### Error Handling

- Catch narrow exceptions — never use bare `except:`.
- Log the full traceback for unexpected errors (`logger.exception(...)`).
- A single failed product should not abort an entire scrape run — log and continue.
- Raise custom exceptions from `src/utils/exceptions.py` for domain-specific errors.

### Logging

- Use Python's standard `logging` module (no `print()` in production code).
- Logger names should match the module: `logger = logging.getLogger(__name__)`.
- Do not log raw HTML or full response bodies at `INFO` level — use `DEBUG`.
- Never log credentials, proxy URLs with passwords, or PII.

---

## Git Workflow

### Branches

| Branch | Purpose |
|---|---|
| `main` | Production-ready code |
| `develop` | Integration branch |
| `feature/<name>` | New features |
| `fix/<name>` | Bug fixes |
| `claude/<description>` | AI-assisted changes |

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scrapers): add Amazon product scraper
fix(proxies): handle 407 proxy auth error correctly
refactor(storage): extract DB connection to context manager
test(scrapers): add fixture for Amazon search results page
docs(claude): update CLAUDE.md with storage conventions
```

### Pull Request Requirements

- All CI checks must pass (lint, type check, tests).
- Include a description of what changed and why.
- Reference the relevant issue number if applicable.
- Keep PRs focused — one logical change per PR.

---

## AI Assistant Guidelines

When working on this codebase, AI assistants should:

### Always

- Read existing source files before suggesting changes to understand patterns already in use.
- Follow the rate-limiting and proxy conventions — never add code that makes unthrottled requests.
- Add tests for any new scraper or utility function introduced.
- Use `ruff` conventions (no `black`, no `flake8`) for formatting guidance.
- Respect `.env.example` — add any new environment variable there with a description.
- Use `async/await` patterns consistently if the codebase is async.

### Never

- Hardcode URLs, selectors, credentials, or delays in source code — use config files or environment variables.
- Commit `.env`, `data/`, `*.log`, or any scraped output files.
- Make real HTTP requests in unit tests.
- Use `time.sleep()` in async code — use `asyncio.sleep()`.
- Add dependencies without updating `requirements.txt` or `pyproject.toml`.
- Bypass `robots.txt` checks without an explicit comment explaining why.

### When Adding a New Scraper

1. Create `src/scrapers/<site_name>.py` inheriting from `BaseScraper`.
2. Add HTML fixture(s) to `tests/fixtures/<site_name>/`.
3. Write unit tests in `tests/unit/scrapers/test_<site_name>.py`.
4. Register the scraper in the main dispatcher / factory.
5. Document the selectors and any fragile assumptions in inline comments.
6. Update `config/settings.yaml` with the new target's configuration.

### When Modifying Selectors

CSS/XPath selectors break when sites update their markup. When fixing a broken selector:
- Update the corresponding HTML fixture in `tests/fixtures/` to match the new markup.
- Update the selector in config or the scraper file.
- Verify the unit test passes with the new fixture.
- Note the date of the selector change in a comment.

---

## Common Pitfalls

| Pitfall | Mitigation |
|---|---|
| IP bans from aggressive scraping | Enforce rate limits; use proxies with rotation |
| Selector breakage after site redesign | Prefer stable attributes (`data-*`, `id`) over positional selectors |
| Duplicate records on re-runs | Upsert logic with a unique key |
| Memory leaks in long-running jobs | Stream/batch large result sets; avoid holding all records in memory |
| Async context manager misuse | Always use `async with` for HTTP clients |
| Timezone-naive timestamps | Always store UTC; use `datetime.now(UTC)` |

---

## Updating This File

Keep CLAUDE.md up to date as the project grows. When you:

- Add a new major dependency → update the Technology Stack table
- Change the directory layout → update the Repository Structure section
- Establish a new coding convention → add it to AI Assistant Guidelines
- Discover a new common pitfall → add it to the Common Pitfalls table

Last updated: 2026-02-28
