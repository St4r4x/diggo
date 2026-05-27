# career-ops-fr

Automated AI/ML job search pipeline for the French market — scraping, scoring, dashboard, and Claude Code-assisted application generation (CV PDF, cover letter, interview prep sheet).

## Features

- **Portal scraping** — APEC, LinkedIn, Glassdoor, Indeed, WTTJ with offer description fetching
- **ATS scraping** — Greenhouse, Lever, Ashby for target companies
- **LLM scoring** — offers scored 0–5 and graded A–F against your profile
- **Daily report** — markdown digest of recommended offers
- **Dashboard** — FastAPI + HTMX web UI to track applications (status, notes, CV/LM paths)
- **PDF generation** — tailored CV, cover letter, and interview prep sheet via WeasyPrint + Jinja2
- **Claude Code skill** — `modes/prepare-candidature.md` drives end-to-end application prep

## Quick start

```bash
# 1. Clone and create virtualenv
git clone git@github.com:St4r4x/career-ops-fr.git
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
```

## Claude Code skills

With [Claude Code](https://claude.ai/code), open this repo and use:

```
# Score a new offer (paste description in chat)
# → open modes/score-offer.md

# Generate tailored CV + cover letter + prep sheet for an offer in the DB
# → open modes/prepare-candidature.md --offer-id <id>
```

## Configuration

| File | Purpose |
|------|---------|
| `config/profile.md` | Your full professional profile (gitignored) |
| `config/contact.yaml` | Name, email, phone, GitHub (gitignored) |
| `config/settings.yaml` | Search keywords, scoring thresholds, target companies |
| `config/ats_map.yaml` | Target company ATS URLs (Greenhouse / Lever / Ashby) |
| `portals/fr/*.yaml` | Portal scraper configs (selectors, pagination) |

## Project structure

```
scripts/        pipeline logic (scan, dedup, pre-filter, import, report, PDF gen)
dashboard/      FastAPI + HTMX application tracker
templates/      Jinja2 + CSS templates for CV / cover letter / prep sheet
portals/        portal YAML configs
config/         profile and settings (profile.md and contact.yaml are gitignored)
modes/          Claude Code skill prompts
tests/          pytest suite
```

## Requirements

- Python 3.11+
- Playwright (Chromium)
- WeasyPrint (system fonts + Cairo required — see [WeasyPrint docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html))
- Anthropic API key (for scoring and prepare-candidature skill)
