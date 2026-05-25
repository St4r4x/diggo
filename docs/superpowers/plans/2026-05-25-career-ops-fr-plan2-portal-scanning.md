# Plan 2 — Portal Scanning
**Date:** 2026-05-25
**Project:** career-ops-fr
**Status:** TODO

---

## Goal

Build an automated portal scanning system that scrapes French job portals daily,
deduplicates offers across sources, pre-filters low-scoring offers, and produces a
Markdown report saved to `reports/daily-YYYY-MM-DD.md`.

---

## Architecture

```
portals/fr/*.yaml          Portal configs (selectors, URL templates)
        │
        ▼
scripts/scan_portals.py    Playwright runner → list[RawOffer]
        │
        ▼
scripts/dedup.py           Normalize + deduplicate → list[RawOffer]
        │
        ▼
scripts/pre_filter.py      Keyword + score filter (threshold 3.0) → list[RawOffer]
        │
        ▼
scripts/daily_report.py    Render Markdown → reports/daily-YYYY-MM-DD.md
```

`RawOffer` is a dataclass defined once in `scripts/models.py` and imported by all
modules.  The scanner can be run standalone:

```bash
.venv/bin/python scripts/scan_portals.py --portal wtfj
.venv/bin/python scripts/scan_portals.py --all
.venv/bin/python scripts/daily_report.py
```

---

## Tech Stack

| Concern | Library | Version |
|---|---|---|
| Browser automation | playwright | 1.44.0 |
| Async test runner | pytest-asyncio | 0.23.7 |
| YAML parsing | pyyaml | 6.0.2 (existing) |
| Test framework | pytest | 8.2.2 (existing) |
| Type checking | built-in dataclasses + typing | stdlib |

---

## Task 1 — Add Playwright, install browsers, scaffold directories

### 1.1 — Update requirements.txt

- [ ] Append the two new packages to `requirements.txt`:

```
playwright==1.44.0
pytest-asyncio==0.23.7
```

Full resulting `requirements.txt`:

```
weasyprint==62.3.0
pydyf==0.11.0
jinja2==3.1.4
pyyaml==6.0.2
pytest==8.2.2
playwright==1.44.0
pytest-asyncio==0.23.7
```

### 1.2 — Install packages and Playwright browsers

- [ ] Run from the project root:

```bash
source .venv/bin/activate
pip install playwright==1.44.0 pytest-asyncio==0.23.7
playwright install chromium
```

### 1.3 — Create directory skeleton

- [ ] Run:

```bash
mkdir -p /home/missia03/Projects/career-ops-fr/portals/fr
mkdir -p /home/missia03/Projects/career-ops-fr/reports
touch /home/missia03/Projects/career-ops-fr/reports/.gitkeep
```

### 1.4 — Create `scripts/models.py`

This central module defines `RawOffer`, imported by every other script.

- [ ] Create `/home/missia03/Projects/career-ops-fr/scripts/models.py`:

```python
"""Shared data models for career-ops-fr portal scanning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class RawOffer:
    """A job offer as scraped from a portal, before any scoring.

    Attributes:
        title: Job title as displayed on the portal.
        company: Company name as displayed on the portal.
        url: Canonical URL of the offer page.
        portal: Short portal identifier, e.g. 'wtfj', 'indeed', 'apec'.
        location: Location string, may be None if not found.
        date_posted: Posting date, may be None if not parseable.
        score: Pre-filter relevance score (0.0 – 5.0). Defaults to 0.0.
        tags: Free-form keyword tags matched during pre-filter.
    """

    title: str
    company: str
    url: str
    portal: str
    location: Optional[str] = None
    date_posted: Optional[date] = None
    score: float = 0.0
    tags: list[str] = field(default_factory=list)

    def dedup_key(self) -> str:
        """Return a normalized string used for deduplication.

        The key is built from the lowercased, stripped title and company so
        that the same offer scraped from two portals is treated as identical.
        """
        title_norm = self.title.lower().strip()
        company_norm = self.company.lower().strip()
        return f"{title_norm}||{company_norm}"
```

### 1.5 — Commit

- [ ] Commit:

```bash
git add requirements.txt scripts/models.py portals/ reports/.gitkeep
git commit -m "feat: scaffold Plan 2 portal scanning — add playwright, models, dirs"
```

---

## Task 2 — Portal config YAML files

Each YAML file describes how to reach and parse one portal.  The scanner reads
these files at runtime; no portal logic is hard-coded in Python.

Schema:

```
portal_id: str               # short identifier used in RawOffer.portal
name: str                    # human-readable name
base_url: str                # root of the portal
search_url_template: str     # Python .format() template — {keywords}, {location}
search_params:               # query-string parameters
  keywords: str              # placeholder replaced at runtime
  location: str              # placeholder replaced at runtime
selectors:
  offer_card: str            # CSS selector for each offer card container
  title: str                 # CSS selector for the title INSIDE a card
  company: str               # CSS selector for the company INSIDE a card
  url: str                   # CSS selector for the <a> INSIDE a card (href extracted)
  location: str              # CSS selector for location (optional)
  date: str                  # CSS selector for date (optional)
pagination:
  type: str                  # "scroll" | "next_button" | "page_param"
  max_pages: int             # safety ceiling
  next_selector: str         # CSS selector for "next page" button (if type=next_button)
  page_param: str            # URL query param name (if type=page_param)
```

### 2.1 — Welcome to the Jungle (`portals/fr/wtfj.yaml`)

- [ ] Create `/home/missia03/Projects/career-ops-fr/portals/fr/wtfj.yaml`:

```yaml
portal_id: wtfj
name: "Welcome to the Jungle"
base_url: "https://www.welcometothejungle.com"
search_url_template: "https://www.welcometothejungle.com/fr/jobs?query={keywords}&aroundQuery={location}"
search_params:
  keywords: ""
  location: "Paris"
selectors:
  offer_card: "li[data-testid='search-results-list-item-wrapper']"
  title: "h3[data-testid='job-title']"
  company: "span[data-testid='company-title']"
  url: "a[data-testid='job-link']"
  location: "span[data-testid='job-location']"
  date: "time"
pagination:
  type: next_button
  max_pages: 5
  next_selector: "a[data-testid='pagination-next-page']"
  page_param: ""
```

### 2.2 — Indeed.fr (`portals/fr/indeed.yaml`)

- [ ] Create `/home/missia03/Projects/career-ops-fr/portals/fr/indeed.yaml`:

```yaml
portal_id: indeed
name: "Indeed France"
base_url: "https://fr.indeed.com"
search_url_template: "https://fr.indeed.com/jobs?q={keywords}&l={location}"
search_params:
  keywords: ""
  location: "Paris"
selectors:
  offer_card: "div.job_seen_beacon"
  title: "h2.jobTitle span[title]"
  company: "span.companyName"
  url: "h2.jobTitle a"
  location: "div.companyLocation"
  date: "span.date"
pagination:
  type: page_param
  max_pages: 5
  next_selector: ""
  page_param: "start"
```

### 2.3 — APEC (`portals/fr/apec.yaml`)

- [ ] Create `/home/missia03/Projects/career-ops-fr/portals/fr/apec.yaml`:

```yaml
portal_id: apec
name: "APEC"
base_url: "https://www.apec.fr"
search_url_template: "https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles={keywords}&lieuTravail={location}"
search_params:
  keywords: ""
  location: "Paris"
selectors:
  offer_card: "div.result-item"
  title: "h2.result-item-title a"
  company: "span.result-item-company"
  url: "h2.result-item-title a"
  location: "span.result-item-location"
  date: "span.result-item-date"
pagination:
  type: next_button
  max_pages: 5
  next_selector: "a.pagination-next"
  page_param: ""
```

### 2.4 — LinkedIn France (`portals/fr/linkedin.yaml`)

- [ ] Create `/home/missia03/Projects/career-ops-fr/portals/fr/linkedin.yaml`:

```yaml
portal_id: linkedin
name: "LinkedIn France"
base_url: "https://www.linkedin.com"
search_url_template: "https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&f_WT=2"
search_params:
  keywords: ""
  location: "Paris"
selectors:
  offer_card: "li.jobs-search__results-list > div"
  title: "h3.base-search-card__title"
  company: "h4.base-search-card__subtitle"
  url: "a.base-card__full-link"
  location: "span.job-search-card__location"
  date: "time.job-search-card__listdate"
pagination:
  type: scroll
  max_pages: 3
  next_selector: ""
  page_param: ""
```

### 2.5 — Glassdoor France (`portals/fr/glassdoor.yaml`)

- [ ] Create `/home/missia03/Projects/career-ops-fr/portals/fr/glassdoor.yaml`:

```yaml
portal_id: glassdoor
name: "Glassdoor France"
base_url: "https://www.glassdoor.fr"
search_url_template: "https://www.glassdoor.fr/Emploi/emplois.htm?sc.keyword={keywords}&locT=C&locName={location}"
search_params:
  keywords: ""
  location: "Paris"
selectors:
  offer_card: "li.react-job-listing"
  title: "a.JobCard_jobTitle__GLyJ1"
  company: "span.EmployerProfile_compactEmployerName__9MGcV"
  url: "a.JobCard_jobTitle__GLyJ1"
  location: "div.JobCard_location__rCz3x"
  date: "div.JobCard_listingAge__KuaxZ"
pagination:
  type: next_button
  max_pages: 5
  next_selector: "button[data-test='pagination-next']"
  page_param: ""
```

### 2.6 — Commit

- [ ] Commit:

```bash
git add portals/
git commit -m "feat: add portal config YAML files for wtfj, indeed, apec, linkedin, glassdoor"
```

---

## Task 3 — `scripts/scan_portals.py` (TDD on parsing functions)

The scanner has two distinct layers:

- **Pure parsing helpers** — `parse_date_string`, `build_search_url`, `extract_offer_from_card_data` — fully unit-testable with no browser.
- **Playwright runner** — `scrape_portal`, `run_scan` — integration only; not unit-tested.

Write the tests first, then the implementation.

### 3.1 — Write failing tests (`tests/test_scan_portals.py`)

- [ ] Create `/home/missia03/Projects/career-ops-fr/tests/test_scan_portals.py`:

```python
"""Tests for scan_portals pure parsing helpers."""

from __future__ import annotations

from datetime import date

import pytest

from scripts.scan_portals import build_search_url, extract_offer_from_card_data, parse_date_string


class TestParseDateString:
    """Tests for parse_date_string()."""

    def test_iso_format(self) -> None:
        assert parse_date_string("2026-05-20") == date(2026, 5, 20)

    def test_french_format_with_month_name(self) -> None:
        # "20 mai 2026" → date(2026, 5, 20)
        result = parse_date_string("20 mai 2026")
        assert result == date(2026, 5, 20)

    def test_relative_today(self) -> None:
        result = parse_date_string("Aujourd'hui")
        assert result == date.today()

    def test_relative_yesterday(self) -> None:
        from datetime import timedelta

        result = parse_date_string("Hier")
        assert result == date.today() - timedelta(days=1)

    def test_unknown_string_returns_none(self) -> None:
        assert parse_date_string("n/a") is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_date_string("") is None


class TestBuildSearchUrl:
    """Tests for build_search_url()."""

    def test_simple_substitution(self) -> None:
        template = "https://example.com/jobs?q={keywords}&l={location}"
        url = build_search_url(template, keywords="AI Engineer", location="Paris")
        assert "AI+Engineer" in url or "AI%20Engineer" in url or "AI Engineer" in url
        assert "Paris" in url

    def test_multi_word_keywords_encoded(self) -> None:
        template = "https://example.com/jobs?q={keywords}&l={location}"
        url = build_search_url(template, keywords="Machine Learning Engineer", location="Lyon")
        # Spaces must be encoded
        assert " " not in url.split("?")[1]

    def test_special_chars_encoded(self) -> None:
        template = "https://example.com/jobs?q={keywords}&l={location}"
        url = build_search_url(template, keywords="C++ Developer", location="Paris")
        assert " " not in url.split("?")[1]


class TestExtractOfferFromCardData:
    """Tests for extract_offer_from_card_data()."""

    def test_full_data_returns_raw_offer(self) -> None:
        from scripts.models import RawOffer

        card_data = {
            "title": "AI Engineer",
            "company": "Mistral AI",
            "url": "https://example.com/offer/123",
            "location": "Paris",
            "date": "2026-05-20",
        }
        offer = extract_offer_from_card_data(card_data, portal_id="wtfj")
        assert isinstance(offer, RawOffer)
        assert offer.title == "AI Engineer"
        assert offer.company == "Mistral AI"
        assert offer.portal == "wtfj"
        assert offer.date_posted == date(2026, 5, 20)

    def test_missing_optional_fields_produce_none(self) -> None:
        card_data = {
            "title": "ML Engineer",
            "company": "Hugging Face",
            "url": "https://example.com/offer/456",
            "location": "",
            "date": "",
        }
        offer = extract_offer_from_card_data(card_data, portal_id="indeed")
        assert offer.location is None
        assert offer.date_posted is None

    def test_title_and_company_stripped(self) -> None:
        card_data = {
            "title": "  LLM Engineer  ",
            "company": "  Nabla  ",
            "url": "https://example.com/offer/789",
            "location": "Paris",
            "date": "",
        }
        offer = extract_offer_from_card_data(card_data, portal_id="apec")
        assert offer.title == "LLM Engineer"
        assert offer.company == "Nabla"

    def test_relative_url_with_base_is_made_absolute(self) -> None:
        card_data = {
            "title": "NLP Engineer",
            "company": "Yseop",
            "url": "/fr/jobs/nlp-engineer-yseop",
            "location": "Paris",
            "date": "",
        }
        offer = extract_offer_from_card_data(
            card_data, portal_id="wtfj", base_url="https://www.welcometothejungle.com"
        )
        assert offer.url.startswith("https://")

    def test_returns_none_when_title_missing(self) -> None:
        card_data = {
            "title": "",
            "company": "SomeCompany",
            "url": "https://example.com/offer/999",
            "location": "Paris",
            "date": "",
        }
        result = extract_offer_from_card_data(card_data, portal_id="wtfj")
        assert result is None
```

- [ ] Run tests — all should FAIL:

```bash
.venv/bin/pytest tests/test_scan_portals.py -v 2>&1 | head -40
```

### 3.2 — Implement `scripts/scan_portals.py`

- [ ] Create `/home/missia03/Projects/career-ops-fr/scripts/scan_portals.py`:

```python
"""Portal scanner: loads portal configs and scrapes job offers via Playwright.

Usage:
    python scripts/scan_portals.py --portal wtfj
    python scripts/scan_portals.py --all
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urljoin

import yaml

from scripts.models import RawOffer

logger = logging.getLogger(__name__)

_PORTALS_DIR = Path(__file__).parent.parent / "portals" / "fr"

# Mapping of French month names to month numbers
_FRENCH_MONTHS: dict[str, int] = {
    "janvier": 1,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
}


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable)
# ---------------------------------------------------------------------------


def parse_date_string(raw: str) -> Optional[date]:
    """Parse a raw date string from a portal into a Python date.

    Supports:
    - ISO format: "2026-05-20"
    - French long form: "20 mai 2026"
    - Relative: "Aujourd'hui", "Hier"

    Args:
        raw: The raw date string scraped from the portal.

    Returns:
        A ``date`` object, or ``None`` when the string cannot be parsed.
    """
    if not raw or not raw.strip():
        return None

    cleaned = raw.strip()

    # Relative dates
    lower = cleaned.lower()
    if lower in ("aujourd'hui", "today", "aujourd"):
        return date.today()
    if lower in ("hier", "yesterday"):
        return date.today() - timedelta(days=1)

    # ISO format YYYY-MM-DD
    iso_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", cleaned)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            return None

    # French "DD mois YYYY"
    french_match = re.fullmatch(r"(\d{1,2})\s+([a-záéèêîôùûüç]+)\s+(\d{4})", cleaned, re.IGNORECASE)
    if french_match:
        day = int(french_match.group(1))
        month_name = french_match.group(2).lower()
        year = int(french_match.group(3))
        month = _FRENCH_MONTHS.get(month_name)
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                return None

    return None


def build_search_url(template: str, *, keywords: str, location: str) -> str:
    """Build a search URL from a template, encoding the query parameters.

    Args:
        template: A Python format string with ``{keywords}`` and ``{location}``
            placeholders.
        keywords: Raw keywords string (may contain spaces).
        location: Raw location string.

    Returns:
        A fully-formed URL with percent-encoded query parameters.
    """
    return template.format(
        keywords=quote_plus(keywords),
        location=quote_plus(location),
    )


def extract_offer_from_card_data(
    card_data: dict[str, str],
    *,
    portal_id: str,
    base_url: str = "",
) -> Optional[RawOffer]:
    """Convert a dict of scraped card fields into a RawOffer.

    Args:
        card_data: Dict with keys ``title``, ``company``, ``url``, ``location``,
            ``date``.  All values are raw strings from the DOM.
        portal_id: Short portal identifier (e.g. ``"wtfj"``).
        base_url: Portal base URL used to resolve relative ``url`` values.

    Returns:
        A ``RawOffer``, or ``None`` when required fields (title, company, url)
        are empty after stripping.
    """
    title = card_data.get("title", "").strip()
    company = card_data.get("company", "").strip()
    raw_url = card_data.get("url", "").strip()
    location = card_data.get("location", "").strip() or None
    raw_date = card_data.get("date", "").strip()

    if not title:
        return None

    # Make relative URLs absolute
    if raw_url and not raw_url.startswith("http") and base_url:
        raw_url = urljoin(base_url, raw_url)

    return RawOffer(
        title=title,
        company=company,
        url=raw_url,
        portal=portal_id,
        location=location,
        date_posted=parse_date_string(raw_date),
    )


# ---------------------------------------------------------------------------
# Portal config loader
# ---------------------------------------------------------------------------


def load_portal_config(portal_id: str) -> dict:
    """Load a portal YAML config by its short identifier.

    Args:
        portal_id: Short identifier, e.g. ``"wtfj"``.

    Returns:
        The parsed YAML config dict.

    Raises:
        FileNotFoundError: When no matching YAML file exists.
    """
    path = _PORTALS_DIR / f"{portal_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Portal config not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def list_portal_ids() -> list[str]:
    """Return all available portal IDs from portals/fr/*.yaml."""
    return sorted(p.stem for p in _PORTALS_DIR.glob("*.yaml"))


# ---------------------------------------------------------------------------
# Playwright scraper (not unit-tested — requires real browser)
# ---------------------------------------------------------------------------


async def scrape_portal(portal_id: str, keywords: str, location: str) -> list[RawOffer]:
    """Scrape a single portal and return raw offers.

    Args:
        portal_id: Short portal identifier.
        keywords: Search keywords string.
        location: Location string.

    Returns:
        List of ``RawOffer`` instances scraped from the portal.
    """
    from playwright.async_api import async_playwright  # local import keeps tests fast

    config = load_portal_config(portal_id)
    selectors = config["selectors"]
    pagination = config["pagination"]
    base_url = config["base_url"]
    offers: list[RawOffer] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        url = build_search_url(config["search_url_template"], keywords=keywords, location=location)
        current_page = 0
        max_pages = pagination.get("max_pages", 3)

        while current_page < max_pages:
            logger.info("[%s] Navigating to page %d: %s", portal_id, current_page + 1, url)
            try:
                await page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception as exc:
                logger.warning("[%s] Navigation error: %s", portal_id, exc)
                break

            # Wait for offer cards
            try:
                await page.wait_for_selector(selectors["offer_card"], timeout=10_000)
            except Exception:
                logger.warning("[%s] No offer cards found on page %d", portal_id, current_page + 1)
                break

            # Infinite scroll: scroll to bottom if needed
            if pagination["type"] == "scroll":
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            cards = await page.query_selector_all(selectors["offer_card"])
            logger.info("[%s] Found %d cards on page %d", portal_id, len(cards), current_page + 1)

            for card in cards:
                async def _text(sel: str) -> str:
                    try:
                        el = await card.query_selector(sel)
                        return (await el.inner_text()).strip() if el else ""
                    except Exception:
                        return ""

                async def _href(sel: str) -> str:
                    try:
                        el = await card.query_selector(sel)
                        return (await el.get_attribute("href") or "").strip() if el else ""
                    except Exception:
                        return ""

                async def _datetime_attr(sel: str) -> str:
                    try:
                        el = await card.query_selector(sel)
                        if el:
                            dt = await el.get_attribute("datetime")
                            if dt:
                                return dt.strip()
                            return (await el.inner_text()).strip()
                        return ""
                    except Exception:
                        return ""

                card_data = {
                    "title": await _text(selectors["title"]),
                    "company": await _text(selectors["company"]),
                    "url": await _href(selectors["url"]),
                    "location": await _text(selectors.get("location", "")),
                    "date": await _datetime_attr(selectors.get("date", "")),
                }

                offer = extract_offer_from_card_data(card_data, portal_id=portal_id, base_url=base_url)
                if offer:
                    offers.append(offer)

            # Pagination
            if pagination["type"] == "next_button":
                next_btn = await page.query_selector(pagination["next_selector"])
                if not next_btn:
                    break
                await next_btn.click()
                await page.wait_for_load_state("networkidle")
                current_page += 1
            elif pagination["type"] == "page_param":
                current_page += 1
                from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                params[pagination["page_param"]] = [str(current_page * 10)]
                new_query = urlencode({k: v[0] for k, v in params.items()})
                url = urlunparse(parsed._replace(query=new_query))
            elif pagination["type"] == "scroll":
                # Scrolling already done above; check if new content appeared
                current_page += 1
            else:
                break

        await browser.close()

    logger.info("[%s] Total offers scraped: %d", portal_id, len(offers))
    return offers


async def run_scan(portal_ids: list[str], keywords: str, location: str) -> list[RawOffer]:
    """Scrape multiple portals concurrently.

    Args:
        portal_ids: List of portal identifiers to scrape.
        keywords: Search keywords string.
        location: Location string.

    Returns:
        Aggregated list of ``RawOffer`` from all portals.
    """
    tasks = [scrape_portal(pid, keywords, location) for pid in portal_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_offers: list[RawOffer] = []
    for pid, result in zip(portal_ids, results):
        if isinstance(result, Exception):
            logger.error("[%s] Scrape failed: %s", pid, result)
        else:
            all_offers.extend(result)
    return all_offers


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape French job portals")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--portal", metavar="ID", help="Scrape a single portal (e.g. wtfj)")
    group.add_argument("--all", action="store_true", help="Scrape all configured portals")
    parser.add_argument("--keywords", default="AI Engineer", help="Search keywords")
    parser.add_argument("--location", default="Paris", help="Search location")
    return parser


def main() -> None:
    """CLI entry point for scan_portals."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = _build_cli_parser()
    args = parser.parse_args()

    portal_ids = list_portal_ids() if args.all else [args.portal]
    offers = asyncio.run(run_scan(portal_ids, keywords=args.keywords, location=args.location))

    for offer in offers:
        print(f"[{offer.portal}] {offer.title} @ {offer.company} — {offer.url}")

    print(f"\nTotal: {len(offers)} offers")


if __name__ == "__main__":
    main()
```

### 3.3 — Run tests, all must pass

- [ ] Run:

```bash
.venv/bin/pytest tests/test_scan_portals.py -v
```

Expected output: all 12 tests green.

### 3.4 — Commit

- [ ] Commit:

```bash
git add scripts/scan_portals.py tests/test_scan_portals.py
git commit -m "feat: add scan_portals with parsing helpers and Playwright runner"
```

---

## Task 4 — `scripts/dedup.py` (TDD)

### 4.1 — Write failing tests (`tests/test_dedup.py`)

- [ ] Create `/home/missia03/Projects/career-ops-fr/tests/test_dedup.py`:

```python
"""Tests for dedup module."""

from __future__ import annotations

from scripts.dedup import deduplicate, normalize_key
from scripts.models import RawOffer


def _make_offer(title: str, company: str, portal: str = "wtfj", url: str = "https://x.com") -> RawOffer:
    return RawOffer(title=title, company=company, url=url, portal=portal)


class TestNormalizeKey:
    """Tests for normalize_key()."""

    def test_lowercase_and_strip(self) -> None:
        assert normalize_key("  AI Engineer  ", "  Mistral AI  ") == "ai engineer||mistral ai"

    def test_accent_normalization(self) -> None:
        # accents are stripped during normalization
        key = normalize_key("Ingénieur IA", "Société Générale")
        assert "ingenieur ia" in key
        assert "societe generale" in key

    def test_punctuation_stripped(self) -> None:
        key = normalize_key("AI/ML Engineer", "Hugging-Face")
        assert "/" not in key
        assert "-" not in key

    def test_multiple_spaces_collapsed(self) -> None:
        key = normalize_key("AI  ML  Engineer", "Big  Corp")
        assert "  " not in key


class TestDeduplicate:
    """Tests for deduplicate()."""

    def test_empty_list(self) -> None:
        assert deduplicate([]) == []

    def test_no_duplicates_unchanged(self) -> None:
        offers = [
            _make_offer("AI Engineer", "Mistral AI", portal="wtfj"),
            _make_offer("ML Engineer", "Hugging Face", portal="indeed"),
        ]
        result = deduplicate(offers)
        assert len(result) == 2

    def test_exact_duplicate_removed(self) -> None:
        offers = [
            _make_offer("AI Engineer", "Mistral AI", portal="wtfj"),
            _make_offer("AI Engineer", "Mistral AI", portal="indeed"),
        ]
        result = deduplicate(offers)
        assert len(result) == 1

    def test_first_occurrence_kept(self) -> None:
        offers = [
            _make_offer("AI Engineer", "Mistral AI", portal="wtfj", url="https://wtfj.com/1"),
            _make_offer("AI Engineer", "Mistral AI", portal="indeed", url="https://indeed.com/2"),
        ]
        result = deduplicate(offers)
        assert result[0].portal == "wtfj"

    def test_case_insensitive_dedup(self) -> None:
        offers = [
            _make_offer("ai engineer", "mistral ai", portal="wtfj"),
            _make_offer("AI Engineer", "Mistral AI", portal="indeed"),
        ]
        result = deduplicate(offers)
        assert len(result) == 1

    def test_accent_insensitive_dedup(self) -> None:
        offers = [
            _make_offer("Ingénieur IA", "Société Générale", portal="wtfj"),
            _make_offer("Ingenieur IA", "Societe Generale", portal="apec"),
        ]
        result = deduplicate(offers)
        assert len(result) == 1

    def test_different_titles_not_deduplicated(self) -> None:
        offers = [
            _make_offer("AI Engineer", "Mistral AI", portal="wtfj"),
            _make_offer("ML Engineer", "Mistral AI", portal="indeed"),
        ]
        result = deduplicate(offers)
        assert len(result) == 2

    def test_preserves_order_of_first_occurrence(self) -> None:
        offers = [
            _make_offer("A", "CompA", portal="wtfj"),
            _make_offer("B", "CompB", portal="wtfj"),
            _make_offer("A", "CompA", portal="indeed"),
            _make_offer("C", "CompC", portal="wtfj"),
        ]
        result = deduplicate(offers)
        assert [o.title for o in result] == ["A", "B", "C"]
```

- [ ] Run tests — all should FAIL:

```bash
.venv/bin/pytest tests/test_dedup.py -v 2>&1 | head -30
```

### 4.2 — Implement `scripts/dedup.py`

- [ ] Create `/home/missia03/Projects/career-ops-fr/scripts/dedup.py`:

```python
"""Deduplication of job offers across portals.

Two offers are considered duplicates when their normalized title+company key is
identical.  Normalization:
- Lowercase
- Unicode accent stripping (NFD decomposition + ASCII encoding)
- Punctuation removal (only alphanumeric and spaces kept)
- Collapse multiple spaces to one
"""

from __future__ import annotations

import re
import unicodedata

from scripts.models import RawOffer


def _remove_accents(text: str) -> str:
    """Return text with Unicode accents stripped via NFD decomposition."""
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def normalize_key(title: str, company: str) -> str:
    """Build a normalized deduplication key from title and company.

    Args:
        title: Raw job title string.
        company: Raw company name string.

    Returns:
        A normalized key string: ``"<title>||<company>"``.
    """
    def _normalize(text: str) -> str:
        text = text.strip().lower()
        text = _remove_accents(text)
        # Keep only alphanumeric and spaces
        text = re.sub(r"[^a-z0-9 ]", " ", text)
        # Collapse multiple spaces
        text = re.sub(r" {2,}", " ", text).strip()
        return text

    return f"{_normalize(title)}||{_normalize(company)}"


def deduplicate(offers: list[RawOffer]) -> list[RawOffer]:
    """Remove duplicate offers, keeping the first occurrence per unique key.

    Iteration order is preserved so that the first portal that found the offer
    (typically the one with higher trust) is kept.

    Args:
        offers: List of raw offers, potentially containing duplicates.

    Returns:
        Deduplicated list of ``RawOffer``, in original order of first occurrence.
    """
    seen: set[str] = set()
    unique: list[RawOffer] = []
    for offer in offers:
        key = normalize_key(offer.title, offer.company)
        if key not in seen:
            seen.add(key)
            unique.append(offer)
    return unique
```

### 4.3 — Run tests, all must pass

- [ ] Run:

```bash
.venv/bin/pytest tests/test_dedup.py -v
```

Expected: all 9 tests green.

### 4.4 — Commit

- [ ] Commit:

```bash
git add scripts/dedup.py tests/test_dedup.py
git commit -m "feat: add dedup module with accent-insensitive normalization"
```

---

## Task 5 — `scripts/pre_filter.py` (TDD)

The pre-filter scores each offer against keywords from `config/settings.yaml` and
drops offers scoring below the `scoring.thresholds.consider` threshold (3.0).

Scoring rules:
- Base score: 0.0
- +1.0 per keyword from `search.keywords` found in title (case-insensitive)
- +1.0 if company appears in any `target_companies` list
- +1.0 if location matches `search.location`
- +0.5 if title contains a seniority indicator matching the profile (junior / alternance / stage / apprenti)
- Capped at 5.0

### 5.1 — Write failing tests (`tests/test_pre_filter.py`)

- [ ] Create `/home/missia03/Projects/career-ops-fr/tests/test_pre_filter.py`:

```python
"""Tests for pre_filter module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from scripts.models import RawOffer
from scripts.pre_filter import load_settings, score_offer, pre_filter


MOCK_SETTINGS = {
    "search": {
        "keywords": ["AI Engineer", "ML Engineer", "LLM Engineer"],
        "location": "Paris",
    },
    "scoring": {
        "thresholds": {"recommend": 4.0, "consider": 3.0},
        "target_salary_min": 40000,
        "target_salary_max": 55000,
    },
    "target_companies": {
        "french_ai": ["Mistral AI", "Hugging Face"],
        "big_tech": ["Google", "Meta"],
    },
}


def _offer(title: str, company: str = "Unknown Corp", location: str = "Paris") -> RawOffer:
    return RawOffer(title=title, company=company, url="https://x.com", portal="wtfj", location=location)


class TestScoreOffer:
    """Tests for score_offer()."""

    def test_perfect_match_scores_high(self) -> None:
        offer = _offer("AI Engineer", company="Mistral AI", location="Paris")
        score, tags = score_offer(offer, MOCK_SETTINGS)
        # keyword match (+1) + target company (+1) + location (+1) = 3.0 minimum
        assert score >= 3.0

    def test_no_keyword_match_scores_low(self) -> None:
        offer = _offer("Java Developer", company="Random Corp", location="Lyon")
        score, tags = score_offer(offer, MOCK_SETTINGS)
        assert score < 3.0

    def test_keyword_match_adds_to_score(self) -> None:
        offer_match = _offer("ML Engineer", company="Unknown", location="Lyon")
        offer_no = _offer("Java Developer", company="Unknown", location="Lyon")
        score_match, _ = score_offer(offer_match, MOCK_SETTINGS)
        score_no, _ = score_offer(offer_no, MOCK_SETTINGS)
        assert score_match > score_no

    def test_target_company_adds_to_score(self) -> None:
        offer_target = _offer("ML Engineer", company="Mistral AI", location="Lyon")
        offer_other = _offer("ML Engineer", company="Random Corp", location="Lyon")
        score_t, _ = score_offer(offer_target, MOCK_SETTINGS)
        score_o, _ = score_offer(offer_other, MOCK_SETTINGS)
        assert score_t > score_o

    def test_location_match_adds_to_score(self) -> None:
        offer_paris = _offer("ML Engineer", company="Unknown", location="Paris")
        offer_other = _offer("ML Engineer", company="Unknown", location="Marseille")
        score_p, _ = score_offer(offer_paris, MOCK_SETTINGS)
        score_o, _ = score_offer(offer_other, MOCK_SETTINGS)
        assert score_p > score_o

    def test_tags_contain_matched_keywords(self) -> None:
        offer = _offer("LLM Engineer", company="Unknown", location="Lyon")
        _, tags = score_offer(offer, MOCK_SETTINGS)
        assert "LLM Engineer" in tags

    def test_score_capped_at_five(self) -> None:
        # Offer that matches everything multiple times
        offer = _offer(
            "AI Engineer ML Engineer LLM Engineer",
            company="Mistral AI",
            location="Paris",
        )
        score, _ = score_offer(offer, MOCK_SETTINGS)
        assert score <= 5.0

    def test_case_insensitive_keyword_match(self) -> None:
        offer = _offer("ai engineer", company="Unknown", location="Lyon")
        score, tags = score_offer(offer, MOCK_SETTINGS)
        assert score > 0

    def test_case_insensitive_company_match(self) -> None:
        offer = _offer("Developer", company="mistral ai", location="Lyon")
        score, _ = score_offer(offer, MOCK_SETTINGS)
        # company match should contribute
        offer_no = _offer("Developer", company="Random Corp", location="Lyon")
        score_no, _ = score_offer(offer_no, MOCK_SETTINGS)
        assert score > score_no


class TestPreFilter:
    """Tests for pre_filter()."""

    def test_empty_list_returns_empty(self) -> None:
        assert pre_filter([], MOCK_SETTINGS) == []

    def test_below_threshold_dropped(self) -> None:
        offers = [_offer("Java Developer", company="Random Corp", location="Lyon")]
        result = pre_filter(offers, MOCK_SETTINGS)
        assert result == []

    def test_above_threshold_kept(self) -> None:
        offers = [_offer("AI Engineer", company="Mistral AI", location="Paris")]
        result = pre_filter(offers, MOCK_SETTINGS)
        assert len(result) == 1

    def test_score_written_to_offer(self) -> None:
        offers = [_offer("AI Engineer", company="Mistral AI", location="Paris")]
        result = pre_filter(offers, MOCK_SETTINGS)
        assert result[0].score > 0

    def test_tags_written_to_offer(self) -> None:
        offers = [_offer("AI Engineer", company="Mistral AI", location="Paris")]
        result = pre_filter(offers, MOCK_SETTINGS)
        assert len(result[0].tags) > 0

    def test_mixed_list_filters_correctly(self) -> None:
        offers = [
            _offer("AI Engineer", company="Mistral AI", location="Paris"),
            _offer("Java Developer", company="Random Corp", location="Lyon"),
            _offer("ML Engineer", company="Hugging Face", location="Paris"),
        ]
        result = pre_filter(offers, MOCK_SETTINGS)
        assert len(result) == 2
        titles = [o.title for o in result]
        assert "Java Developer" not in titles
```

- [ ] Run tests — all should FAIL:

```bash
.venv/bin/pytest tests/test_pre_filter.py -v 2>&1 | head -30
```

### 5.2 — Implement `scripts/pre_filter.py`

- [ ] Create `/home/missia03/Projects/career-ops-fr/scripts/pre_filter.py`:

```python
"""Pre-filter: score offers against settings.yaml and drop those below threshold.

Scoring rubric (max 5.0):
- +1.0 per keyword from search.keywords found in the offer title (case-insensitive)
- +1.0 if the company appears in any target_companies list (case-insensitive)
- +1.0 if the offer location contains the search.location string (case-insensitive)
- +0.5 if the title contains a junior/apprenti/alternance indicator
- Score capped at 5.0
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from scripts.models import RawOffer

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"

_JUNIOR_PATTERNS = frozenset(["junior", "alternance", "stage", "apprenti", "stagiaire"])


def load_settings(path: Path = _SETTINGS_PATH) -> dict:
    """Load and return the parsed settings.yaml.

    Args:
        path: Path to the settings YAML file.

    Returns:
        Parsed settings as a dict.
    """
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _all_target_companies(settings: dict) -> set[str]:
    """Return a flat set of lowercased target company names."""
    companies: set[str] = set()
    for category in settings.get("target_companies", {}).values():
        for name in category:
            companies.add(name.lower())
    return companies


def score_offer(offer: RawOffer, settings: dict) -> tuple[float, list[str]]:
    """Compute a relevance score and matched tags for a single offer.

    Args:
        offer: The ``RawOffer`` to evaluate.
        settings: Parsed settings dict (from ``load_settings``).

    Returns:
        A ``(score, tags)`` tuple where ``score`` is capped at 5.0 and
        ``tags`` is the list of matched keyword strings.
    """
    score = 0.0
    tags: list[str] = []
    title_lower = offer.title.lower()
    company_lower = offer.company.lower()
    location_lower = (offer.location or "").lower()

    # Keyword matches in title
    search_keywords: list[str] = settings.get("search", {}).get("keywords", [])
    for kw in search_keywords:
        if kw.lower() in title_lower:
            score += 1.0
            tags.append(kw)

    # Target company match
    target_companies = _all_target_companies(settings)
    if company_lower in target_companies:
        score += 1.0
        tags.append(f"target:{offer.company}")

    # Location match
    search_location: str = settings.get("search", {}).get("location", "").lower()
    if search_location and search_location in location_lower:
        score += 1.0
        tags.append(f"location:{offer.location}")

    # Junior / alternance bonus
    for pattern in _JUNIOR_PATTERNS:
        if pattern in title_lower:
            score += 0.5
            tags.append(f"seniority:{pattern}")
            break  # only one bonus

    return min(score, 5.0), tags


def pre_filter(offers: list[RawOffer], settings: dict) -> list[RawOffer]:
    """Score all offers and return only those meeting the consider threshold.

    The function mutates ``offer.score`` and ``offer.tags`` in-place before
    filtering so that downstream consumers always see scored offers.

    Args:
        offers: List of ``RawOffer`` to evaluate.
        settings: Parsed settings dict (from ``load_settings``).

    Returns:
        Filtered list of ``RawOffer`` with score >= ``scoring.thresholds.consider``.
    """
    threshold: float = (
        settings.get("scoring", {}).get("thresholds", {}).get("consider", 3.0)
    )

    kept: list[RawOffer] = []
    for offer in offers:
        score, tags = score_offer(offer, settings)
        offer.score = score
        offer.tags = tags
        if score >= threshold:
            kept.append(offer)
        else:
            logger.debug(
                "Dropped [score=%.1f]: %s @ %s", score, offer.title, offer.company
            )

    logger.info("Pre-filter: kept %d / %d offers (threshold %.1f)", len(kept), len(offers), threshold)
    return kept
```

### 5.3 — Run tests, all must pass

- [ ] Run:

```bash
.venv/bin/pytest tests/test_pre_filter.py -v
```

Expected: all 14 tests green.

### 5.4 — Commit

- [ ] Commit:

```bash
git add scripts/pre_filter.py tests/test_pre_filter.py
git commit -m "feat: add pre_filter with keyword scoring and threshold filtering"
```

---

## Task 6 — `scripts/daily_report.py` (TDD)

The daily report script ties everything together: it runs the full pipeline
(scan → dedup → pre_filter) and writes a Markdown file to
`reports/daily-YYYY-MM-DD.md`.

### 6.1 — Write failing tests (`tests/test_daily_report.py`)

- [ ] Create `/home/missia03/Projects/career-ops-fr/tests/test_daily_report.py`:

```python
"""Tests for daily_report module."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts.daily_report import render_report, report_path
from scripts.models import RawOffer


def _offer(
    title: str,
    company: str,
    portal: str = "wtfj",
    score: float = 4.0,
    location: str = "Paris",
    url: str = "https://example.com/offer",
) -> RawOffer:
    offer = RawOffer(
        title=title,
        company=company,
        url=url,
        portal=portal,
        location=location,
        date_posted=date(2026, 5, 25),
        score=score,
        tags=["AI Engineer", "target:Mistral AI"],
    )
    return offer


class TestReportPath:
    """Tests for report_path()."""

    def test_returns_path_object(self) -> None:
        p = report_path(date(2026, 5, 25))
        assert isinstance(p, Path)

    def test_filename_format(self) -> None:
        p = report_path(date(2026, 5, 25))
        assert p.name == "daily-2026-05-25.md"

    def test_parent_is_reports_dir(self) -> None:
        p = report_path(date(2026, 5, 25))
        assert p.parent.name == "reports"


class TestRenderReport:
    """Tests for render_report()."""

    def test_empty_offers_produces_valid_markdown(self) -> None:
        md = render_report([], report_date=date(2026, 5, 25))
        assert "# Daily Report" in md
        assert "2026-05-25" in md
        assert "No offers" in md or "0 offer" in md

    def test_offer_title_in_output(self) -> None:
        offers = [_offer("AI Engineer", "Mistral AI")]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "AI Engineer" in md

    def test_offer_company_in_output(self) -> None:
        offers = [_offer("AI Engineer", "Mistral AI")]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "Mistral AI" in md

    def test_offer_url_in_output(self) -> None:
        offers = [_offer("AI Engineer", "Mistral AI", url="https://example.com/offer/42")]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "https://example.com/offer/42" in md

    def test_offer_score_in_output(self) -> None:
        offers = [_offer("AI Engineer", "Mistral AI", score=4.5)]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "4.5" in md

    def test_offers_sorted_by_score_descending(self) -> None:
        offers = [
            _offer("B offer", "Corp B", score=3.5),
            _offer("A offer", "Corp A", score=4.5),
            _offer("C offer", "Corp C", score=3.0),
        ]
        md = render_report(offers, report_date=date(2026, 5, 25))
        pos_a = md.index("A offer")
        pos_b = md.index("B offer")
        pos_c = md.index("C offer")
        assert pos_a < pos_b < pos_c

    def test_portal_label_in_output(self) -> None:
        offers = [_offer("AI Engineer", "Mistral AI", portal="apec")]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "apec" in md.lower()

    def test_total_count_in_header(self) -> None:
        offers = [
            _offer("AI Engineer", "Mistral AI"),
            _offer("ML Engineer", "Hugging Face"),
        ]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "2" in md

    def test_recommend_section_present(self) -> None:
        offers = [_offer("AI Engineer", "Mistral AI", score=4.5)]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "Recommend" in md or "recommend" in md

    def test_consider_section_present(self) -> None:
        offers = [_offer("ML Engineer", "Hugging Face", score=3.2)]
        md = render_report(offers, report_date=date(2026, 5, 25))
        assert "Consider" in md or "consider" in md
```

- [ ] Run tests — all should FAIL:

```bash
.venv/bin/pytest tests/test_daily_report.py -v 2>&1 | head -30
```

### 6.2 — Implement `scripts/daily_report.py`

- [ ] Create `/home/missia03/Projects/career-ops-fr/scripts/daily_report.py`:

```python
"""Daily report generator.

Runs the full pipeline (scan → dedup → pre_filter) and writes a Markdown
report to reports/daily-YYYY-MM-DD.md.

Usage:
    python scripts/daily_report.py
    python scripts/daily_report.py --date 2026-05-25
    python scripts/daily_report.py --dry-run   # print to stdout, do not write
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date
from pathlib import Path
from textwrap import indent

from scripts.dedup import deduplicate
from scripts.models import RawOffer
from scripts.pre_filter import load_settings, pre_filter
from scripts.scan_portals import list_portal_ids, run_scan

logger = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).parent.parent / "reports"
_RECOMMEND_THRESHOLD = 4.0
_CONSIDER_THRESHOLD = 3.0


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable)
# ---------------------------------------------------------------------------


def report_path(report_date: date) -> Path:
    """Return the Path where the daily report will be written.

    Args:
        report_date: The date for which the report is generated.

    Returns:
        Path object pointing to ``reports/daily-YYYY-MM-DD.md``.
    """
    return _REPORTS_DIR / f"daily-{report_date.isoformat()}.md"


def render_report(offers: list[RawOffer], *, report_date: date) -> str:
    """Render the daily report as a Markdown string.

    Offers are split into two sections:
    - **Recommend** (score >= 4.0) sorted descending by score
    - **Consider**  (3.0 <= score < 4.0) sorted descending by score

    Args:
        offers: List of pre-filtered, scored ``RawOffer`` objects.
        report_date: Date to display in the report header.

    Returns:
        Complete Markdown string for the report.
    """
    recommend = sorted(
        [o for o in offers if o.score >= _RECOMMEND_THRESHOLD],
        key=lambda o: o.score,
        reverse=True,
    )
    consider = sorted(
        [o for o in offers if _CONSIDER_THRESHOLD <= o.score < _RECOMMEND_THRESHOLD],
        key=lambda o: o.score,
        reverse=True,
    )

    lines: list[str] = [
        f"# Daily Report — {report_date.isoformat()}",
        "",
        f"**Total offers:** {len(offers)}  |  "
        f"**Recommend:** {len(recommend)}  |  "
        f"**Consider:** {len(consider)}",
        "",
        "---",
        "",
    ]

    if not offers:
        lines.append("_No offers matched the pre-filter threshold today._")
        return "\n".join(lines)

    # Recommend section
    lines.append(f"## Recommend ({len(recommend)})")
    lines.append("")
    if recommend:
        for offer in recommend:
            lines.extend(_render_offer_entry(offer))
    else:
        lines.append("_No offers in this category._")
        lines.append("")

    # Consider section
    lines.append(f"## Consider ({len(consider)})")
    lines.append("")
    if consider:
        for offer in consider:
            lines.extend(_render_offer_entry(offer))
    else:
        lines.append("_No offers in this category._")
        lines.append("")

    return "\n".join(lines)


def _render_offer_entry(offer: RawOffer) -> list[str]:
    """Render a single offer as a Markdown list block.

    Args:
        offer: A scored ``RawOffer``.

    Returns:
        List of Markdown lines for this offer.
    """
    date_str = offer.date_posted.isoformat() if offer.date_posted else "N/A"
    tags_str = ", ".join(offer.tags) if offer.tags else "—"
    location_str = offer.location or "N/A"

    return [
        f"### [{offer.title}]({offer.url})",
        f"- **Company:** {offer.company}",
        f"- **Portal:** `{offer.portal}`",
        f"- **Location:** {location_str}",
        f"- **Posted:** {date_str}",
        f"- **Score:** {offer.score:.1f} / 5.0",
        f"- **Tags:** {tags_str}",
        "",
    ]


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


async def _run_pipeline(settings: dict) -> list[RawOffer]:
    """Execute the full scan → dedup → pre_filter pipeline.

    Args:
        settings: Parsed settings dict.

    Returns:
        Filtered, scored list of ``RawOffer``.
    """
    keywords: str = settings.get("search", {}).get("keywords", ["AI Engineer"])[0]
    location: str = settings.get("search", {}).get("location", "Paris")
    portal_ids = list_portal_ids()

    logger.info("Starting scan of %d portals for '%s' in %s", len(portal_ids), keywords, location)
    raw_offers = await run_scan(portal_ids, keywords=keywords, location=location)
    logger.info("Scraped %d raw offers", len(raw_offers))

    deduped = deduplicate(raw_offers)
    logger.info("After dedup: %d offers", len(deduped))

    filtered = pre_filter(deduped, settings)
    logger.info("After pre-filter: %d offers", len(filtered))

    return filtered


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate daily job offers report")
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        default=None,
        help="Report date (default: today)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print report to stdout instead of writing to file",
    )
    return parser


def main() -> None:
    """CLI entry point for daily_report."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = _build_cli_parser()
    args = parser.parse_args()

    report_date = date.fromisoformat(args.date) if args.date else date.today()
    settings = load_settings()

    offers = asyncio.run(_run_pipeline(settings))
    report_md = render_report(offers, report_date=report_date)

    if args.dry_run:
        print(report_md)
    else:
        path = report_path(report_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report_md, encoding="utf-8")
        print(f"Report written to {path}")
        print(f"Total: {len(offers)} offers")


if __name__ == "__main__":
    main()
```

### 6.3 — Run tests, all must pass

- [ ] Run the full test suite:

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests green (scan_portals, dedup, pre_filter, daily_report).

### 6.4 — Commit

- [ ] Commit:

```bash
git add scripts/daily_report.py tests/test_daily_report.py
git commit -m "feat: add daily_report with full scan-dedup-filter pipeline"
```

---

## Final validation

- [ ] Run the complete test suite with coverage:

```bash
.venv/bin/pytest tests/ -v --tb=short
```

- [ ] Verify the scanner CLI works (dry run against a single portal — will attempt real browser, may fail without network):

```bash
.venv/bin/python scripts/scan_portals.py --portal wtfj --keywords "AI Engineer" --location "Paris" 2>&1 | head -20
```

- [ ] Verify the report generator CLI (dry run against real portals OR with empty list):

```bash
.venv/bin/python scripts/daily_report.py --dry-run 2>&1 | head -30
```

- [ ] Final commit tagging the plan as complete:

```bash
git add -A
git commit -m "chore: complete Plan 2 portal scanning implementation"
```

---

## Files produced by this plan

```
requirements.txt                           (updated)
scripts/models.py                          (new)
scripts/scan_portals.py                    (new)
scripts/dedup.py                           (new)
scripts/pre_filter.py                      (new)
scripts/daily_report.py                    (new)
portals/fr/wtfj.yaml                       (new)
portals/fr/indeed.yaml                     (new)
portals/fr/apec.yaml                       (new)
portals/fr/linkedin.yaml                   (new)
portals/fr/glassdoor.yaml                  (new)
reports/.gitkeep                           (new)
tests/test_scan_portals.py                 (new)
tests/test_dedup.py                        (new)
tests/test_pre_filter.py                   (new)
tests/test_daily_report.py                 (new)
```
