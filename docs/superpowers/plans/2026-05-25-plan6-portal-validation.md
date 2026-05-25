# Plan 6 — Portal Validation Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add portal status filtering (skip blocked portals gracefully) and a `--max-pages` CLI override to make individual portal smoke-testing easy, then mark LinkedIn and Glassdoor as `needs_auth` so daily runs don't fail on them.

**Architecture:** Add two pure helpers to `scan_portals.py` — `portal_is_active(config)` and `_effective_max_pages(config, override)` — both fully unit-testable without Playwright. Wire them into `scrape_portal` and `run_scan`. Update the 5 YAML configs with a `status:` field. The `--max-pages` arg in the CLI lets Arnaud run `python scripts/scan_portals.py --portal wtfj --max-pages 1` as a quick smoke test.

**Tech Stack:** Python 3, pytest, PyYAML, existing Playwright scraper

---

## Key current state

**`scripts/scan_portals.py`** relevant signatures (do not change return types):
```python
async def scrape_portal(portal_id: str, keywords: str, location: str) -> list[RawOffer]
async def run_scan(portal_ids: list[str], keywords: str, location: str) -> list[RawOffer]
```

**Portal status decisions:**
| Portal | `status` | Reason |
|---|---|---|
| wtfj | `active` | `data-testid` attrs are stable |
| apec | `active` | French public site, stable BEM classes |
| indeed | `active` | Accessible headlessly, may need selector tuning |
| linkedin | `needs_auth` | Blocks headless browsers aggressively |
| glassdoor | `needs_auth` | Cloudflare WAF + mandatory login |

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/scan_portals.py` | Modify | Add `portal_is_active`, `_effective_max_pages`, update `scrape_portal` + `run_scan` + `main()` |
| `portals/fr/wtfj.yaml` | Modify | Add `status: active` |
| `portals/fr/apec.yaml` | Modify | Add `status: active` |
| `portals/fr/indeed.yaml` | Modify | Add `status: active` |
| `portals/fr/linkedin.yaml` | Modify | Add `status: needs_auth` |
| `portals/fr/glassdoor.yaml` | Modify | Add `status: needs_auth` |
| `tests/test_scan_portals.py` | Modify | Add `TestPortalIsActive`, `TestEffectiveMaxPages` |

---

### Task 1: portal_is_active + _effective_max_pages helpers (TDD)

**Files:**
- Modify: `tests/test_scan_portals.py` — add two test classes
- Modify: `scripts/scan_portals.py` — add two helpers, wire into `scrape_portal`, `run_scan`, `main()`

Current `tests/test_scan_portals.py` imports:
```python
from scripts.scan_portals import (
    build_search_url,
    extract_offer_from_card_data,
    parse_date_string,
)
```

- [ ] **Step 1: Write the failing tests**

Append these two classes to the END of `tests/test_scan_portals.py` (after the existing `TestExtractOfferFromCardData` class):

```python
class TestPortalIsActive:
    def test_active_status_returns_true(self) -> None:
        from scripts.scan_portals import portal_is_active

        assert portal_is_active({"status": "active"}) is True

    def test_needs_auth_returns_false(self) -> None:
        from scripts.scan_portals import portal_is_active

        assert portal_is_active({"status": "needs_auth"}) is False

    def test_blocked_returns_false(self) -> None:
        from scripts.scan_portals import portal_is_active

        assert portal_is_active({"status": "blocked"}) is False

    def test_missing_status_defaults_to_active(self) -> None:
        from scripts.scan_portals import portal_is_active

        assert portal_is_active({}) is True

    def test_unknown_status_returns_false(self) -> None:
        from scripts.scan_portals import portal_is_active

        assert portal_is_active({"status": "maintenance"}) is False


class TestEffectiveMaxPages:
    def test_override_takes_precedence(self) -> None:
        from scripts.scan_portals import _effective_max_pages

        config = {"pagination": {"max_pages": 5}}
        assert _effective_max_pages(config, max_pages_override=1) == 1

    def test_yaml_value_used_when_no_override(self) -> None:
        from scripts.scan_portals import _effective_max_pages

        config = {"pagination": {"max_pages": 5}}
        assert _effective_max_pages(config, max_pages_override=None) == 5

    def test_defaults_to_3_when_not_in_yaml(self) -> None:
        from scripts.scan_portals import _effective_max_pages

        config = {"pagination": {}}
        assert _effective_max_pages(config, max_pages_override=None) == 3

    def test_override_zero_is_respected(self) -> None:
        from scripts.scan_portals import _effective_max_pages

        config = {"pagination": {"max_pages": 5}}
        assert _effective_max_pages(config, max_pages_override=0) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/test_scan_portals.py::TestPortalIsActive tests/test_scan_portals.py::TestEffectiveMaxPages -v
```

Expected: `ImportError: cannot import name 'portal_is_active'`

- [ ] **Step 3: Add the two helpers to scan_portals.py**

In `scripts/scan_portals.py`, add these two functions right before the `scrape_portal` function (after the `build_search_url` function, around line 77):

```python
def portal_is_active(config: dict) -> bool:
    return config.get("status", "active") == "active"


def _effective_max_pages(config: dict, max_pages_override: Optional[int] = None) -> int:
    if max_pages_override is not None:
        return max_pages_override
    return config["pagination"].get("max_pages", 3)
```

- [ ] **Step 4: Update scrape_portal to use the helpers**

In `scripts/scan_portals.py`, update the `scrape_portal` signature and body.

Current signature:
```python
async def scrape_portal(portal_id: str, keywords: str, location: str) -> list[RawOffer]:
```

New signature and early-return:
```python
async def scrape_portal(
    portal_id: str,
    keywords: str,
    location: str,
    *,
    max_pages_override: Optional[int] = None,
) -> list[RawOffer]:
    from playwright.async_api import async_playwright

    config = load_portal_config(portal_id)

    if not portal_is_active(config):
        logger.warning(
            "[%s] Skipped — status: %s", portal_id, config.get("status", "active")
        )
        return []

    selectors = config["selectors"]
    pagination = config["pagination"]
    base_url = config["base_url"]
    pagination_type = pagination["type"]
    page_size = pagination.get("page_size", 10)
    offers: list[RawOffer] = []
    max_pages = _effective_max_pages(config, max_pages_override)
```

The rest of the function body (from `async with async_playwright() as pw:` onward) is unchanged. The key changes are:
1. Add `*, max_pages_override: Optional[int] = None` parameter
2. Add `if not portal_is_active(config): return []` after `config = load_portal_config(portal_id)`
3. Move `from playwright.async_api import async_playwright` to just below the function signature (before the active check is fine — or keep it before `async with`)
4. Replace `max_pages = pagination.get("max_pages", 3)` with `max_pages = _effective_max_pages(config, max_pages_override)`

- [ ] **Step 5: Update run_scan to thread max_pages_override**

Current `run_scan`:
```python
async def run_scan(
    portal_ids: list[str], keywords: str, location: str
) -> list[RawOffer]:
    tasks = [scrape_portal(pid, keywords, location) for pid in portal_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_offers: list[RawOffer] = []
    for pid, result in zip(portal_ids, results):
        if isinstance(result, Exception):
            logger.error("[%s] Scrape failed: %s", pid, result)
        else:
            all_offers.extend(result)
    return all_offers
```

Replace with:
```python
async def run_scan(
    portal_ids: list[str],
    keywords: str,
    location: str,
    *,
    max_pages_override: Optional[int] = None,
) -> list[RawOffer]:
    tasks = [
        scrape_portal(pid, keywords, location, max_pages_override=max_pages_override)
        for pid in portal_ids
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_offers: list[RawOffer] = []
    for pid, result in zip(portal_ids, results):
        if isinstance(result, Exception):
            logger.error("[%s] Scrape failed: %s", pid, result)
        else:
            all_offers.extend(result)
    return all_offers
```

- [ ] **Step 6: Add --max-pages to scan_portals.py main()**

In the `main()` function of `scan_portals.py`, add one argument after `--location`:

```python
parser.add_argument(
    "--max-pages",
    type=int,
    default=None,
    metavar="N",
    help="Override max pages per portal (useful for smoke-testing)",
)
```

And update the `run_scan` call at the bottom of `main()`:
```python
offers = asyncio.run(
    run_scan(
        portal_ids,
        keywords=args.keywords,
        location=args.location,
        max_pages_override=args.max_pages,
    )
)
```

- [ ] **Step 7: Run the new tests to verify they pass**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/test_scan_portals.py::TestPortalIsActive tests/test_scan_portals.py::TestEffectiveMaxPages -v
```

Expected: 9 passed (5 + 4).

- [ ] **Step 8: Run the full test suite — no regressions**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/ -v
```

Expected: 87 tests pass (78 existing + 9 new).

- [ ] **Step 9: Commit**

```bash
git add scripts/scan_portals.py tests/test_scan_portals.py
git commit -m "feat: add portal status filtering and --max-pages CLI override"
```

---

### Task 2: Update YAML configs with status fields + tag v0.6.0

**Files:**
- Modify: `portals/fr/wtfj.yaml`
- Modify: `portals/fr/apec.yaml`
- Modify: `portals/fr/indeed.yaml`
- Modify: `portals/fr/linkedin.yaml`
- Modify: `portals/fr/glassdoor.yaml`

No tests needed — YAML changes are validated by the existing integration path and the `portal_is_active` unit tests.

- [ ] **Step 1: Add status to wtfj.yaml**

Add `status: active` as the second line (after `portal_id: wtfj`):

Full file content:
```yaml
portal_id: wtfj
status: active
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

- [ ] **Step 2: Add status to apec.yaml**

Full file content:
```yaml
portal_id: apec
status: active
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

- [ ] **Step 3: Add status to indeed.yaml**

Full file content:
```yaml
portal_id: indeed
status: active
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

- [ ] **Step 4: Add status to linkedin.yaml**

Full file content:
```yaml
portal_id: linkedin
status: needs_auth
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

- [ ] **Step 5: Add status to glassdoor.yaml**

Full file content:
```yaml
portal_id: glassdoor
status: needs_auth
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

- [ ] **Step 6: Verify YAML files are valid**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/python -c "
import yaml
from pathlib import Path
for p in sorted(Path('portals/fr').glob('*.yaml')):
    cfg = yaml.safe_load(p.read_text())
    print(p.name, '->', cfg.get('status', 'MISSING'))
"
```

Expected output:
```
apec.yaml -> active
glassdoor.yaml -> needs_auth
indeed.yaml -> active
linkedin.yaml -> needs_auth
wtfj.yaml -> active
```

- [ ] **Step 7: Run the full test suite**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/ -v
```

Expected: 87 tests pass.

- [ ] **Step 8: Commit the YAML updates**

```bash
git add portals/fr/
git commit -m "feat: add status field to portal configs; mark linkedin and glassdoor as needs_auth"
```

- [ ] **Step 9: Push and tag v0.6.0**

```bash
git push github.com-personal HEAD:master
git tag v0.6.0 -m "Plan 6 complete: portal status filtering and smoke-test CLI"
git push github.com-personal v0.6.0
```

Expected: tag `v0.6.0` on `git@github.com-personal:St4r4x/career-ops-fr.git`.

---

## How to smoke-test a portal manually (for Arnaud)

After this plan is complete, to validate that WTTJ returns real results:

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/python scripts/scan_portals.py --portal wtfj \
  --keywords "AI Engineer" --location "Paris" --max-pages 1
```

If 0 results are returned, open the browser DevTools on the WTTJ search page and check that the selector `li[data-testid='search-results-list-item-wrapper']` still matches. Update `portals/fr/wtfj.yaml` if needed.

Same for APEC and Indeed with their respective portal IDs.
