# Changelog

All notable changes to career-ops-fr are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

## 2026-06-04

### Changed
- `dashboard/templates/` — full UI redesign: deep-purple gradient background (`#0f0a1e`→`#1a0f30`), Indigo+Rose accent palette (`#6366f1`/`#8b5cf6`/`#ec4899`), rounded-lg cards with surface/raised/border color system (`#1e1535`/`#2d1f5e`); no logic changes
- `dashboard/templates/base.html` — new nav style (gradient logo text, indigo active link), shared `.grade-a/b/c/d/f` badge classes, `.bg-accent` / `.bg-accent-rose` gradient utilities
- `dashboard/templates/index.html` — left panel dark surface, filter inputs and selects dark-styled with indigo focus rings
- `dashboard/templates/partials/offer_list.html` — avatar initials per company (`bg-accent` gradient circle), gradient grade badges via `.grade-*` classes, hover highlight `#251b45`
- `dashboard/templates/partials/offer_detail.html` — large avatar header, indigo→transparent gradient divider, indigo metadata labels, styled action buttons (Préparer candidature uses `bg-accent`)
- `dashboard/templates/partials/offer_notes.html` — dark surface textarea, indigo focus border via `onfocus`/`onblur`
- `dashboard/templates/partials/offer_form.html` — dark inputs/select/textarea with indigo focus, gradient save button
- `dashboard/templates/partials/offer_empty.html` — centered empty state with `bg-accent-rose` placeholder
- `dashboard/templates/partials/scan_status.html` — idle button uses `bg-accent`, running state shows indigo spinner, done/error states themed
- `dashboard/templates/stats.html` — KPI cards with 3px colored top-border gradients, indigo→rose progress bars
- `dashboard/templates/profile.html` — accordion and form elements updated to match new theme (indigo open-state gradient, gradient save buttons, `#6366f1` input focus)

---

## [0.9.0] — 2026-06-03

First public release.

## 2026-06-03

### Added
- `config/cv.yaml` (gitignored) — CV content file (FR + EN): experience, skills, education, hobbies; replaces hardcoded data in `generate_pdf.py`
- `config/cv.yaml.example` — template for new contributors

### Changed
- `scripts/generate_pdf.py` — `default_context(lang)` now loads from `config/cv.yaml` via `_load_cv()`; `default_context_en()` kept as backwards-compatible shim; all hardcoded personal content removed from source
- `.gitignore` — added `config/cv.yaml`
- `README.md` — full rewrite for new users: pipeline diagram, 5-step setup, scoring signal table, prepare-candidature phases, config table with gitignored flags

## 2026-06-02

### Added
- `scripts/generate_pdf.py` -- `--lang en` flag: generates an English CV using a new `default_context_en()` function with fully translated content (experience bullets, job types, education labels, languages); output filename suffixed `-en.pdf`
- `templates/cv-en/cv.html.j2` -- English CV template (section labels: Profile, Experience, Skills, Education, Languages)
- `templates/cv-en/cv.css` -- copy of fr CSS for the English template

### Added
- `scripts/generate_pdf.py` -- `hobbies` field in `build_cv_context()` and both `default_context()` / `default_context_en()` (Sport — tennis, padel · Video games · Cinema · Travel)
- `templates/cv-fr/cv.html.j2` -- "Centres d'intérêt" section rendered when `hobbies` is non-empty
- `templates/cv-en/cv.html.j2` -- "Interests" section rendered when `hobbies` is non-empty

### Fixed
- `templates/cover-letter-fr/cover-letter.html.j2` -- subject line and closing line were hardcoded in French; both now accept optional `subject` / `closing_line` template variables with French fallback, enabling fully English cover letters
- `scripts/generate_cover_letter.py` -- forward `subject` and `closing_line` keys from `--context-file` JSON into the template context

### Changed
- `scripts/generate_pdf.py` -- `TEMPLATE_DIR` split into `TEMPLATE_DIR_FR` / `TEMPLATE_DIR_EN`; `render_html()` and `generate_pdf()` accept a `lang` parameter to select the correct template directory

## 2026-05-29 (later)

### Fixed
- `scripts/pre_filter.py` — `_EXP_RE`: now covers `Minimum X ans` (WTTJ structured field, 118 occurrences), `années d'expérience`, and `X years of experience` (EN offers); was previously missing ~85% of experience mentions
- `scripts/pre_filter.py` — `_SALARY_RE`: added `keuro` variant ("50 à 60 keuro")
- `scripts/pre_filter.py` — `_RTT_RE`: now detects RTT presence without a leading number ("RTT pour tous les CDI"); was silently skipping ~50% of RTT mentions
- `scripts/pre_filter.py` — `_TR_RE`: added `swile` (meal voucher platform, 3 occurrences)
- `scripts/pre_filter.py` — `_score_salary()` and `score_offer()`: adapted for new regex group structure

### Changed
- `dashboard/data/applications.db` — rescored with improved regex coverage (45 offers updated; B: 21→26, C: 49→60)

## 2026-05-29

### Added
- `scripts/liveness.py` — `check_liveness(url)` HTTP-first job URL liveness checker; returns `(status, reason)` with statuses `active | expired | uncertain`; detects expiry via HTTP 404/410, URL path patterns, and French/English body patterns; zero browser, zero LLM
- `tests/test_liveness.py` — 7 tests covering 404, 410, FR/EN body patterns, clean 200, network error, empty URL
- `scripts/generate_pdf.py` — `_normalize_for_ats()`: replaces typographic characters that break ATS parsers (em-dashes, smart quotes, zero-width spaces) while preserving `<style>`/`<script>` blocks
- `tests/test_generate_pdf.py` — `TestNormalizeForAts` (6 tests)
- `scripts/pre_filter.py` — `_score_legitimacy()`: penalties for thin desc (<300 chars, -0.5), no tech skills (-0.3), no salary (-0.2); capped at -0.5; `legitimacy:suspicious` tag if penalty ≥ 0.3
- `tests/test_pre_filter.py` — `TestLegitimacy` (4 tests), `TestSalaryNormalized` (5 tests)

### Changed
- `scripts/pre_filter.py` — replaced flat salary signal (+0.3) with `_score_salary()`: reconstructs French annual package (13e mois, RTT, titre-restaurant, intéressement); +0.5 if in range, -0.3 if out of range, 0.0 if absent; added `_MONTHS_13_RE`, `_RTT_RE`, `_TR_RE`, `_INTERESSEMENT_RE`
- `scripts/generate_cover_letter.py` — `_normalize_for_ats()` applied before WeasyPrint render
- `scripts/generate_prep_sheet.py` — `_normalize_for_ats()` applied before WeasyPrint render
- `scripts/import_offers.py` — added `import_offers_with_liveness()` returning `(inserted, skipped, expired)` and `--check-liveness` CLI flag
- `tests/test_import_offers.py` — `TestLivenessIntegration` (2 tests)
- `dashboard/data/applications.db` — rescored with updated salary + legitimacy signals

## 2026-05-28

### Added
- `scripts/rescore.py` — migration script to rescore all existing DB offers with updated signals; supports `--dry-run` and `--db PATH` flags
- `scripts/pre_filter.py` — 5 new scoring signals: tech skills in description (+0.1/skill, cap +1.0), experience ≤ threshold (+0.5), CDI mention (+0.3), salary in target range (+0.3), ATS quality portal bonus (+0.3); `_normalize_company()` strips noisy suffixes before company matching
- `tests/test_rescore.py` — 8 tests: `TestInferPortal` (4) and `TestRescore` (dry-run, update, idempotency, summary)
- `tests/test_pre_filter.py` — `TestNewSignals` class with 11 tests for all new signals
- `dashboard/templates/partials/scan_status.html` — HTMX partial for scan button/badge (idle, running, done, error states)
- `dashboard/app.py` — `POST /scan/start` and `GET /scan/status` endpoints: trigger full import pipeline as asyncio Task with live HTMX polling feedback
- `tests/test_dashboard_app.py` — `TestScan` (6 tests) and `TestPrepareCandidature` (1 test)

### Changed
- `scripts/backfill_descriptions.py` — replaced Playwright with HTTP for APEC and Ashby
  - `ApecApiExtractor`: calls internal REST webservice (`cms/webservices/offre/public`) discovered via network interception; no browser
  - `AshbyJsonLdExtractor`: fetches static HTML and parses the embedded JSON-LD `JobPosting` block; no browser
  - Playwright now only launched when Indeed URLs are present (~2% of offers)
- `scripts/backfill_descriptions.py` — replaced Playwright with public REST APIs for Lever and Greenhouse
  - `LeverApiExtractor`: uses `api.lever.co/v0/postings/{company}/{uuid}`, prefers `descriptionPlain`
  - `GreenhouseApiExtractor`: uses `boards-api.greenhouse.io/v1/boards/{company}/jobs/{id}`, HTML → text via `_html_to_text` (with `html.unescape` pre-pass for doubly-encoded entities)
  - Browser lazy-initialized only when at least one URL requires it
- `dashboard/templates/base.html` — renamed nav link "Pipeline" → "Candidatures"
- `dashboard/app.py` — `GET /` passes `status` and `result` to template for initial scan button render; lifespan initializes `scan_status`/`scan_result` on `app.state`
- `dashboard/templates/index.html` — scan button added to filter bar via `scan_status.html` include
- `scripts/import_offers.py` — `score_to_grade()` thresholds recalibrated: A≥4.0, B≥3.0, C≥2.0, D≥1.0, F<1.0
- `tests/test_dashboard_app.py` — `client` fixture initializes `scan_status`/`scan_result` to avoid lifespan bypass issues

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
