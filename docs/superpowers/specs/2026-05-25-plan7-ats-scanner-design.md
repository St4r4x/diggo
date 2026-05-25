# Plan 7 — ATS Scanner + Pipeline Fixes Design Spec

**Date:** 2026-05-25
**Status:** Approved

---

## Goal

Three parallel improvements:
1. Fix broken portal selectors (apec, wtfj return 0 results)
2. Add French keywords to settings.yaml so scoring actually matches French job titles
3. Add an ATS scanner that queries Greenhouse / Lever / Ashby public JSON APIs for the ~40 target companies

---

## 1. Fix Portal Selectors

`portals/fr/apec.yaml` and `portals/fr/wtfj.yaml` return 0 cards. The CSS selectors are stale.

**Fix approach:** use Playwright to navigate to each portal's search result page and inspect the real DOM, then update the YAML selectors. No code changes — YAML-only fix.

Files to update:
- `portals/fr/apec.yaml` — update `selectors.*`
- `portals/fr/wtfj.yaml` — update `selectors.*`

---

## 2. Bilingual Keywords

`config/settings.yaml` currently lists English-only keywords. Indeed.fr returns French titles ("Ingénieur Machine Learning", "Ingénieur IA") that never match.

**Fix:** add French equivalents to `search.keywords`. The pre_filter scorer already does substring matching (case-insensitive), so adding "Ingénieur" or "Machine Learning" covers most French titles.

Updated keyword list:
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
```

---

## 3. ATS Scanner

### Architecture

**No Playwright** — Greenhouse, Lever, and Ashby expose unauthenticated public JSON APIs. Pure `httpx` async HTTP.

```
config/ats_map.yaml          # company → careers_url mapping
scripts/scan_ats.py          # async scanner, returns list[RawOffer]
tests/test_scan_ats.py       # unit tests (providers + integration with httpx mock)
```

`import_offers.py` calls both `run_scan()` (portals) and `scan_ats()` (ATS) then merges before dedup.

### Provider auto-detection

Provider is resolved from `careers_url` pattern — no explicit `provider:` field needed:

| URL pattern | Provider | API endpoint |
|---|---|---|
| `greenhouse.io` | greenhouse | `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs` |
| `jobs.lever.co` | lever | `https://api.lever.co/v0/postings/{slug}` |
| `jobs.ashbyhq.com` | ashby | `https://api.ashbyhq.com/posting-api/job-board/{slug}` |
| anything else | unknown | skipped with WARNING |

### `scan_ats.py` public interface

```python
async def scan_ats(
    ats_map_path: Path = _DEFAULT_ATS_MAP,
    *,
    company_filter: str | None = None,
    keywords: list[str] | None = None,
) -> list[RawOffer]
```

- `company_filter`: if set, only scan that company (for smoke-testing)
- `keywords`: if set, client-side filter on title (case-insensitive substring match on any keyword)
- Returns `list[RawOffer]` with `portal` field set to the provider name (`"greenhouse"`, `"lever"`, `"ashby"`)

CLI:
```bash
python scripts/scan_ats.py --company "Mistral AI"
python scripts/scan_ats.py --keywords "AI Engineer" "Machine Learning"
```

### `config/ats_map.yaml`

One entry per company. The `careers_url` is the direct ATS URL (not the company's own careers landing page).

```yaml
# Greenhouse
- name: "Mistral AI"
  careers_url: "https://job-boards.greenhouse.io/mistralai"
- name: "Dataiku"
  careers_url: "https://job-boards.greenhouse.io/dataiku"
- name: "Artefact"
  careers_url: "https://job-boards.greenhouse.io/artefact"

# Lever
- name: "Doctrine"
  careers_url: "https://jobs.lever.co/doctrine"
- name: "ContentSquare"
  careers_url: "https://jobs.lever.co/contentsquare"
- name: "Ekimetrics"
  careers_url: "https://jobs.lever.co/ekimetrics"

# Ashby
- name: "Nabla"
  careers_url: "https://jobs.ashbyhq.com/nabla"
- name: "Alan"
  careers_url: "https://jobs.ashbyhq.com/alan"
- name: "Owkin"
  careers_url: "https://jobs.ashbyhq.com/owkin"

# Unknown / to be investigated later
# Hugging Face uses Workable (apply.workable.com/huggingface) — no public API, skip for now
# Big tech (Google, Meta, Microsoft, Amazon) use Workday — Plan 8
# Qonto, Doctolib, BlaBlaCar, Ledger, Algolia — ATS to confirm manually
```

**Note:** companies marked `unknown` or not in the map are silently skipped. Adding a new company = add one line to `ats_map.yaml`, no code change.

### RawOffer field mapping

| ATS field | RawOffer field | Notes |
|---|---|---|
| `title` | `title` | direct |
| `company name from map` | `company` | from ats_map entry |
| `absolute_url` / `hostedUrl` / `jobUrl` | `url` | provider-specific |
| `location` | `location` | provider-specific extraction |
| provider name | `portal` | `"greenhouse"`, `"lever"`, `"ashby"` |
| `None` | `date_posted` | ATS APIs don't always expose it |
| `0.0` | `score` | scored later by pre_filter |

### Integration in import_offers.py

Current `_run_pipeline`:
```python
raw = await run_scan(portal_ids, keywords=keywords, location=location)
```

Updated:
```python
portal_raw = await run_scan(portal_ids, keywords=keywords, location=location)
ats_raw = await scan_ats(keywords=keyword_list)
raw = portal_raw + ats_raw
```

### Error handling

- HTTP error on one company → log WARNING, continue with others
- Unknown provider → log WARNING, skip
- Timeout (default 10s per company) → log WARNING, skip
- `ats_map.yaml` missing → raise FileNotFoundError (fail fast)

### Testing

`tests/test_scan_ats.py` uses `pytest-httpx` to mock HTTP responses:
- `TestGreenhouseProvider`: valid response, empty jobs array, HTTP 404
- `TestLeverProvider`: valid response, empty array, HTTP 500
- `TestAshbyProvider`: valid response, empty jobs
- `TestResolveProvider`: greenhouse/lever/ashby/unknown URL detection
- `TestScanAts`: company_filter, keyword filtering, merges providers correctly

---

## 4. Out of Scope (Plan 8)

- Workday (Google, Meta, Amazon, Microsoft, Apple, Criteo) — React-heavy, requires Playwright or dedicated API
- SmartRecruiters (Sopra Steria, Thales, Capgemini, OCTO, OnePoint) — no public JSON API
- Companies confirmed on LinkedIn only — already scraped via `linkedin` portal (currently `needs_auth`)
