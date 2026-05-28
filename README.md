# career-ops-fr

Automated AI/ML job search pipeline for the French market — scraping, scoring, dashboard, and Claude Code-assisted application generation (CV PDF, cover letter, interview prep sheet).

## Features

- **Multi-source scraping** — APEC, Indeed, WTTJ, LinkedIn, Glassdoor portals + direct ATS (Greenhouse, Lever, Ashby)
- **Description fetching** — platform-specific strategies: public REST APIs (Lever, Greenhouse, APEC internal webservice, Ashby JSON-LD); Playwright browser only for Indeed (Cloudflare-protected)
- **LLM scoring** — offers scored 0–5 and graded A–F against your profile
- **Daily report** — markdown digest of recommended offers
- **Dashboard** — FastAPI + HTMX + Tailwind web UI to track applications (Candidatures, Stats, Profil pages)
- **Profile editor** — `/profile` page to edit `config/profile.md` and `config/contact.yaml` directly from the browser
- **PDF generation** — tailored CV, cover letter, and interview prep sheet via WeasyPrint + Jinja2
- **Claude Code modes** — `modes/prepare-candidature.md` drives end-to-end application prep

## Quick start

```bash
# 1. Clone and create virtualenv
git clone git@github.com-personal:St4r4x/career-ops-fr.git
cd career-ops-fr
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Configure your profile
cp config/profile.md.example config/profile.md   # edit with your experience
cp config/contact.yaml.example config/contact.yaml  # edit with your contact info

# 3. Configure target companies and search settings
# edit config/settings.yaml and config/ats_map.yaml

# 4. Set your LLM API key
export ANTHROPIC_API_KEY=sk-ant-...

# 5. Run the pipeline (scrape + score + import to DB)
python -m scripts.import_offers

# 6. Start the dashboard
cd dashboard && uvicorn app:app --reload --port 8000
# → http://localhost:8000
```

## Docker

```bash
# Dashboard only (persistent data via volumes)
docker compose up dashboard

# Full pipeline run (one-shot)
docker compose --profile manual run --rm pipeline

# Backfill missing descriptions on existing offers
docker compose exec dashboard python3 scripts/backfill_descriptions.py
```

## Description fetching strategies

The `scripts/backfill_descriptions.py` script recovers missing job descriptions without LLM or agent usage (~98% coverage with pure HTTP):

| Platform | Strategy | Browser needed |
|----------|----------|---------------|
| APEC | Internal REST API (`cms/webservices/offre/public`) discovered via network interception | No |
| Lever | Public REST API (`api.lever.co/v0/postings/{company}/{uuid}`) | No |
| Greenhouse | Public boards API (`boards-api.greenhouse.io/v1/boards/{company}/jobs/{id}`) | No |
| Ashby | JSON-LD `JobPosting` block embedded in static HTML | No |
| Indeed | Playwright with canonical URL (`/voir-emploi?jk=`) | Yes (Cloudflare) |

## Claude Code modes

With [Claude Code](https://claude.ai/code), open this repo and use:

```
# Score a new offer (paste description in chat)
/score-offer

# Generate tailored CV + cover letter + prep sheet for an offer in the DB
/prepare-candidature
```

## Dashboard pages

| Route | Description |
|-------|-------------|
| `/` | Candidatures — Kanban-style application tracker |
| `/stats` | Statistics and pipeline overview |
| `/profile` | Profile editor — edit profile.md and contact.yaml in-browser |

## Configuration

| File | Purpose |
|------|---------|
| `config/profile.md` | Full professional profile (gitignored) |
| `config/contact.yaml` | Name, email, phone, GitHub (gitignored) |
| `config/settings.yaml` | Search keywords, scoring thresholds, target companies |
| `config/ats_map.yaml` | Target company ATS URLs (Greenhouse / Lever / Ashby) |
| `portals/fr/*.yaml` | Portal scraper configs (selectors, pagination) |

## Project structure

```
scripts/                  Pipeline logic
  import_offers.py        Full scan → dedup → score → DB import
  backfill_descriptions.py Fetch missing descriptions (HTTP-first, Playwright fallback)
  scan_portals.py         Portal scraping (APEC, Indeed, WTTJ, LinkedIn, Glassdoor)
  scan_ats.py             ATS scraping (Greenhouse, Lever, Ashby)
  daily_report.py         Markdown digest generation
  generate_pdf.py         CV PDF generation (WeasyPrint + Jinja2)
  generate_cover_letter.py Cover letter PDF generation
  generate_prep_sheet.py  Interview prep sheet PDF generation
  pre_filter.py           Keyword-based pre-filtering
  dedup.py                Accent-insensitive deduplication
  models.py               Shared data models

dashboard/                FastAPI web application
  app.py                  Routes: /, /stats, /profile (+ HTMX partials)
  db.py                   SQLite persistence layer
  profile_parser.py       Load/save profile.md and contact.yaml
  templates/              Jinja2 templates (base, pages, partials)
  data/                   applications.db (gitignored)

templates/                PDF templates (CV, cover letter, prep sheet)
portals/fr/               Portal scraper YAML configs
config/                   Profile and settings (profile.md and contact.yaml gitignored)
modes/                    Claude Code mode prompts
tests/                    pytest suite (197 tests)
output/                   Generated PDFs (gitignored)
```

## Requirements

- Python 3.11+
- Playwright (Chromium) — only required for Indeed scraping
- WeasyPrint (system fonts + Cairo — see [WeasyPrint docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html))
- Anthropic API key (for scoring and prepare-candidature mode)
