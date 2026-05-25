# Plan 7 — ATS Scanner + Pipeline Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix broken portal selectors (apec, wtfj), add French keywords to settings.yaml, and add an ATS scanner querying Greenhouse / Lever / Ashby public JSON APIs for the ~40 target companies.

**Architecture:** Three independent tasks. Task 1 fixes YAML selectors for apec and wtfj by inspecting real DOM with Playwright. Task 2 adds French keywords to settings.yaml. Task 3 creates `scripts/scan_ats.py` (pure `httpx` async, provider pattern) + `config/ats_map.yaml`, then wires `scan_ats()` into `import_offers._run_pipeline()`.

**Tech Stack:** Python 3, httpx (async HTTP), pytest, pytest-httpx (mocking), PyYAML, existing Playwright scraper

---

## Key current state

**`scripts/import_offers._run_pipeline()`** (lines 110–126):
```python
async def _run_pipeline(settings: dict) -> list[RawOffer]:
    keyword_list: list[str] = settings.get("search", {}).get("keywords", ["AI Engineer"])
    keywords = keyword_list[0] if keyword_list else "AI Engineer"
    location: str = settings.get("search", {}).get("location", "Paris")
    portal_ids = list_portal_ids()
    raw = await run_scan(portal_ids, keywords=keywords, location=location)
    deduped = deduplicate(raw)
    filtered = pre_filter(deduped, settings)
    return filtered
```

**`scripts/models.RawOffer`**:
```python
@dataclass
class RawOffer:
    title: str
    company: str
    url: str
    portal: str
    location: Optional[str] = None
    date_posted: Optional[date] = None
    score: float = 0.0
    tags: list[str] = field(default_factory=list)
```

**Provider API contracts:**
- Greenhouse: `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs` → `{"jobs": [{"title": ..., "absolute_url": ..., "location": {"name": ...}}]}`
- Lever: `GET https://api.lever.co/v0/postings/{slug}` → `[{"text": ..., "hostedUrl": ..., "categories": {"location": ...}}]`
- Ashby: `GET https://api.ashbyhq.com/posting-api/job-board/{slug}` → `{"jobs": [{"title": ..., "jobUrl": ..., "location": ...}]}`

Slugs are extracted from the `careers_url` pattern in `ats_map.yaml`.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `portals/fr/apec.yaml` | Modify | Fix stale CSS selectors |
| `portals/fr/wtfj.yaml` | Modify | Fix stale CSS selectors |
| `config/settings.yaml` | Modify | Add French keyword equivalents |
| `config/ats_map.yaml` | Create | Company → careers_url mapping |
| `scripts/scan_ats.py` | Create | `resolve_provider`, `GreenhouseProvider`, `LeverProvider`, `AshbyProvider`, `scan_ats`, CLI |
| `tests/test_scan_ats.py` | Create | Unit tests for all providers + `scan_ats` integration |
| `scripts/import_offers.py` | Modify | Wire `scan_ats()` into `_run_pipeline()` |

---

### Task 1: Fix portal selectors (apec + wtfj)

**Files:**
- Modify: `portals/fr/apec.yaml`
- Modify: `portals/fr/wtfj.yaml`

No automated tests for YAML selector changes — verified by running the scanner directly.

- [ ] **Step 1: Inspect the real APEC DOM**

```bash
cd /home/missia03/Projects/career-ops-fr
PYTHONPATH=. .venv/bin/python - <<'EOF'
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, channel="chrome")
        page = await browser.new_page()
        await page.goto(
            "https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles=AI+Engineer&lieuTravail=Paris",
            wait_until="networkidle", timeout=30000
        )
        # Print the first 3000 chars of the job list area
        content = await page.content()
        # Find the job cards area
        idx = content.find('class="result')
        print(content[max(0,idx-200):idx+3000])
        await browser.close()

asyncio.run(main())
EOF
```

Read the output and identify the actual CSS classes for:
- offer card container
- job title
- company name
- job URL (href)
- location
- date

- [ ] **Step 2: Update portals/fr/apec.yaml with real selectors**

Based on DOM inspection, update the `selectors` section. The current (broken) selectors are:
```yaml
selectors:
  offer_card: "div.result-item"
  title: "h2.result-item-title a"
  company: "span.result-item-company"
  url: "h2.result-item-title a"
  location: "span.result-item-location"
  date: "span.result-item-date"
```

Replace with actual selectors found in step 1. Example (verify against real DOM — do not copy blindly):
```yaml
selectors:
  offer_card: "article.result"
  title: "a.job-card-title"
  company: "span.company-name"
  url: "a.job-card-title"
  location: "span.job-location"
  date: "span.job-date"
```

- [ ] **Step 3: Smoke-test apec**

```bash
cd /home/missia03/Projects/career-ops-fr
PYTHONPATH=. .venv/bin/python scripts/scan_portals.py --portal apec --keywords "AI Engineer" --location "Paris" --max-pages 1
```

Expected: at least 1 offer printed. If still 0, go back to step 1 and inspect more carefully.

- [ ] **Step 4: Inspect the real WTFJ DOM**

```bash
cd /home/missia03/Projects/career-ops-fr
PYTHONPATH=. .venv/bin/python - <<'EOF'
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, channel="chrome")
        page = await browser.new_page()
        await page.goto(
            "https://www.welcometothejungle.com/fr/jobs?query=AI+Engineer&aroundQuery=Paris",
            wait_until="networkidle", timeout=30000
        )
        content = await page.content()
        # Look for data-testid attributes
        import re
        testids = re.findall(r'data-testid="[^"]*"', content)
        for t in sorted(set(testids)):
            print(t)
        await browser.close()

asyncio.run(main())
EOF
```

Identify which `data-testid` values match offer cards, title, company, url, location, date.

- [ ] **Step 5: Update portals/fr/wtfj.yaml with real selectors**

Current selectors:
```yaml
selectors:
  offer_card: "li[data-testid='search-results-list-item-wrapper']"
  title: "h3[data-testid='job-title']"
  company: "span[data-testid='company-title']"
  url: "a[data-testid='job-link']"
  location: "span[data-testid='job-location']"
  date: "time"
```

Replace with selectors confirmed in step 4.

- [ ] **Step 6: Smoke-test wtfj**

```bash
cd /home/missia03/Projects/career-ops-fr
PYTHONPATH=. .venv/bin/python scripts/scan_portals.py --portal wtfj --keywords "AI Engineer" --location "Paris" --max-pages 1
```

Expected: at least 1 offer printed.

- [ ] **Step 7: Run full test suite — no regressions**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/ -v
```

Expected: 87 tests pass.

- [ ] **Step 8: Commit**

```bash
git add portals/fr/apec.yaml portals/fr/wtfj.yaml
git commit -m "fix: update apec and wtfj selectors to match current DOM"
```

---

### Task 2: Add French keywords to settings.yaml

**Files:**
- Modify: `config/settings.yaml`

No code changes, no tests needed. Verified by re-running the dry-run pipeline.

- [ ] **Step 1: Update config/settings.yaml**

Replace the `search.keywords` section with:

```yaml
search:
  keywords:
    - "AI Engineer"
    - "ML Engineer"
    - "Machine Learning Engineer"
    - "Computer Vision Engineer"
    - "Deep Learning Engineer"
    - "LLM Engineer"
    - "RAG Engineer"
    - "NLP Engineer"
    - "Ingénieur IA"
    - "Ingénieur ML"
    - "Ingénieur Machine Learning"
    - "Ingénieur Computer Vision"
    - "Ingénieur Deep Learning"
    - "Data Scientist"
    - "Machine Learning"
  location: "Paris"
  contract: "CDI"
  experience_max_years: 3
```

Keep all other sections unchanged.

- [ ] **Step 2: Run full test suite — no regressions**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/ -v
```

Expected: 87 tests pass (settings.yaml change only affects runtime scoring, not tests).

- [ ] **Step 3: Commit**

```bash
git add config/settings.yaml
git commit -m "feat: add French keyword equivalents to settings.yaml"
```

---

### Task 3: ATS Scanner (TDD)

**Files:**
- Create: `config/ats_map.yaml`
- Create: `scripts/scan_ats.py`
- Create: `tests/test_scan_ats.py`
- Modify: `scripts/import_offers.py` (lines 110–126 `_run_pipeline`)

#### Step 1: Install dependencies

- [ ] **Install httpx and pytest-httpx**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pip install httpx==0.28.1 pytest-httpx==0.35.0
```

Verify:
```bash
.venv/bin/pip show httpx pytest-httpx | grep "Name\|Version"
```

Expected:
```
Name: httpx
Version: 0.28.1
Name: pytest-httpx
Version: 0.35.0
```

Update `requirements.txt`:
```bash
echo "httpx==0.28.1" >> requirements.txt
echo "pytest-httpx==0.35.0" >> requirements.txt
```

#### Step 2: Write failing tests

- [ ] **Create tests/test_scan_ats.py**

```python
"""Tests for scan_ats: providers, resolve_provider, scan_ats integration."""

from __future__ import annotations

import pytest
import pytest_asyncio
from pytest_httpx import HTTPXMock

from scripts.scan_ats import (
    AshbyProvider,
    GreenhouseProvider,
    LeverProvider,
    resolve_provider,
    scan_ats,
)


class TestResolveProvider:
    def test_greenhouse_url_detected(self) -> None:
        entry = {"name": "Acme", "careers_url": "https://job-boards.greenhouse.io/acme"}
        provider, slug = resolve_provider(entry)
        assert provider is GreenhouseProvider
        assert slug == "acme"

    def test_greenhouse_boards_url_detected(self) -> None:
        entry = {"name": "Acme", "careers_url": "https://boards.greenhouse.io/acme"}
        provider, slug = resolve_provider(entry)
        assert provider is GreenhouseProvider
        assert slug == "acme"

    def test_lever_url_detected(self) -> None:
        entry = {"name": "Acme", "careers_url": "https://jobs.lever.co/acme"}
        provider, slug = resolve_provider(entry)
        assert provider is LeverProvider
        assert slug == "acme"

    def test_ashby_url_detected(self) -> None:
        entry = {"name": "Acme", "careers_url": "https://jobs.ashbyhq.com/acme"}
        provider, slug = resolve_provider(entry)
        assert provider is AshbyProvider
        assert slug == "acme"

    def test_unknown_url_returns_none(self) -> None:
        entry = {"name": "Acme", "careers_url": "https://www.acme.com/careers"}
        assert resolve_provider(entry) is None

    def test_missing_careers_url_returns_none(self) -> None:
        entry = {"name": "Acme"}
        assert resolve_provider(entry) is None


class TestGreenhouseProvider:
    @pytest.mark.asyncio
    async def test_fetch_returns_offers(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://boards-api.greenhouse.io/v1/boards/acme/jobs",
            json={
                "jobs": [
                    {
                        "title": "AI Engineer",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                        "location": {"name": "Paris"},
                    },
                    {
                        "title": "ML Engineer",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
                        "location": {"name": "Remote"},
                    },
                ]
            },
        )
        import httpx
        async with httpx.AsyncClient() as client:
            offers = await GreenhouseProvider.fetch("Acme Corp", "acme", client)
        assert len(offers) == 2
        assert offers[0].title == "AI Engineer"
        assert offers[0].company == "Acme Corp"
        assert offers[0].url == "https://boards.greenhouse.io/acme/jobs/1"
        assert offers[0].location == "Paris"
        assert offers[0].portal == "greenhouse"

    @pytest.mark.asyncio
    async def test_fetch_empty_jobs_array(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://boards-api.greenhouse.io/v1/boards/acme/jobs",
            json={"jobs": []},
        )
        import httpx
        async with httpx.AsyncClient() as client:
            offers = await GreenhouseProvider.fetch("Acme Corp", "acme", client)
        assert offers == []

    @pytest.mark.asyncio
    async def test_fetch_http_error_returns_empty(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://boards-api.greenhouse.io/v1/boards/acme/jobs",
            status_code=404,
        )
        import httpx
        async with httpx.AsyncClient() as client:
            offers = await GreenhouseProvider.fetch("Acme Corp", "acme", client)
        assert offers == []


class TestLeverProvider:
    @pytest.mark.asyncio
    async def test_fetch_returns_offers(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acme",
            json=[
                {
                    "text": "Data Scientist",
                    "hostedUrl": "https://jobs.lever.co/acme/123",
                    "categories": {"location": "Paris, France"},
                }
            ],
        )
        import httpx
        async with httpx.AsyncClient() as client:
            offers = await LeverProvider.fetch("Acme Corp", "acme", client)
        assert len(offers) == 1
        assert offers[0].title == "Data Scientist"
        assert offers[0].company == "Acme Corp"
        assert offers[0].url == "https://jobs.lever.co/acme/123"
        assert offers[0].location == "Paris, France"
        assert offers[0].portal == "lever"

    @pytest.mark.asyncio
    async def test_fetch_empty_returns_empty(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acme",
            json=[],
        )
        import httpx
        async with httpx.AsyncClient() as client:
            offers = await LeverProvider.fetch("Acme Corp", "acme", client)
        assert offers == []

    @pytest.mark.asyncio
    async def test_fetch_http_500_returns_empty(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acme",
            status_code=500,
        )
        import httpx
        async with httpx.AsyncClient() as client:
            offers = await LeverProvider.fetch("Acme Corp", "acme", client)
        assert offers == []


class TestAshbyProvider:
    @pytest.mark.asyncio
    async def test_fetch_returns_offers(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.ashbyhq.com/posting-api/job-board/acme",
            json={
                "jobs": [
                    {
                        "title": "LLM Engineer",
                        "jobUrl": "https://jobs.ashbyhq.com/acme/abc",
                        "location": "Paris",
                    }
                ]
            },
        )
        import httpx
        async with httpx.AsyncClient() as client:
            offers = await AshbyProvider.fetch("Acme Corp", "acme", client)
        assert len(offers) == 1
        assert offers[0].title == "LLM Engineer"
        assert offers[0].portal == "ashby"

    @pytest.mark.asyncio
    async def test_fetch_empty_jobs_returns_empty(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://api.ashbyhq.com/posting-api/job-board/acme",
            json={"jobs": []},
        )
        import httpx
        async with httpx.AsyncClient() as client:
            offers = await AshbyProvider.fetch("Acme Corp", "acme", client)
        assert offers == []


class TestScanAts:
    @pytest.mark.asyncio
    async def test_returns_offers_from_all_providers(
        self, httpx_mock: HTTPXMock, tmp_path
    ) -> None:
        ats_map = tmp_path / "ats_map.yaml"
        ats_map.write_text(
            "- name: 'Acme GH'\n  careers_url: 'https://job-boards.greenhouse.io/acme'\n"
            "- name: 'Acme Lever'\n  careers_url: 'https://jobs.lever.co/acmelever'\n"
        )
        httpx_mock.add_response(
            url="https://boards-api.greenhouse.io/v1/boards/acme/jobs",
            json={"jobs": [{"title": "AI Eng", "absolute_url": "https://gh.io/1", "location": {"name": "Paris"}}]},
        )
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acmelever",
            json=[{"text": "ML Eng", "hostedUrl": "https://lever.co/1", "categories": {"location": "Paris"}}],
        )
        offers = await scan_ats(ats_map_path=ats_map)
        assert len(offers) == 2

    @pytest.mark.asyncio
    async def test_company_filter(self, httpx_mock: HTTPXMock, tmp_path) -> None:
        ats_map = tmp_path / "ats_map.yaml"
        ats_map.write_text(
            "- name: 'Acme'\n  careers_url: 'https://jobs.lever.co/acme'\n"
            "- name: 'Beta'\n  careers_url: 'https://jobs.lever.co/beta'\n"
        )
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acme",
            json=[{"text": "Dev", "hostedUrl": "https://lever.co/1", "categories": {"location": ""}}],
        )
        offers = await scan_ats(ats_map_path=ats_map, company_filter="Acme")
        assert len(offers) == 1
        assert offers[0].company == "Acme"

    @pytest.mark.asyncio
    async def test_unknown_provider_skipped(self, httpx_mock: HTTPXMock, tmp_path) -> None:
        ats_map = tmp_path / "ats_map.yaml"
        ats_map.write_text(
            "- name: 'Unknown Co'\n  careers_url: 'https://custom.com/careers'\n"
        )
        offers = await scan_ats(ats_map_path=ats_map)
        assert offers == []

    @pytest.mark.asyncio
    async def test_keyword_filter(self, httpx_mock: HTTPXMock, tmp_path) -> None:
        ats_map = tmp_path / "ats_map.yaml"
        ats_map.write_text(
            "- name: 'Acme'\n  careers_url: 'https://jobs.lever.co/acme'\n"
        )
        httpx_mock.add_response(
            url="https://api.lever.co/v0/postings/acme",
            json=[
                {"text": "AI Engineer", "hostedUrl": "https://lever.co/1", "categories": {"location": "Paris"}},
                {"text": "Office Manager", "hostedUrl": "https://lever.co/2", "categories": {"location": "Paris"}},
            ],
        )
        offers = await scan_ats(ats_map_path=ats_map, keywords=["AI Engineer"])
        assert len(offers) == 1
        assert offers[0].title == "AI Engineer"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/test_scan_ats.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'GreenhouseProvider' from 'scripts.scan_ats'`

#### Step 4: Implement scan_ats.py

- [ ] **Create scripts/scan_ats.py**

```python
"""ATS Scanner: queries Greenhouse, Lever, and Ashby public JSON APIs.

No Playwright — pure httpx async HTTP. Provider is auto-detected from
the careers_url pattern in config/ats_map.yaml.

Usage:
    python scripts/scan_ats.py
    python scripts/scan_ats.py --company "Mistral AI"
    python scripts/scan_ats.py --keywords "AI Engineer" "Machine Learning"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

import httpx
import yaml

from scripts.models import RawOffer

logger = logging.getLogger(__name__)

_DEFAULT_ATS_MAP = Path(__file__).parent.parent / "config" / "ats_map.yaml"
_TIMEOUT = 10.0


class GreenhouseProvider:
    id = "greenhouse"

    @staticmethod
    async def fetch(company_name: str, slug: str, client: httpx.AsyncClient) -> list[RawOffer]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        try:
            resp = await client.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("[greenhouse/%s] Request failed: %s", slug, exc)
            return []
        jobs = resp.json().get("jobs", [])
        offers = []
        for j in jobs:
            title = j.get("title", "").strip()
            job_url = j.get("absolute_url", "").strip()
            location = (j.get("location") or {}).get("name", "").strip() or None
            if not title:
                continue
            offers.append(
                RawOffer(
                    title=title,
                    company=company_name,
                    url=job_url,
                    portal="greenhouse",
                    location=location,
                )
            )
        return offers


class LeverProvider:
    id = "lever"

    @staticmethod
    async def fetch(company_name: str, slug: str, client: httpx.AsyncClient) -> list[RawOffer]:
        url = f"https://api.lever.co/v0/postings/{slug}"
        try:
            resp = await client.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("[lever/%s] Request failed: %s", slug, exc)
            return []
        jobs = resp.json()
        if not isinstance(jobs, list):
            return []
        offers = []
        for j in jobs:
            title = j.get("text", "").strip()
            job_url = j.get("hostedUrl", "").strip()
            location = (j.get("categories") or {}).get("location", "").strip() or None
            if not title:
                continue
            offers.append(
                RawOffer(
                    title=title,
                    company=company_name,
                    url=job_url,
                    portal="lever",
                    location=location,
                )
            )
        return offers


class AshbyProvider:
    id = "ashby"

    @staticmethod
    async def fetch(company_name: str, slug: str, client: httpx.AsyncClient) -> list[RawOffer]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        try:
            resp = await client.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("[ashby/%s] Request failed: %s", slug, exc)
            return []
        jobs = resp.json().get("jobs", [])
        offers = []
        for j in jobs:
            title = j.get("title", "").strip()
            job_url = j.get("jobUrl", "").strip()
            location = (j.get("location") or "").strip() or None
            if not title:
                continue
            offers.append(
                RawOffer(
                    title=title,
                    company=company_name,
                    url=job_url,
                    portal="ashby",
                    location=location,
                )
            )
        return offers


_PROVIDER_PATTERNS: list[tuple[re.Pattern, type]] = [
    (re.compile(r"greenhouse\.io/([^/?#]+)"), GreenhouseProvider),
    (re.compile(r"jobs\.lever\.co/([^/?#]+)"), LeverProvider),
    (re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)"), AshbyProvider),
]


def resolve_provider(entry: dict) -> Optional[tuple[type, str]]:
    """Return (ProviderClass, slug) or None if URL is not recognised."""
    url = entry.get("careers_url", "")
    if not url:
        return None
    for pattern, provider_cls in _PROVIDER_PATTERNS:
        m = pattern.search(url)
        if m:
            return provider_cls, m.group(1)
    return None


def _load_ats_map(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, list) else []


async def scan_ats(
    ats_map_path: Path = _DEFAULT_ATS_MAP,
    *,
    company_filter: Optional[str] = None,
    keywords: Optional[list[str]] = None,
) -> list[RawOffer]:
    """Scan all companies in ats_map.yaml and return RawOffer list.

    company_filter: if set, only scan that company (case-insensitive match on name).
    keywords: if set, keep only offers whose title contains at least one keyword
              (case-insensitive substring match).
    """
    entries = _load_ats_map(ats_map_path)
    if company_filter:
        entries = [e for e in entries if e.get("name", "").lower() == company_filter.lower()]

    all_offers: list[RawOffer] = []
    async with httpx.AsyncClient() as client:
        tasks = []
        meta = []
        for entry in entries:
            resolved = resolve_provider(entry)
            if resolved is None:
                logger.warning("[ats] Unknown provider for '%s' — skipping", entry.get("name"))
                continue
            provider_cls, slug = resolved
            tasks.append(provider_cls.fetch(entry["name"], slug, client))
            meta.append(entry["name"])

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(meta, results):
            if isinstance(result, Exception):
                logger.error("[ats/%s] Fetch failed: %s", name, result)
            else:
                all_offers.extend(result)

    if keywords:
        kw_lower = [k.lower() for k in keywords]
        all_offers = [
            o for o in all_offers
            if any(kw in o.title.lower() for kw in kw_lower)
        ]

    logger.info("[ats] Total offers fetched: %d", len(all_offers))
    return all_offers


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Scan ATS job boards for target companies")
    parser.add_argument("--company", default=None, metavar="NAME", help="Filter to a single company")
    parser.add_argument(
        "--keywords", nargs="+", default=None, metavar="KW",
        help="Only show offers matching these keywords (case-insensitive)"
    )
    args = parser.parse_args()

    offers = asyncio.run(scan_ats(company_filter=args.company, keywords=args.keywords))
    for o in offers:
        print(f"[{o.portal}] {o.title} @ {o.company} — {o.url}")
    print(f"\nTotal: {len(offers)} offers")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/test_scan_ats.py -v
```

Expected: all 14 tests pass.

#### Step 6: Create ats_map.yaml

- [ ] **Create config/ats_map.yaml**

```yaml
# ATS job board map for career-ops-fr target companies.
# Provider is auto-detected from careers_url pattern.
# To add a company: add one entry with name + careers_url.
# Supported patterns: greenhouse.io, jobs.lever.co, jobs.ashbyhq.com

# --- Greenhouse ---
- name: "Mistral AI"
  careers_url: "https://job-boards.greenhouse.io/mistralai"

- name: "Dataiku"
  careers_url: "https://job-boards.greenhouse.io/dataiku"

- name: "Artefact"
  careers_url: "https://job-boards.greenhouse.io/artefact"

# --- Lever ---
- name: "Doctrine"
  careers_url: "https://jobs.lever.co/doctrine"

- name: "ContentSquare"
  careers_url: "https://jobs.lever.co/contentsquare"

- name: "Ekimetrics"
  careers_url: "https://jobs.lever.co/ekimetrics"

# --- Ashby ---
- name: "Nabla"
  careers_url: "https://jobs.ashbyhq.com/nabla"

- name: "Alan"
  careers_url: "https://jobs.ashbyhq.com/alan"

- name: "Owkin"
  careers_url: "https://jobs.ashbyhq.com/owkin"

# --- To be confirmed (ATS unknown — skipped until verified) ---
# Hugging Face: uses Workable (apply.workable.com/huggingface) — no public API
# Qonto, Doctolib, BlaBlaCar, Ledger, Algolia: ATS not confirmed
# Big tech (Google, Meta, Microsoft, Amazon, Apple): Workday — Plan 8
# ESN/grands groupes: SmartRecruiters — Plan 8
```

- [ ] **Step 7: Smoke-test the scanner**

```bash
cd /home/missia03/Projects/career-ops-fr
PYTHONPATH=. .venv/bin/python scripts/scan_ats.py --company "Mistral AI"
```

Expected: a list of current Mistral AI job postings printed, or `Total: 0 offers` if no openings (both are valid — no error means the HTTP call worked).

```bash
PYTHONPATH=. .venv/bin/python scripts/scan_ats.py 2>&1 | tail -3
```

Expected: `Total: N offers` with no ERROR lines.

#### Step 7: Wire scan_ats into import_offers._run_pipeline

- [ ] **Step 8: Update scripts/import_offers.py**

Add the import at the top of `import_offers.py` (after the existing imports):

```python
from scripts.scan_ats import scan_ats
```

Replace `_run_pipeline` (lines 110–126) with:

```python
async def _run_pipeline(settings: dict) -> list[RawOffer]:
    keyword_list: list[str] = settings.get("search", {}).get(
        "keywords", ["AI Engineer"]
    )
    keywords = keyword_list[0] if keyword_list else "AI Engineer"
    location: str = settings.get("search", {}).get("location", "Paris")
    portal_ids = list_portal_ids()
    logger.info(
        "Scanning %d portals for '%s' in %s", len(portal_ids), keywords, location
    )
    portal_raw = await run_scan(portal_ids, keywords=keywords, location=location)
    logger.info("Scraped %d raw offers from portals", len(portal_raw))
    ats_raw = await scan_ats(keywords=keyword_list)
    logger.info("Scraped %d raw offers from ATS", len(ats_raw))
    raw = portal_raw + ats_raw
    deduped = deduplicate(raw)
    logger.info("After dedup: %d offers", len(deduped))
    filtered = pre_filter(deduped, settings)
    logger.info("After pre-filter: %d offers", len(filtered))
    return filtered
```

- [ ] **Step 9: Run full test suite — no regressions**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/ -v
```

Expected: 87 + 14 = 101 tests pass, 0 failures.

- [ ] **Step 10: Run full pipeline dry-run**

```bash
cd /home/missia03/Projects/career-ops-fr
PYTHONPATH=. .venv/bin/python scripts/import_offers.py --dry-run 2>&1
```

Expected: INFO lines from both portal scan and ATS scan, then a list of scored offers (or `Total: 0 offers (dry run, nothing inserted)` if none pass the 3.0 threshold — that's fine).

- [ ] **Step 11: Commit**

```bash
git add config/ats_map.yaml scripts/scan_ats.py tests/test_scan_ats.py scripts/import_offers.py requirements.txt
git commit -m "feat: add ATS scanner (Greenhouse, Lever, Ashby) and wire into pipeline"
```

#### Step 12: Push and tag v0.7.0

- [ ] **Step 12: Push and tag**

```bash
git push github.com-personal HEAD:master
git tag v0.7.0 -m "Plan 7 complete: ATS scanner + pipeline fixes"
git push github.com-personal v0.7.0
```

Expected: tag `v0.7.0` on `git@github.com-personal:St4r4x/career-ops-fr.git`.

---

## Smoke-test checklist after Plan 7

```bash
# Verify apec and wtfj return results
PYTHONPATH=. .venv/bin/python scripts/scan_portals.py --portal apec --keywords "Ingénieur Machine Learning" --location "Paris" --max-pages 1
PYTHONPATH=. .venv/bin/python scripts/scan_portals.py --portal wtfj --keywords "Ingénieur IA" --location "Paris" --max-pages 1

# Verify ATS scanner works on a known company
PYTHONPATH=. .venv/bin/python scripts/scan_ats.py --company "Alan"

# Full pipeline dry-run
PYTHONPATH=. .venv/bin/python scripts/import_offers.py --dry-run 2>&1
```
