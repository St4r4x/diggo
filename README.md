# Diggo · v0.11

Automated AI/ML job search pipeline for the French market — scraping, scoring, dashboard, and AI-assisted application generation (CV PDF, cover letter, interview prep sheet).

## Run the app (daily use)

> **Prerequisites (first time only):** see [Quick start](#quick-start) below.

```bash
# 1. Start the local auth + DB stack (must be running before the dashboard)
supabase start

# 2. Start the stack (API + frontend + proxy)
docker compose up api web proxy

# → http://localhost:8000  (log in with your Supabase account)
```

To stop everything:

```bash
docker compose down
supabase stop
```

---

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│  1. SCAN          Scrape job portals + ATS → raw offers          │
│  2. SCORE         Keyword + description signals → grade A–F      │
│  3. IMPORT        Deduplicate, filter, store in PostgreSQL DB     │
│  4. DASHBOARD     Review offers, track applications              │
│  5. APPLY         Generate tailored CV + cover letter + prep     │
└─────────────────────────────────────────────────────────────────┘
```

Steps 1–3 run automatically when you click **Scanner** in the dashboard.
Step 5 uses Claude Code to generate PDFs for a specific offer.

---

## Quick start

### 1. Clone and set up

```bash
git clone https://github.com/St4r4x/diggo.git
cd diggo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
playwright install chromium
```

### 2. Start the local Supabase stack

```bash
supabase start
# Gives you: API URL, anon key, JWT secret, DB URL
```

### 3. Configure environment

```bash
cp .env.example .env
# Fill in values from `supabase status`
```

Key variables:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL URL — `postgresql://postgres:postgres@127.0.0.1:54322/postgres` |
| `SUPABASE_URL` | Internal Supabase API URL (used by the container for JWKS) — `http://host.docker.internal:54321` in Docker |
| `SUPABASE_PUBLIC_URL` | Browser-facing Supabase URL — `http://localhost:54321` |
| `SUPABASE_ANON_KEY` | Anon key from `supabase status` |
| `SUPABASE_JWT_SECRET` | JWT secret from `supabase status` |
| `ALLOWED_ORIGINS` | CORS-allowed origins — `http://localhost:8000` for local dev |
| `SECRET_KEY` | Encrypts per-user Hugging Face tokens at rest — generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `COOKIE_SECURE` | Set to `true` in production (HTTPS only); `false` for local dev |
| `DEV_AUTO_LOGIN` | Set to `true` to bypass auth in local dev (hardcoded dev user) |

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Configure your profile (gitignored — personal data)

```bash
cp config/contact.yaml.example config/contact.yaml   # name, email, phone, LinkedIn, GitHub
cp config/profile.md.example   config/profile.md     # full professional profile for scoring & LLM modes
cp config/cv.yaml.example      config/cv.yaml        # CV content (experience, skills, education)
cp config/settings.yaml.example config/settings.yaml # search keywords, location, salary range, target companies
cp config/ats_map.yaml.example  config/ats_map.yaml  # direct ATS URLs to monitor (Greenhouse/Lever/Ashby)
```

> **Note:** `settings.yaml` and `ats_map.yaml` are read once on first login and migrated into the database. After that, edit them via the **Paramètres** page in the dashboard (`/settings`). The files serve as the initial seed only.

### 6. Start the stack

```bash
docker compose up api web proxy
# → http://localhost:8000
```

Log in at `/login` with your Supabase account (create one at `/signup`).

---

## Authentication

The dashboard uses [Supabase Auth](https://supabase.com/docs/guides/auth) with httpOnly session cookies.

| Route | Description |
|-------|-------------|
| `/login` | Email + password login |
| `/signup` | Account creation (email confirmation disabled in local dev) |
| `/auth/confirm` | Post-signup confirmation page |
| `/auth/reset-password` | Password reset (link sent by email) |

In local dev, emails are intercepted by **Inbucket** at `http://localhost:54324`.

To bypass auth entirely during development, set `DEV_AUTO_LOGIN=true` in `.env`.

---

## Dashboard

| Route | Description |
|-------|-------------|
| `/candidatures` | Offer list with filters and a detail panel — status quick-change, notes autosave, edit form, delete, scan trigger, and "Préparer candidature"/"Préparer entretien" actions; shared nav (logo, Candidatures/Stats/Profil/Paramètres links, user email, logout) |
| `/stats` | Pipeline statistics — response rate, interview count, funnel with conversion rates, daily report widget |
| `/profile` | Profile editor — contact info, résumé, and CV editor (FR/EN tabs, editable) |
| `/settings` | Preferences — search keywords, active portals picker (flags portals that require registration), salary range, target companies, ATS targets CRUD, Hugging Face API token |

Every page above is served by the Next.js frontend (`web`), backed by the FastAPI JSON API under `/api/*` (`dashboard/api.py`). `POST /api/offers/{offer_id}/prepare` runs the LLM pipeline: analyzes the offer, rewrites the CV summary, writes the cover letter, generates the interview prep sheet, and renders all three as PDFs.

---

## Scoring

Offers are scored 0–5 and graded A–F using keyword and description signals — no LLM required:

| Signal | Points |
|--------|--------|
| Keyword match in title | +1.0 per keyword |
| Target company | +1.0 |
| Location match (Paris) | +1.0 |
| Junior / alternance | +0.5 |
| Tech skills in description (Python, PyTorch, Docker…) | +0.1/skill, cap +1.0 |
| Experience ≤ threshold | +0.5 |
| CDI mentioned | +0.3 |
| Salary in target range (FR package: 13e mois, RTT, TR) | +0.5 |
| ATS quality portal (Lever, Greenhouse, Ashby) | +0.3 |
| Thin description / no tech / no salary | −0.5 penalty |

**Grade thresholds:** A ≥ 4.0 · B ≥ 3.0 · C ≥ 2.0 · D ≥ 1.0 · F < 1.0

Expired offers ("À envoyer" with a dead URL) are automatically marked **Abandonnée** on each scan.

---

## Generating applications with Claude Code

The dashboard shows context-sensitive action buttons per offer. Run the copied command in your terminal from the repo root.

```bash
# Score a new offer (paste the job description in chat)
claude --system-prompt "$(cat modes/score-offer.md)"

# CV only (apply statuses — button unchecked)
claude --system-prompt "$(cat modes/generate-cv.md)" "Génère le CV pour l'offre ID <id>"

# CV + cover letter (apply statuses — "Inclure lettre de motivation" checked)
claude --system-prompt "$(cat modes/prepare-candidature.md)" "Prépare la candidature pour l'offre ID <id> --no-prep"

# Interview prep sheet only (interview statuses: Entretien RH / Entretien tech / Offre)
claude --system-prompt "$(cat modes/prepare-entretien.md)" "Prépare l'entretien pour l'offre ID <id>"

# Cover letter only, without the rest of the prepare-candidature pipeline
claude --system-prompt "$(cat modes/generate-cover-letter.md)" "Écris la lettre de motivation pour l'offre ID <id>"

# Rescore all existing offers after changing config/settings.yaml
claude --system-prompt "$(cat modes/rescore-offers.md)"
```

`prepare-candidature` phases (when run manually without `--no-prep`):
1. Load your profile and fetch the offer description
2. Analyse the offer (top skills, keywords, gaps, hook angle)
3. Generate a tailored CV PDF (FR by default; EN if the offer requires it)
4. Write and generate a cover letter PDF (in the offer's language)
5. Generate an interview prep sheet PDF (8–12 questions)

All PDFs are saved to `output/<slug>-<date>/` and paths are written back to the DB.

---

## Description fetching

The `scripts/backfill_descriptions.py` script recovers missing descriptions without LLM (~98% coverage via pure HTTP):

| Platform | Strategy | Browser needed |
|----------|----------|----------------|
| APEC | Internal REST API (`cms/webservices/offre/public`) | No |
| Lever | Public REST API (`api.lever.co/v0/postings/{company}/{uuid}`) | No |
| Greenhouse | Public boards API (`boards-api.greenhouse.io/v1/boards/{company}/jobs/{id}`) | No |
| Ashby | JSON-LD `JobPosting` block in static HTML | No |
| Indeed | Playwright with canonical URL | Yes (Cloudflare) |

```bash
docker compose exec api python3 scripts/backfill_descriptions.py
```

---

## Docker

```bash
# Start the full stack (API + frontend + proxy)
docker compose up api web proxy

# One-shot pipeline run (scrape + score + import)
docker compose --profile manual run --rm pipeline

# Backfill missing descriptions
docker compose exec api python3 scripts/backfill_descriptions.py
```

The stack is now three services behind a single nginx proxy on `127.0.0.1:8000`: `api` (FastAPI, pure JSON API under `/api/*` — no rendered pages left), `web` (Next.js frontend, serving the entire dashboard: `/`, `/login`, `/signup`, `/auth/confirm`, `/auth/reset-password`, `/candidatures`, `/stats`, `/profile`, `/settings`), `proxy` (nginx, routes `/api/*` and `/_next/*` accordingly, every other path to `web`). The `api` container connects to the host-side Supabase CLI stack via `host.docker.internal`.

---

## Configuration files

| File | Tracked | Purpose |
|------|---------|---------|
| `.env` | ❌ gitignored | Runtime secrets (DB URL, Supabase keys, API keys) |
| `.env.example` | ✅ | Template for `.env` |
| `config/contact.yaml` | ❌ gitignored | Name, email, phone, LinkedIn, GitHub |
| `config/profile.md` | ❌ gitignored | Full profile used by LLM scoring modes |
| `config/cv.yaml` | ❌ gitignored | CV content: experience (with stack tags), skill_categories, certifications, education, hobbies |
| `config/settings.yaml` | ✅ | Search keywords, salary range, scoring thresholds, target companies — read once on first login, then stored in DB |
| `config/ats_map.yaml` | ✅ | Direct ATS URLs for Greenhouse / Lever / Ashby companies — read once on first login, then stored in DB |
| `portals/fr/*.yaml` | ✅ | Portal scraper YAML configs (selectors, pagination, `status: active`/`needs_auth` — surfaced in the Settings page's portal picker) |
| `supabase/` | ✅ | Supabase CLI local config (`config.toml`) |

`*.example` files are provided for each gitignored config — copy and fill in your data.

---

## Project structure

```
scripts/
  import_offers.py          Full pipeline: scan → dedup → score → DB import
  scan_portals.py           Portal scraping (APEC, WTTJ, LinkedIn, Glassdoor, Indeed)
  scan_ats.py               ATS scraping (Greenhouse, Lever, Ashby)
  backfill_descriptions.py  Fetch missing descriptions (HTTP-first, Playwright fallback)
  pre_filter.py             Scoring engine (keyword + description signals)
  rescore.py                Rescore all existing DB offers (use after changing settings)
  liveness.py               HTTP-first liveness checker (APEC internal API aware)
  dedup.py                  Accent-insensitive deduplication
  description_parser.py     Parse raw job description text into structured fields per portal
  daily_report.py           Markdown digest generation
  generate_pdf.py           CV PDF generation (WeasyPrint + Jinja2, FR/EN)
  generate_cover_letter.py  Cover letter PDF generation
  generate_prep_sheet.py    Interview prep sheet PDF generation
  models.py                 Shared data models

dashboard/
  app.py                    FastAPI app entrypoint — mounts api.py's router, nothing else
  api.py                    JSON API router under /api/* (auth, offers, scan, prepare, stats, profile, settings — consumed by the Next.js frontend)
  auth.py                   Supabase JWT validation (JWKS/ES256), cookie helpers, DEV_AUTO_LOGIN bypass
  db.py                     PostgreSQL persistence layer (psycopg2, all queries scoped by user_id)
  user_data.py              Per-user data access layer (profile, settings, ATS targets, CV tables)
  profile_parser.py         Profile load/save — delegates to user_data (DB); file fallback for migration
  scan_state.py             Per-user in-process scan state (start/poll)
  prepare_state.py          Per-offer in-process prepare state (start/poll)
  llm.py                    LLM client + phase functions for server-side candidature prep (Hugging Face Inference Providers)
  data/                     (gitignored)

frontend/
  app/                       Next.js App Router pages (/, /login, /signup, /auth/*, /candidatures, /stats, /profile, /settings)
  components/                Page-specific UI (candidatures/, profile/, settings/, stats/) + shared (dashboard-nav, theme-toggle, ui/)
  lib/                       Shared client helpers — supabase.ts, session.ts, types.ts, status-colors.ts, api-errors.ts

proxy/
  nginx.conf                 Reverse proxy — routes /api/* to `api`, everything else to `web`

supabase/
  config.toml               Supabase CLI local config (auth, DB, redirects)

alembic/                    Alembic migrations (PostgreSQL schema)

templates/
  cv-fr/                    French CV template (HTML + CSS)
  cv-en/                    English CV template (HTML + CSS)
  cover-letter-fr/          Cover letter template (FR/EN via context variables)
  prep-sheet-fr/            Interview prep sheet template

config/                     Settings and gitignored personal data
modes/                      Claude Code instruction files
portals/fr/                 Portal scraper YAML configs
tests/                      pytest suite
output/                     Generated PDFs (gitignored)
```

---

## Requirements

- Python 3.11+
- [Supabase CLI](https://supabase.com/docs/guides/cli) — for local auth + PostgreSQL stack
- Playwright (Chromium) — only needed for Indeed scraping
- WeasyPrint + system fonts (Cairo, Pango) — see [WeasyPrint docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)
- Anthropic API key — for LLM scoring modes (`score-offer`, `prepare-candidature`)
