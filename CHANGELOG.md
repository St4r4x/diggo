# Changelog

All notable changes to career-ops-fr are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## 2026-05-28

### Changed
- `scripts/backfill_descriptions.py` — replaced Playwright with HTTP for APEC and Ashby
  - `ApecApiExtractor`: calls internal REST webservice (`cms/webservices/offre/public`) discovered via network interception; no browser
  - `AshbyJsonLdExtractor`: fetches static HTML and parses the embedded JSON-LD `JobPosting` block; no browser
  - Playwright now only launched when Indeed URLs are present (~2% of offers)

### Changed
- `scripts/backfill_descriptions.py` — replaced Playwright with public REST APIs for Lever and Greenhouse
  - `LeverApiExtractor`: uses `api.lever.co/v0/postings/{company}/{uuid}`, prefers `descriptionPlain`
  - `GreenhouseApiExtractor`: uses `boards-api.greenhouse.io/v1/boards/{company}/jobs/{id}`, HTML → text via `_html_to_text` (with `html.unescape` pre-pass for doubly-encoded entities)
  - Browser lazy-initialized only when at least one URL requires it

### Changed
- `dashboard/templates/base.html` — renamed nav link "Pipeline" → "Candidatures"

### Removed
- 15 unrecoverable offers deleted from DB:
  - 8 × Indeed `pagead/clk` tracking URLs (one-shot redirects, irrecoverable)
  - 7 × APEC expired offers (returned empty from scraper)

---

## 2026-05-27

### Added
- `dashboard/profile_parser.py` — `load_profile()` / `save_profile()` to read/write `config/profile.md` + `config/contact.yaml`
- `dashboard/templates/profile.html` — full profile page with accordion sections
- `dashboard/templates/partials/profile_contact.html` — contact section (7 fields, HTMX POST)
- `dashboard/templates/partials/profile_summary.html` — summary textarea, HTMX POST
- `dashboard/templates/partials/profile_experience.html` — experience cards with add/remove, HTMX POST
- `dashboard/templates/partials/profile_skills.html` — skill tags by category with add/remove, HTMX POST
- `dashboard/templates/partials/profile_education.html` — education cards + certifications textarea, HTMX POST
- `dashboard/templates/partials/profile_projects.html` — project cards with add/remove, HTMX POST
- `tests/test_profile_parser.py` — 8 parser unit tests including roundtrip
- `tests/test_profile_routes.py` — route tests covering all 6 POST endpoints (invalid JSON, persistence, error handling)
- `scripts/backfill_descriptions.py` — initial Playwright-based backfill script (APEC + Lever); later replaced with HTTP-first architecture

### Changed
- `dashboard/app.py` — added GET `/profile` + 6 POST routes (`/profile/contact`, `/profile/summary`, `/profile/experience`, `/profile/skills`, `/profile/education`, `/profile/projects`)
- `dashboard/templates/base.html` — added "Profil" nav link with active state

### Fixed
- `dashboard/app.py` — moved `import json` and `import profile_parser` to module level (were inside function bodies)
- `dashboard/app.py` — education route catches `AttributeError` in addition to `json.JSONDecodeError`
- `dashboard/profile_parser.py` — strengthened `_split_sections` guard; module-level `_PROFILE_MD` / `_CONTACT_YAML` constants for test monkeypatching

---

## 2026-05-XX — Prior work (condensed)

### Added
- Portal scraping: APEC, Indeed, WTTJ, LinkedIn, Glassdoor via Playwright + YAML portal configs
- ATS scraping: Greenhouse, Lever, Ashby direct integrations (`scan_ats.py`)
- Description enrichment from detail pages after pagination (`scan_portals.py`)
- Deduplication with accent-insensitive normalization (`dedup.py`)
- Keyword pre-filtering with scoring threshold (`pre_filter.py`)
- Full pipeline: scan → dedup → filter → score → import to SQLite (`import_offers.py`)
- Daily report markdown digest (`daily_report.py`)
- FastAPI + HTMX dashboard with Kanban application tracker (`dashboard/`)
- SQLite persistence layer (`dashboard/db.py`)
- Stats page (`/stats`)
- CV PDF generation via WeasyPrint + Jinja2 (`scripts/generate_pdf.py`)
- Cover letter PDF generation with context JSON support (`scripts/generate_cover_letter.py`)
- Interview prep sheet PDF generation (`scripts/generate_prep_sheet.py`)
- Claude Code modes: `score-offer`, `generate-cv`, `generate-cover-letter`, `prepare-candidature`
- Docker Compose setup with dashboard service and pipeline profile
- Full pytest suite (197 tests)
