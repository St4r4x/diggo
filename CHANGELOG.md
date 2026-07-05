# Changelog

All notable changes to career-ops-fr are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- `dashboard/user_data.py` — `get_cv()`, `save_cv_meta()`, `save_experience()`, `save_skills()`, `save_certifications()`, `save_education()` for CV data access with per-user/per-lang isolation and `cv.yaml` file migration
- `dashboard/user_data.py` — `_migrate_cv_from_files()` helper reads `config/cv.yaml` and seeds DB on first access
- `tests/test_user_data.py` — 7 tests covering CV (empty state, meta save/get, experience with bullets, replace existing, skills, certifications, education)
- `dashboard/user_data.py` — `get_ats_targets()`, `add_ats_target()`, `delete_ats_target()` functions for ATS target CRUD with per-user isolation and `ats_map.yaml` file migration
- `tests/test_user_data.py` — 5 tests covering ATS targets (empty list, add/get, delete, wrong user, per-user isolation)

## 2026-07-05

### Changed
- `README.md` — add v0.2 badge, "Run the app" quick-launch section at top (supabase start → docker compose up → stop sequence); full rewrite: Supabase CLI setup, auth section (routes, Inbucket, DEV_AUTO_LOGIN), updated env vars table, Docker note about host.docker.internal, updated project structure (auth.py, supabase/, PostgreSQL db.py)

### Fixed
- `dashboard/app.py` / `docker-compose.yml` — split `SUPABASE_URL` (container→Supabase for JWKS) from `SUPABASE_PUBLIC_URL` (browser→Supabase for auth JS); fixes "Failed to fetch" on login/signup when running in Docker

### Changed
- `dashboard/auth.py` — cache JWKS client with `_jwks_unavailable` flag to skip repeated failed fetches; collapse redundant `ExpiredSignatureError` branch into `InvalidTokenError`; replace per-call `os.getenv("DEV_AUTO_LOGIN")` with module-level constant
- `dashboard/app.py` — move `supabase_url`/`supabase_anon_key` to `templates.env.globals`; drop per-route context injection
- `tests/test_auth.py` — fix `test_get_current_user_expired_token` and `test_get_current_user_wrong_secret` to use cookie requests; remove duplicate `test_get_current_user_valid_cookie`

### Fixed
- `dashboard/auth.py` — switched JWT validation to JWKS (ES256) via `PyJWKClient`; Supabase CLI recent versions sign tokens with ES256 not HS256; HS256 fallback kept for tests
- `dashboard/auth.py` — removed `_ALGORITHM`/`_AUDIENCE` module constants; validation now dynamic via `_decode_token()`
- `requirements.txt` — added `cryptography==42.0.8` (required by PyJWT for ES256 support)
- `docker-compose.yml` — override `SUPABASE_URL` to `http://host.docker.internal:54321` so the container can reach the JWKS endpoint on the host
- `docker-compose.yml` — mount `dashboard/templates` as a volume so template changes don't require a full image rebuild
- `dashboard/templates/auth/login.html` — added defensive init guard, loading state, and precise error messages
- `dashboard/templates/auth/signup.html` — added defensive init guard, loading state, precise error messages, and `name`/`autocomplete` attributes on inputs

### Fixed
- `dashboard/auth.py` — `set_auth_cookies` now reads `COOKIE_SECURE` env var and sets `secure=True` on both cookies when enabled; defaults to `false` for local HTTP dev
- `dashboard/auth.py` — extracted `validate_access_token()` helper that decodes and validates a Supabase JWT; raises 401 on invalid token
- `dashboard/app.py` — `POST /auth/session` now calls `validate_access_token` before setting cookies, preventing session fixation via arbitrary token injection
- `supabase/config.toml` — `site_url` corrected to `http://localhost:8000`; added `http://localhost:8000` and `http://127.0.0.1:8000` to `additional_redirect_urls` so password-reset redirects work in local dev
- `.env.example` — added `COOKIE_SECURE` variable (default `false`)
- `tests/test_dashboard_app.py` — `test_session_post_sets_cookies` now mints a valid JWT instead of sending a dummy string

### Added
- `dashboard/user_data.py` — profile and settings module with `get_profile()`, `save_profile()`, `get_settings()`, `save_settings()` functions; file-based auto-migration fallback reads from `config/contact.yaml`, `config/profile.md`, `config/settings.yaml`
- `tests/test_user_data.py` — test suite for profile and settings (5 tests: empty defaults, save/get roundtrip, per-user isolation, array handling)
- `dashboard/templates/base.html` — user email and logout button in nav; `DELETE /auth/session` then redirect to `/login`
- `dashboard/app.py` — pass `current_user` to index, stats, and profile template contexts so nav can display the email

---

### Added
- `dashboard/templates/auth/login.html` — full styled login page: email/password form, Supabase signInWithPassword, POST /auth/session on success, password-reset link trigger
- `dashboard/templates/auth/signup.html` — full styled signup page: email/password/confirm form, Supabase signUp, redirects to /auth/confirm
- `dashboard/templates/auth/confirm.html` — static "check your email" page with Inbucket link for local dev
- `dashboard/templates/auth/reset-password.html` — new password form using Supabase updateUser after PASSWORD_RECOVERY event

### Changed
- `dashboard/app.py` — auth routes now pass `supabase_url` and `supabase_anon_key` context vars to login/signup/reset-password templates; added `_SUPABASE_URL` / `_SUPABASE_ANON_KEY` module-level constants from env

---

### Added (Task 3)
- `dashboard/app.py` — public routes `/login`, `/signup`, `/auth/confirm`, `/auth/reset-password` (no auth dependency)
- `dashboard/app.py` — `POST /auth/session`: accepts `access_token`/`refresh_token` JSON body, sets httpOnly cookies, returns `{"ok": true}`
- `dashboard/app.py` — `DELETE /auth/session`: clears auth cookies, redirects 302 to `/login`
- `dashboard/templates/auth/` — placeholder templates for login, signup, confirm, reset-password (full UI in Task 4)
- `tests/test_dashboard_app.py` — `TestAuthRoutes`: 3 tests covering login page 200, session cookie set, session cookie clear

### Changed
- `dashboard/auth.py` — switched from `Authorization: Bearer` header to httpOnly `session` cookie; auth failures now redirect 302 to `/login` instead of returning 401; added `set_auth_cookies` and `clear_auth_cookies` helpers
- `tests/test_auth.py` — updated 3 existing tests to expect 302 redirect; added `_request_with_cookie` helper and 3 new cookie-based tests
- `tests/test_dashboard_app.py` — `test_requires_auth` now uses `follow_redirects=False` and asserts `status_code == 302`

### Fixed
- `dashboard/auth.py` — `SUPABASE_JWT_SECRET` now read lazily inside `get_current_user` instead of at module load time; prevents silent bypass (empty-string secret) when `.env` is loaded after import; raises 500 if secret is unconfigured

### Added
- `dashboard/auth.py` — Supabase JWT verification dependency (`get_current_user`); raises 401 on missing/expired/invalid token
- `tests/test_auth.py` — 4 tests covering valid token, missing token, expired token, wrong secret
- `dashboard/db.py` — rewritten for PostgreSQL (psycopg2); all methods now accept `user_id: str` and scope queries to that user; `open_db(url)` replaces `open_db(path)`; `_migrate()` removed (Alembic handles schema)
- `tests/test_dashboard_db.py` — migrated from SQLite in-memory to PostgreSQL temp table fixture; added user isolation tests
- `alembic/` — Alembic migration setup; `alembic upgrade head` creates the `applications` table with `user_id VARCHAR(36) NOT NULL` and composite index on `(user_id, status)`
- `alembic/versions/0001_initial_schema.py` — initial migration: full `applications` schema matching the existing SQLite columns plus `user_id`
- `dashboard/env.py` — `load_env()` helper using python-dotenv; loads `.env` in dev, no-op in prod
- `.env.example` — template for all required env vars (DATABASE_URL, Supabase, Groq)
- `tests/test_env.py` — test for env var loading from a temp file
- `config/settings.yaml.example` — template for search keywords, location, salary range, target companies
- `config/ats_map.yaml.example` — template for direct ATS URLs (Greenhouse/Lever/Ashby)
- `docs/todo-deployment.md` — SaaS deployment roadmap (auth, multi-tenancy, LLM migration, security)

### Changed
- `docker-compose.yml` — override `DATABASE_URL` to `postgres:5432` in dashboard and pipeline services (env_file uses localhost, which is wrong inside Docker)
- `scripts/import_offers.py` — replace sqlite3 with psycopg2; `import_offers`, `import_offers_with_liveness`, and `expire_stale_offers` now accept `user_id: str` instead of `db_path: Path`; CLI requires `--user-id UUID`; `_DATABASE_URL` read from env
- `tests/test_import_offers.py` — migrated to PostgreSQL temp table fixture; `mock_pg_connect` fixture redirects `psycopg2.connect` to the test connection; added user-scoping test
- `dashboard/app.py` — rewritten to use PostgreSQL via `open_db(DATABASE_URL)`; every route now has `Depends(get_current_user)` and passes `user_id` to all DB calls; `_run_scan_task` and `_start_scan` accept explicit `user_id`
- `tests/test_dashboard_app.py` — migrated from SQLite in-memory to PostgreSQL temp table fixture; auth dependency mocked via `dependency_overrides[get_current_user]`; all DB calls updated with `user_id`
- `tests/test_profile_routes.py` — fixture migrated from SQLite to PostgreSQL temp table; auth dependency mocked
- `docker-compose.yml` — add postgres:16 service with healthcheck; dashboard/pipeline now depend on it; remove SQLite data volume
- `scripts/import_offers.py` — call load_dotenv() at startup so CLI usage picks up .env
- `tests/test_env.py` — fix stdlib import order (os → pathlib → sys) and add type hints to test signature
- `.gitignore` — untrack personal config files: `config/settings.yaml`, `config/ats_map.yaml`, `config/cover-letter-*.json`
- `README.md` — add `settings.yaml` and `ats_map.yaml` to quick start setup steps

## [0.10.0] — 2026-07-03

### Added
- `dashboard/db.py` — `DB.get_followups()`: returns applications in "Envoyée" or "Entretien RH" with `send_date` older than 7 days
- `dashboard/app.py`, `dashboard/templates/index.html` — amber bandeau when applications are overdue for follow-up
- `dashboard/templates/partials/offer_list.html` — red dot indicator on overdue offer rows
- `dashboard/app.py` — `_build_funnel()`: computes funnel steps and conversion rates from `by_status`
- `dashboard/templates/stats.html` — funnel section with horizontal bars, conversion rates, and exits (Refusée, Abandonnée)
- `dashboard/templates/stats.html` — daily report widget: reads latest `reports/daily-*.md` and renders as HTML
- `requirements.txt` — `mistune==3.0.2`

### Fixed
- `dashboard/db.py` — `get_stats()` stale_count threshold corrected to `>=` to match `get_followups()` cutoff

## 2026-07-01

### Changed
- `scripts/scan_portals.py` — `run_scan()` now launches a single shared Chromium browser for all portals instead of one per portal; `scrape_portal()` receives the browser as a parameter and creates its own context
- `scripts/scan_portals.py` — navigation changed from `wait_until="networkidle"` to `"domcontentloaded"` (faster page loads); `next_button`/`scroll` pagination waits reduced from `networkidle` to `load`
- `scripts/scan_portals.py` — description fetch semaphore raised from 5 to 15 concurrent slots; `skip_descriptions` parameter added to `scrape_portal()` and `run_scan()`
- `scripts/scan_ats.py` — Greenhouse and Lever detail fetches are now parallelised with `asyncio.gather` instead of sequential per-company loops
- `scripts/import_offers.py` — `portal_queries` now run in parallel with `asyncio.gather` instead of sequentially; `_run_pipeline()` accepts `skip_descriptions` parameter
- `dashboard/app.py` — added `/scan/start-quick` route (skip_descriptions=True); extracted `_start_scan()` helper to avoid duplication
- `dashboard/templates/partials/scan_status.html` — added "⚡ Rapide" button triggering `/scan/start-quick`

## 2026-06-19

### Added
- `config/cv.yaml.example` — new `skill_categories` dict field (replaces `skills`), `certifications` list field, and `stack` list per experience entry
- `templates/cv-fr/cv.html.j2`, `templates/cv-en/cv.html.j2` — categorised skills grid, optional Certifications section (after Skills), per-role stack tag row
- `templates/cv-fr/cv.css`, `templates/cv-en/cv.css` — `.skill-category`, `.skill-category-label`, `.cert-line`, `.cert-name`, `.cert-meta`, `.stack-tags`, `.stack-tag` classes

### Changed
- `scripts/generate_pdf.py` — `build_cv_context()` now accepts `skill_categories: dict[str, list[str]]` (replacing `skills: list[str]`) and optional `certifications: list[dict] | None`; context dict keys now include `skill_categories` and `certifications`
- `scripts/generate_pdf.py` — `default_context()` reads `skill_categories` and `certifications` from cv.yaml config
- `tests/test_generate_pdf.py` — updated all tests to use `skill_categories` instead of `skills`; added 2 new tests for certifications handling (default None, and when present)

## 2026-06-15 (3)

### Added
- `dashboard/db.py` — `_parse_salary_min()` helper: extracts lower bound in k€ from APEC salary strings ("40 - 55 k€" → 40, "A partir de 45 k€" → 45, unparseable → None); `get_all()` filters by `sal_min` threshold in Python post-fetch; "A négocier" and missing salaries are excluded when a threshold is set
- `dashboard/app.py` — `/offers` route accepts `sal_min` query param
- `dashboard/templates/index.html` — salary filter select (≥ 40/50/60/70/80k€), all existing `hx-include` updated to carry `sal_min`

## 2026-06-15 (2)

### Changed
- `scripts/backfill_descriptions.py` — `ApecApiExtractor` now builds `ParsedDescription` directly from APEC API structured fields: `competences[]` (SAVOIR_FAIRE type) → `stack`, `salaireTexte` → `salaire`, `texteHtmlEntreprise` → `avantages`; returns pre-built JSON bypassing text re-parsing; `_save_parsed()` detects pre-built JSON and stores it directly; backfill query adds `portal='apec' AND stack=''` condition to re-enrich already-parsed APEC rows
- Result: 196/372 APEC rows now have structured `stack` (techs from API competences), 372/431 total rows have `salaire`; 176 APEC rows without stack are expired offers (API 404, re-parsed from stored text only)

## 2026-06-15

### Fixed
- `scripts/description_parser.py` — dispatcher now auto-detects HTML (`<h[234]>` scan) and APEC blobs (`"Descriptif du poste"` marker) regardless of `portal` value; falls back to `_parse_heuristic` instead of dead-end `_parse_generic`; `_parse_html_headings` fallback also runs `_parse_heuristic` on extracted plain text when no headings found; heading and section regexes expanded with English patterns from Lever/Greenhouse jobs (Mistral, Dataiku, Artefact)
- `scripts/scan_ats.py` — Greenhouse provider applies `unescape()` on doubly-encoded HTML entities; Lever provider prefers `descriptionPlain` (Lever uses `<strong style>` not `<h2>/<h3>`, so plain text feeds `_parse_heuristic` more effectively); Ashby provider prefers `descriptionBody` over `descriptionPlain`
- `scripts/backfill_descriptions.py` — `GreenhouseApiExtractor` applies `unescape()`, `LeverApiExtractor` reverted to prefer plain text; APEC extractor emits structured text with `"Descriptif du poste"` / `"Profil recherché"` markers instead of one flat blob; backfill query re-processes rows where all non-`mission` fields are empty; portal inferred and persisted for legacy rows; rows with existing plain-text description are re-parsed directly without a network call (handles expired APEC offers that return 404)
- `scripts/import_offers.py` — `infer_portal_from_url()` fills empty `portal` column at insert time using URL hostname

### Fixed
- `scripts/dedup.py` — added `normalize_offer_url()`: strips query params for APEC URLs (offer ID is in path, `page=` / `selectedIndex=` are search context and caused duplicate inserts across scans); detection uses both portal field and URL hostname so legacy rows with empty portal are covered
- `scripts/import_offers.py` — `existing_urls()` and both import loops now use `normalize_offer_url()` so APEC offers with different query strings are correctly recognised as duplicates

### Changed
- DB cleanup: removed 477 duplicate entries (455 + 22 earlier) from `applications` (886 → 431); protected rows with status Envoyée/Refusée were untouched

### Added
- `scripts/description_parser.py` — new module with public `parse_description(raw, portal) -> ParsedDescription`; dispatches to portal-specific heuristic parsers: APEC (French section-marker regex), Lever/Greenhouse/Ashby (HTML `<h2>`–`<h4>` headings), Indeed/WTTJ/LinkedIn/Glassdoor (keyword-line heuristics), generic fallback (everything → mission)
- `scripts/models.py` — `ParsedDescription` dataclass with 6 fields: `mission`, `profil`, `stack`, `avantages`, `contrat`, `salaire`; added `parsed_description: ParsedDescription | None = None` to `RawOffer`
- `dashboard/db.py` — `_migrate()`: adds `portal TEXT NOT NULL DEFAULT ''` column to `applications` table idempotently; `_SELECT` and `DB.update()` updated to include `portal`
- `tests/test_description_parser.py` — 19 tests covering all portals and both paths (parsed + raw fallback)
- `tests/test_dashboard_db.py` — `test_portal_column_created_by_migration`

### Changed
- `scripts/import_offers.py` — `insert_offer()` now calls `parse_description()` and writes a JSON-serialised `ParsedDescription` to the `description` column; `portal` column populated on every insert; skip-path UPDATE also serialises to JSON
- `scripts/pre_filter.py` — `score_offer()` uses new `_desc_blob(offer)` helper: concatenates all 6 `ParsedDescription` fields when available, falls back to raw `offer.description` for legacy rows
- `scripts/backfill_descriptions.py` — after extracting raw HTML text, calls `parse_description(desc, portal)` and saves JSON instead of plain text; DB query now reads `portal` column via `COALESCE(portal, '')`
- `dashboard/app.py` — added `_parse_description(raw) -> dict | str` helper; all 3 routes returning `offer_detail.html` inject `parsed_desc` into the template context
- `dashboard/templates/partials/offer_detail.html` — description block renders 6 labelled sections (Missions, Profil recherché, Stack technique, Avantages, Contrat, Salaire) when `parsed_desc` is a mapping; falls back to plain-text display for legacy rows

## 2026-06-11 (2)

### Added
- `scripts/pre_filter.py` — `_is_location_compatible(location, target)`: generic location gate; passes if location is empty, remote/hybrid/télétravail, or `target` appears anywhere in the offer location string (case-insensitive); works for any city configured in `search.location`
- `scripts/pre_filter.py` — `pre_filter()` now hard-rejects offers whose location doesn't match `search.location` before scoring
- `tests/test_pre_filter.py` — `TestIsLocationCompatible` (13 cases) and `TestPreFilterLocationGate` (5 cases)

## 2026-06-11

### Added
- `scripts/scan_ats.py` — `_fetch_with_retry()` helper: GET with up to 3 attempts and exponential backoff (1s/2s/4s); 4xx errors (except 429) are not retried; applied to all 5 ATS fetch call sites
- `modes/rescore-offers.md` — new mode documenting when and how to run `scripts/rescore.py` after changing scoring config

### Changed
- `scripts/scan_ats.py` — `_RETRY_ATTEMPTS` derived from `len(_RETRY_BACKOFF)` to keep both in sync; `_TIMEOUT` (10s) used as default for `_fetch_with_retry`; fixed fabricated "Expected output" block in `modes/rescore-offers.md` to show actual output format
- `scripts/scan_portals.py` — `_enrich()` now wraps `_fetch_description` in `asyncio.wait_for(timeout=15.0)`; timed-out offers log a warning and get an empty description instead of hanging indefinitely
- `dashboard/db.py` — corrected inline comment on `check_same_thread=False` to accurately attribute it to the background scan coroutine rather than FastAPI's thread pool
- `scripts/pre_filter.py` — extracted magic numbers into named constants: `_DEFAULT_RTT_DAYS` (10), `_ANNUAL_WORKING_DAYS` (218), `_MEAL_TICKET_VALUE_PER_DAY` (9.0), `_INTERESSEMENT_RATE` (0.05); improves maintainability of salary reconstruction logic

### Fixed
- `dashboard/app.py` — added `OSError` handling to `POST /profile/experience`, `/profile/skills`, `/profile/education`, and `/profile/projects`; filesystem write failures now return a 200 error template instead of crashing with an unhandled 500
- `tests/test_profile_routes.py` — added 4 `TestProfileSaveErrors` tests covering the new `OSError` paths for experience, skills, education, and projects routes

### Added
- `tests/test_dashboard_app.py::TestScan::test_scan_task_exception_sets_error_status` — test that verifies `_run_scan_task` correctly sets `scan_status="error"` and captures exception message when `_run_pipeline` raises
- `scripts/generate_cover_letter.py` — bilingual support (`--lang fr|en`): auto-translated subject line, salutation, and closing; `subject` and `closing_line` overridable via context JSON
- `scripts/generate_cover_letter.py` — `_normalize_for_ats` stub hook for future ATS sanitisation
- `scripts/generate_prep_sheet.py` — `section_company` and `section_questions` i18n parameters; `_normalize_for_ats` stub
- `templates/cv-fr/cv.html.j2` — optional `hobbies` section rendered as dot-separated inline list
- `modes/prepare-entretien.md` — new Claude CLI mode generating interview prep sheet only (called for Entretien RH / Entretien tech / Offre statuses)

### Changed
- `templates/cover-letter-fr/cover-letter.html.j2` — subject and closing line now resolve from `subject`/`closing_line` context variables or `lang` fallback
- `templates/prep-sheet-fr/prep-sheet.html.j2` — section titles use `section_company` / `section_questions` Jinja2 variables with French defaults
- `templates/partials/offer_detail.html` — action buttons now conditional on offer status: "Préparer candidature" (with optional LM checkbox) shown for apply statuses only; "Préparer entretien" shown for interview statuses only; no action button for terminal statuses
- `modes/prepare-candidature.md` — added `--no-prep` flag to skip prep sheet generation; Phase 6 summary conditional on flag

## 2026-06-04

### Changed
- `dashboard/templates/` — full UI redesign: deep-purple gradient background (`#0f0a1e`→`#1a0f30`), Indigo+Rose accent palette (`#6366f1`/`#8b5cf6`/`#ec4899`), rounded-lg cards with surface/raised/border color system (`#1e1535`/`#2d1f5e`); no logic changes
- `dashboard/templates/base.html` — new nav style (gradient logo text, indigo active link), shared `.grade-a/b/c/d/f` badge classes, `.bg-accent` / `.bg-accent-rose` gradient utilities
- `dashboard/templates/index.html` — left panel dark surface, filter inputs and selects dark-styled with indigo focus rings
- `dashboard/templates/partials/offer_list.html` — avatar initials per company (`bg-accent` gradient circle), gradient grade badges via `.grade-*` classes, hover highlight `#251b45`
- `dashboard/templates/partials/offer_detail.html` — large avatar header, indigo→transparent gradient divider, indigo metadata labels, styled action buttons (Préparer candidature uses `bg-accent`); 2-column layout (meta+actions left, description+notes right) occupying full panel height
- `dashboard/templates/partials/offer_notes.html` — dark surface textarea, indigo focus border via `onfocus`/`onblur`; textarea stretches to fill remaining column height
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
