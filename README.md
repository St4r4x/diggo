# career-ops-fr

Automated AI/ML job search pipeline for the French market — scraping, scoring, dashboard, and Claude Code-assisted application generation (CV PDF, cover letter, interview prep sheet).

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│  1. SCAN          Scrape job portals + ATS → raw offers          │
│  2. SCORE         Keyword + description signals → grade A–F      │
│  3. IMPORT        Deduplicate, filter, store in SQLite DB        │
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
git clone https://github.com/St4r4x/career-ops-fr.git
cd career-ops-fr
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure your profile (gitignored — personal data)

```bash
cp config/contact.yaml.example config/contact.yaml   # name, email, phone, LinkedIn, GitHub
cp config/profile.md.example   config/profile.md     # full professional profile for scoring & LLM modes
cp config/cv.yaml.example      config/cv.yaml        # CV content (experience, skills, education)
```

Edit each file with your real information. These three files are gitignored and never committed.

### 3. Configure search settings

Edit `config/settings.yaml`:
- `search.keywords` — job titles to search (e.g. "AI Engineer", "ML Engineer")
- `search.location` — target city (default: "Paris")
- `scoring.target_salary_min/max` — your salary range in € for scoring
- `target_companies` — companies that get a scoring bonus

Edit `config/ats_map.yaml` to add direct ATS URLs (Greenhouse / Lever / Ashby) for companies you want to monitor.

### 4. Set your API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 5. Start the dashboard

```bash
docker compose up dashboard
# → http://localhost:8000
```

Click **Scanner** to run the full pipeline. New offers appear in the list automatically.

---

## Dashboard

| Route | Description |
|-------|-------------|
| `/` | Candidatures — offer list with filters, notes, status tracking, scan button; amber bandeau when applications are overdue for follow-up (> 7 days since send) |
| `/stats` | Pipeline statistics — response rate, interview count, funnel with conversion rates, daily report widget |
| `/profile` | Profile editor — edit `profile.md` and `contact.yaml` directly from the browser |

**Offer detail panel:**
- Change status (À envoyer → Envoyée → Entretien RH → …)
- Write notes (autosaved with 800ms debounce)
- Copy the context-sensitive action command (see below): "Préparer candidature" for apply statuses, "Préparer entretien" for interview statuses

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
docker compose exec dashboard python3 scripts/backfill_descriptions.py
```

---

## Docker

```bash
# Start the dashboard (recommended)
docker compose up dashboard

# One-shot pipeline run (scrape + score + import)
docker compose --profile manual run --rm pipeline

# Backfill missing descriptions
docker compose exec dashboard python3 scripts/backfill_descriptions.py
```

---

## Configuration files

| File | Tracked | Purpose |
|------|---------|---------|
| `config/contact.yaml` | ❌ gitignored | Name, email, phone, LinkedIn, GitHub |
| `config/profile.md` | ❌ gitignored | Full profile used by LLM scoring modes |
| `config/cv.yaml` | ❌ gitignored | CV content: experience (with stack tags), skill_categories, certifications, education, hobbies |
| `config/settings.yaml` | ✅ | Search keywords, salary range, scoring thresholds, target companies |
| `config/ats_map.yaml` | ✅ | Direct ATS URLs for Greenhouse / Lever / Ashby companies |
| `portals/fr/*.yaml` | ✅ | Portal scraper configs (selectors, pagination) |

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
  daily_report.py           Markdown digest generation
  generate_pdf.py           CV PDF generation (WeasyPrint + Jinja2, FR/EN)
  generate_cover_letter.py  Cover letter PDF generation
  generate_prep_sheet.py    Interview prep sheet PDF generation
  models.py                 Shared data models

dashboard/
  app.py                    FastAPI routes (/, /stats, /profile, /scan/*, /offers/*)
  db.py                     SQLite persistence layer
  profile_parser.py         Load/save profile.md and contact.yaml
  templates/                Jinja2 templates (base, pages, HTMX partials)
  data/                     applications.db (gitignored)

templates/
  cv-fr/                    French CV template (HTML + CSS)
  cv-en/                    English CV template (HTML + CSS)
  cover-letter-fr/          Cover letter template (FR/EN via context variables)
  prep-sheet-fr/            Interview prep sheet template

config/                     Settings and gitignored personal data
modes/                      Claude Code instruction files
portals/fr/                 Portal scraper YAML configs
tests/                      pytest suite (256 tests)
output/                     Generated PDFs (gitignored)
```

---

## Requirements

- Python 3.11+
- Playwright (Chromium) — only needed for Indeed scraping
- WeasyPrint + system fonts (Cairo, Pango) — see [WeasyPrint docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)
- Anthropic API key — for LLM scoring modes (`score-offer`, `prepare-candidature`)
