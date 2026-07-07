# Deployment TODO — career-ops-fr SaaS

Audit date: 2026-07-03
Target: multi-user hosted deployment (replace Claude Code CLI with server-side LLM)

Items are ordered by dependency: nothing in a later group can be done before the earlier ones.

---

## Group 0 — Blockers (must ship before anything is usable)

### Stack choice: Supabase
- **Dev local** : `postgres:16` container dans docker-compose + JWT vérifié localement
- **Prod** : Supabase cloud (PostgreSQL managé + Auth + Storage pour les PDFs)
- Auth = Supabase Auth (JWT) — pas besoin de FastAPI-Users ni de `users` table maison
- Storage = Supabase Storage (buckets) — remplace le besoin S3/R2
- Row Level Security PostgreSQL : policies `auth.uid()` pour scoper les données par user côté DB

### 0.1 Authentication (via Supabase Auth)
- [ ] Ajouter `supabase-py` à `requirements.txt`
- [ ] Ajouter env vars : `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`
- [ ] Créer un FastAPI dependency `get_current_user` qui vérifie le JWT Supabase (décoder avec `python-jose` ou `PyJWT`, vérifier `SUPABASE_JWT_SECRET`)
- [ ] Ajouter `Depends(get_current_user)` sur toutes les routes
- [ ] Ajouter endpoints login/register (ou déléguer entièrement au client Supabase JS côté front)
- [ ] docker-compose dev : ajouter service `postgres:16` + env vars locales

### 0.2 Multi-tenancy — database (PostgreSQL)
- [ ] Remplacer SQLite par PostgreSQL : `asyncpg` ou `psycopg2` dans `db.py`
- [ ] Ajouter `DATABASE_URL` env var (`postgresql://...`)
- [ ] Ajouter Alembic pour les migrations (remplacer `_migrate()` startup)
- [ ] Ajouter `user_id UUID NOT NULL REFERENCES auth.users(id)` sur `applications`
- [ ] Activer Row Level Security sur `applications` : `USING (user_id = auth.uid())`
- [ ] Ajouter index sur `(user_id, status)`
- [ ] Scoper toutes les méthodes `DB` à `user_id` (get_all, get_by_id, update, delete, get_stats, get_followups)
- [ ] Migrer `scripts/import_offers.py`, `rescore.py`, `backfill_descriptions.py` pour accepter `user_id`

### 0.3 Multi-tenancy — user settings & profile
- [ ] Store per-user settings in DB (job keywords, location, salary range) — replace `config/settings.yaml`
- [ ] Store per-user profile in DB — replace `config/profile.md` and `config/contact.yaml`
- [ ] Store per-user CV data in DB — replace `config/cv.yaml`
- [ ] Store per-user ATS target list in DB — replace `config/ats_map.yaml`
- [ ] Add profile/settings editor in dashboard (extend existing `/profile` page)
- [ ] Update `pre_filter.py`, `profile_parser.py`, `generate_pdf.py`, `generate_cover_letter.py` to read from DB

---

## Group 1 — LLM migration (core feature replacement)

### 1.1 LLM provider choice

**Primary: Groq** (free tier — 14 400 req/day, 30 req/min)
- Model: `llama-3.3-70b-versatile` (best French quality on free tier) or `llama-3.1-8b-instant` (faster)
- API OpenAI-compatible → `openai` Python client with `base_url="https://api.groq.com/openai/v1"`
- Env var: `GROQ_API_KEY`

**Fallback: Google Gemini Flash 2.0** (free tier — 1 500 req/day, excellent French)
- Lib: `google-generativeai`
- Env var: `GEMINI_API_KEY`

**Self-hosted option (if Jetson Orin NX is available):** Ollama with `mistral:7b` or `llama3.1:8b` — zero API cost, depends on machine uptime.

### 1.2 Server-side LLM calls
- [ ] Add `groq` or `openai` package to `requirements.txt`
- [ ] Implement offer analysis prompt (extract mission, stack, profile, contract — currently phase 2 of `modes/prepare-candidature.md`)
- [ ] Implement CV summary rewrite prompt (highlight skills matching offer — phase 3)
- [ ] Implement cover letter generation prompt (phase 4) — respect style rules: no em-dashes, plain language, closing "Cordialement,"
- [ ] Implement prep sheet generation prompt (8-12 interview questions — phase 5)
- [ ] Wire all four into a `POST /offers/{id}/prepare` route that calls LLM then `generate_pdf.py`
- [ ] Eliminate `/tmp/cl-context-*.json` IPC pattern — pass generated JSON directly in-process
- [ ] Add `GROQ_API_KEY` (+ optional `GEMINI_API_KEY`) to `.env.example`

---

## Group 2 — Infrastructure hardening

### 2.1 Environment variables
- [ ] Add `python-dotenv` + `.env` loading in `dashboard/app.py` and all scripts
- [ ] Create `.env.example` documenting: `DATABASE_URL`, `SECRET_KEY` (encrypts per-user Hugging Face tokens, set via `/settings`), `ALLOWED_ORIGINS`, `STORAGE_BUCKET`, `PROXY_URL`
- [ ] Replace all `Path(__file__).parent.parent / "config"` hardcodes with env-configurable paths

### 2.2 Output / artifact storage (Supabase Storage)
- [ ] Créer un bucket `pdfs` dans Supabase Storage (ou local via docker-compose en dev)
- [ ] Uploader les PDFs générés vers `pdfs/<user_id>/<slug>-<date>/cv.pdf` etc.
- [ ] Stocker l'URL Supabase Storage (pas un path local) dans `cv_path` / `cover_letter_path`
- [ ] Ajouter `GET /offers/{id}/download/cv` et `/cover-letter` générant des signed URLs Supabase

### 2.3 Scan job isolation
- [ ] Replace `app.state.scan_status` + `asyncio.Lock()` with per-user scan state in DB
- [ ] Add `scan_jobs` table: (id, user_id, started_at, status, result_json)
- [ ] Move scan execution to a background worker (Celery/RQ) or asyncio task per user
- [ ] Add per-user scan cooldown (1 scan / hour minimum)
- [ ] Add `GET /scan/status` to poll job status by user

### 2.4 Reports
- [ ] Namespace `reports/daily-*.md` by user: `reports/<user_id>/daily-*.md`
- [ ] Wire `daily_report.py` to user-scoped DB query

---

## Group 3 — Scraping at scale

### 3.1 Playwright hardening
- [ ] Add `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu` to `chromium.launch()` args (`scan_portals.py:348`)
- [ ] Add proxy support: `launch(proxy={"server": os.getenv("PROXY_URL")})` if set
- [ ] Reduce description semaphore from 15 → 3-5 for cloud environments
- [ ] Separate scan worker from web process (run Playwright in dedicated container)

### 3.2 Portal coverage
- [ ] WTTJ: investigate auth requirements, consider adding public API if available
- [ ] Indeed/LinkedIn: evaluate residential proxy cost vs. ATS-only strategy
- [ ] Fallback strategy: ATS scanner (Greenhouse/Lever/Ashby) as primary source, Playwright portals as optional nightly batch

### 3.3 Async fix
- [ ] Convert `scripts/liveness.py:check_liveness()` from `httpx.Client` to `httpx.AsyncClient` (blocks event loop in async scan task — `import_offers.py` → `dashboard/app.py:540`)

---

## Group 4 — Docker & deployment

### Hébergement cible

| Service | Plateforme | Coût |
|---------|------------|------|
| FastAPI web | Railway Hobby (service "web") | ~$0.25/mois (512MB 24/7) |
| Scan worker | Railway Hobby (service "worker", sleep replica) | ~$0.01/mois (actif ~2h/mois) |
| DB + Auth + Storage | Supabase free | $0 |
| LLM | Groq free tier | $0 |
| **Total** | | **~$5.26/mois** (dans le crédit Hobby) |

### 4.1 Job queue (pg_notify — pas de Redis nécessaire)
- [ ] Créer table `scan_jobs` dans Supabase : `(id, user_id, status, created_at, started_at, finished_at, result_json)`
- [ ] FastAPI `POST /scan/start` insère un job dans `scan_jobs` + `NOTIFY scan_queue, '<user_id>'`
- [ ] Worker écoute `LISTEN scan_queue` via `asyncpg` — se réveille sur notification, exécute le scan, écrit le résultat
- [ ] FastAPI `GET /scan/status` lit `scan_jobs` pour l'user courant (polling HTMX existant)

### 4.2 Dockerfiles (2 images séparées)
- [ ] `Dockerfile.web` — FastAPI uniquement, pas de Playwright, image légère (~200MB)
  - Multi-stage : deps prod séparés des deps dev (pytest, pytest-asyncio)
  - Non-root user (`useradd -r appuser && USER appuser`)
  - `HEALTHCHECK CMD curl -f http://localhost:8000/`
- [ ] `Dockerfile.worker` — Playwright + Chrome, image lourde (~1.5GB, acceptable car Railway ne facture que le runtime)
  - `--no-sandbox --disable-dev-shm-usage --disable-gpu` dans `chromium.launch()`
  - Non-root user
  - Entrypoint : `python worker/main.py` (boucle `LISTEN scan_queue`)

### 4.3 Railway config
- [ ] `railway.toml` à la racine avec deux services : `web` et `worker`
- [ ] Service `worker` : `sleepApplication: true` — Railway met en veille si pas de CPU activity
- [ ] Variables d'env Railway : `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, `GROQ_API_KEY`, `SECRET_KEY`, `ALLOWED_ORIGINS`
- [ ] TLS + domaine custom : géré nativement par Railway (pas besoin de Traefik/nginx)

### 4.4 Dev local (docker-compose)
- [ ] Service `postgres:16` avec même schéma que Supabase
- [ ] Service `web` (Dockerfile.web)
- [ ] Service `worker` (Dockerfile.worker)
- [ ] `pg_notify` fonctionne identiquement en local — pas de différence de comportement dev/prod

---

## Group 5 — User experience (per-user settings UI)

- [ ] `/settings` page: keywords, location, salary range, target companies
- [ ] `/profile` page extension: upload/edit CV YAML, contact info, ATS target list
- [ ] Onboarding flow: new user → settings wizard before first scan
- [ ] Scan history per user
- [ ] Download links for generated PDFs in offer detail panel

---

## Group 6 — Security & compliance

### 6.1 Sécurité applicative (OWASP)

**Headers HTTP**
- [ ] Ajouter middleware `secure` (`pip install secure`) — injecte automatiquement : `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`
- [ ] Ajouter `Content-Security-Policy` strict — critique avec HTMX (vecteur XSS si mal configuré) : autoriser uniquement les scripts inline HTMX + CDN Tailwind/HTMX via hash ou nonce

**Rate limiting**
- [ ] Ajouter `slowapi` (`pip install slowapi`) — rate limiter pour FastAPI
- [ ] Limites par route : `/scan/start` → 1 req/heure/user ; `/offers/{id}/prepare` → 10 req/heure/user ; login → 5 tentatives/15min/IP

**CORS**
- [ ] Configurer `CORSMiddleware` avec `allow_origins=[os.getenv("ALLOWED_ORIGINS")]` — pas de `*` en prod
- [ ] HTTPS redirect middleware en prod (`HTTPSRedirectMiddleware`)

**Validation des entrées**
- [ ] Ajouter longueurs max sur tous les champs Form (company, role, notes, etc.) — actuellement aucune limite
- [ ] Valider `offer_url` : doit être une URL HTTP/HTTPS (évite SSRF via import d'offre)
- [ ] Sanitiser les champs `notes` et `contacts` avant stockage (strip HTML)

**Dépendances**
- [ ] Ajouter `pip-audit` en CI : `pip-audit -r requirements.txt` — scan des CVE sur les dépendances
- [ ] Ajouter `detect-secrets` en pre-commit hook — empêche les secrets dans le code

**Sessions / tokens**
- [ ] Durée de vie JWT : 1 heure access token, 7 jours refresh token (configurable via Supabase)
- [ ] Stocker les tokens côté client uniquement (localStorage ou httpOnly cookie) — ne jamais logger les JWT

### 6.2 RGPD (obligatoire — CVs et profils = données personnelles sensibles)

**Base légale et consentement**
- [ ] Consentement explicite à l'inscription : checkbox "J'accepte la politique de confidentialité" non pré-cochée
- [ ] Enregistrer date et version du consentement dans `users` table (`consent_at`, `consent_version`)

**Droits des utilisateurs**
- [ ] `GET /account/export` — export JSON de toutes les données de l'utilisateur (candidatures, profil, settings, PDFs)
- [ ] `DELETE /account` — suppression complète : user row, toutes ses `applications`, fichiers Supabase Storage, settings — avec confirmation par email
- [ ] `POST /account/data-correction` — permettre la modification de toute donnée personnelle (déjà partiellement couvert par `/profile`)

**Conservation des données**
- [ ] Politique de rétention : supprimer automatiquement les données des comptes inactifs depuis > 12 mois (cron job)
- [ ] Ne pas logger de données personnelles (emails, noms, contenu des notes) dans les logs applicatifs

**Infrastructure**
- [ ] Supabase : choisir la région **EU West** (Frankfurt ou Ireland) — transfert hors UE interdit sans garanties
- [ ] Vérifier que Groq (LLM) ne stocke pas les prompts — leurs CGU indiquent "no data retention" sur le free tier, à confirmer
- [ ] Chiffrement au repos activé sur Supabase Storage (activé par défaut)

**Documentation légale**
- [ ] Page `/privacy` — politique de confidentialité (finalité du traitement, durée, droits)
- [ ] Page `/legal` — mentions légales (éditeur, hébergeur)
- [ ] Registre des traitements interne (document, pas une page web) — obligatoire RGPD article 30
- [ ] Bannière cookies si analytics ajoutés plus tard

**Notification de violation**
- [ ] Définir une procédure : en cas de breach, notification CNIL sous 72h (article 33 RGPD)
- [ ] Ajouter un email de contact `dpo@<domaine>` ou contact de responsable de traitement dans les mentions légales

---

## Cost estimates (server-side LLM, per user per "prepare candidature")

| Model | Cost/run | Notes |
|---|---|---|
| Groq llama-3.3-70b | ~$0 (free tier) | 14 400 req/day, best quality open |
| Groq llama-3.1-8b | ~$0 (free tier) | faster, lower quality |
| Gemini Flash 2.0 | ~$0 (free tier) | fallback, 1 500 req/day |
| Claude Sonnet | ~$0.03 | paid fallback, best quality |

Playwright scan per user: ~900MB RAM peak (APEC only). Full 5-portal scan: 2-4GB. Must run in isolated worker.
