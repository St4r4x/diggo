# Per-user settings & profile in DB — Design Spec

Date: 2026-07-05
Status: approved

## Goal

Move all per-user configuration from flat files (`config/settings.yaml`, `contact.yaml`, `cv.yaml`, `profile.md`, `ats_map.yaml`) into PostgreSQL. Each user gets their own isolated data. Expose editors in the dashboard at `/profile` (identity + CV) and `/settings` (search preferences + ATS targets).

## Architecture

**Approach:** Option B (fully structured) with B2 separation (contact/CV on `/profile`, search prefs on `/settings`).

- Contact and CV decomposed into typed columns and relational tables — enables proper forms, validation, and future querying.
- `user_settings` is a separate table from `user_profiles` (identity ≠ search preferences).
- `user_ats_targets` is a CRUD table (multiple rows per user).
- `profile_md` stored as TEXT in `user_profiles` (Markdown, free-form, no structure to impose).
- No RLS at DB level for now — all queries are scoped with `WHERE user_id = %s` in application code.

## Global Constraints

- Python 3.11+, psycopg2, FastAPI, HTMX — no new frameworks
- No ORM — raw SQL via psycopg2, same pattern as `dashboard/db.py`
- Type hints on all function signatures
- `user_id` is a TEXT (UUID string from Supabase Auth JWT `sub` claim)
- `lang` on CV tables: `'fr'` or `'en'` — both languages supported for PDF generation
- Autosave debounce: 800ms (same pattern as offer notes)
- Files in `config/` remain on disk; they are read as fallback on first DB access if DB row is empty (auto-migration on first login)

---

## Schema — 9 new tables, 1 Alembic migration

### `user_profiles`
```sql
CREATE TABLE user_profiles (
    user_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    title       TEXT NOT NULL DEFAULT '',
    email       TEXT NOT NULL DEFAULT '',
    phone       TEXT NOT NULL DEFAULT '',
    location    TEXT NOT NULL DEFAULT '',
    linkedin    TEXT NOT NULL DEFAULT '',
    github      TEXT NOT NULL DEFAULT '',
    profile_md  TEXT NOT NULL DEFAULT ''
);
```

### `user_settings`
```sql
CREATE TABLE user_settings (
    user_id              TEXT PRIMARY KEY,
    keywords             TEXT[] NOT NULL DEFAULT '{}',
    portal_queries       TEXT[] NOT NULL DEFAULT '{}',
    location             TEXT NOT NULL DEFAULT '',
    contract             TEXT NOT NULL DEFAULT 'CDI',
    experience_max_years INT NOT NULL DEFAULT 3,
    salary_min           INT NOT NULL DEFAULT 0,
    salary_max           INT NOT NULL DEFAULT 0,
    target_companies     TEXT[] NOT NULL DEFAULT '{}',
    follow_up_days       INT NOT NULL DEFAULT 7
);
```

### `user_ats_targets`
```sql
CREATE TABLE user_ats_targets (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    name        TEXT NOT NULL,
    careers_url TEXT NOT NULL
);
CREATE INDEX ix_user_ats_targets_user ON user_ats_targets (user_id);
```

### `user_cv_meta`
```sql
CREATE TABLE user_cv_meta (
    user_id TEXT NOT NULL,
    lang    TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, lang)
);
```

### `user_experience`
```sql
CREATE TABLE user_experience (
    id         SERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL,
    lang       TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT '',
    company    TEXT NOT NULL DEFAULT '',
    type       TEXT NOT NULL DEFAULT '',  -- "Alternance", "CDI", "Stage"
    period     TEXT NOT NULL DEFAULT '',
    sort_order INT NOT NULL DEFAULT 0
);
CREATE INDEX ix_user_experience_user_lang ON user_experience (user_id, lang);
```

### `user_experience_bullets`
```sql
CREATE TABLE user_experience_bullets (
    id            SERIAL PRIMARY KEY,
    experience_id INT NOT NULL REFERENCES user_experience(id) ON DELETE CASCADE,
    text          TEXT NOT NULL DEFAULT '',
    sort_order    INT NOT NULL DEFAULT 0
);
```

### `user_skills`
```sql
CREATE TABLE user_skills (
    id         SERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL,
    lang       TEXT NOT NULL,
    category   TEXT NOT NULL,
    skill      TEXT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0
);
CREATE INDEX ix_user_skills_user_lang ON user_skills (user_id, lang);
```

### `user_certifications`
```sql
CREATE TABLE user_certifications (
    id      SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    name    TEXT NOT NULL,
    issuer  TEXT NOT NULL DEFAULT '',
    year    INT
);
```

### `user_education`
```sql
CREATE TABLE user_education (
    id      SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    lang    TEXT NOT NULL,
    degree  TEXT NOT NULL DEFAULT '',
    school  TEXT NOT NULL DEFAULT '',
    year    INT
);
```

---

## Data access layer — `dashboard/user_data.py`

New module, same psycopg2 pattern as `db.py`. All functions take `conn` (psycopg2 connection) as first arg.

```python
# Profile
get_profile(conn, user_id: str) -> dict | None
save_profile(conn, user_id: str, data: dict) -> None  # upsert

# Settings
get_settings(conn, user_id: str) -> dict | None
save_settings(conn, user_id: str, data: dict) -> None  # upsert

# ATS targets
get_ats_targets(conn, user_id: str) -> list[dict]
add_ats_target(conn, user_id: str, name: str, careers_url: str) -> int
delete_ats_target(conn, user_id: str, target_id: int) -> None

# CV
get_cv(conn, user_id: str, lang: str = "fr") -> dict
  # returns {meta: {summary}, experience: [{...bullets: [...]}], skills: [{category, skill}], certifications: [...], education: [...]}
save_cv_meta(conn, user_id: str, lang: str, summary: str) -> None  # upsert
save_experience(conn, user_id: str, lang: str, entries: list[dict]) -> None  # delete+reinsert
save_skills(conn, user_id: str, lang: str, entries: list[dict]) -> None  # delete+reinsert
save_certifications(conn, user_id: str, entries: list[dict]) -> None  # delete+reinsert
save_education(conn, user_id: str, lang: str, entries: list[dict]) -> None  # delete+reinsert
```

`save_experience`, `save_skills`, `save_certifications`, `save_education` use delete-then-reinsert (not per-row upsert) — simpler to implement, correct for full-form saves.

---

## Auto-migration on first login

In `get_profile()`, `get_settings()`, `get_cv()`, `get_ats_targets()`: if the DB row is empty/absent and the corresponding local config file exists, read the file and write it to DB, then return the data.

```python
def get_profile(conn, user_id: str) -> dict:
    row = _fetch_profile(conn, user_id)
    if row is None:
        local = _read_profile_from_files()   # reads contact.yaml + profile.md
        if local:
            save_profile(conn, user_id, local)
            return local
        return _empty_profile()
    return row
```

This runs once per user. After that the files are ignored. No standalone migration script needed.

---

## `profile_parser.py` changes

`load_profile()` and `save_profile()` are updated to call `user_data` instead of reading files directly. They now require `conn` and `user_id` parameters.

```python
# Before
def load_profile() -> dict:
    contact = _parse_contact(_CONTACT_YAML)
    ...

# After
def load_profile(conn, user_id: str) -> dict:
    return user_data.get_profile(conn, user_id)
```

All callers in `app.py` already have `current_user` — they pass `current_user["sub"]` as `user_id`.

---

## Scripts changes

`pre_filter.py`, `scan_ats.py`, `import_offers.py`, `rescore.py`, `daily_report.py` receive `user_id: str` as a parameter. They call `user_data.get_settings()` / `user_data.get_ats_targets()` instead of `yaml.safe_load()`.

`load_settings()` in `pre_filter.py` gains a `user_id` parameter with a fallback to file-based loading when `user_id` is None (for CLI use: `python scripts/rescore.py`).

---

## Dashboard routes

### New `/settings` page

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/settings` | Full settings page |
| POST | `/settings/search` | Save search preferences → partial `partials/settings_search.html` |
| POST | `/settings/ats` | Add ATS target → partial `partials/settings_ats.html` |
| DELETE | `/settings/ats/{id}` | Remove ATS target → partial `partials/settings_ats.html` |

### Updated `/profile` routes

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/profile` | Full profile page (contact + profile_md + CV tabs fr/en) |
| POST | `/profile/contact` | Save contact → partial (existing, rebranched to DB) |
| POST | `/profile/text` | Save profile_md → partial (existing, rebranched to DB) |
| POST | `/profile/cv/meta` | Save CV summary (lang param) → partial |
| POST | `/profile/cv/experience` | Save all experiences for lang → partial |
| DELETE | `/profile/cv/experience/{id}` | Delete one experience → partial |
| POST | `/profile/cv/skills` | Save all skills for lang → partial |
| POST | `/profile/cv/certifications` | Save certifications → partial |
| POST | `/profile/cv/education` | Save education for lang → partial |

---

## Templates

### `/settings` — `templates/settings.html`
- Extends `base.html`
- Section 1: **Recherche** — keywords (one per line textarea, split on `\n`), location, contrat, expérience max (number), salary min/max, target companies (same textarea pattern), follow_up_days
- Section 2: **ATS Targets** — table rows (name, URL, delete button via `hx-delete`), "Ajouter" button triggers inline row

### `/profile` updates — `templates/profile.html`
- Add `fr / en` language tab at top of CV section — switches `lang` param on all CV form posts
- CV sections: Résumé (textarea), Expériences (collapsible cards + bullets), Compétences (category + skills tags), Certifications, Formation
- Each CV section is a HTMX partial with its own save button

---

## Testing

- `tests/test_user_data.py` — unit tests for all `user_data.py` functions using a real test DB connection (same pattern as `test_dashboard_db.py`)
- Auto-migration test: empty DB + existing config file → `get_profile()` returns populated data and writes to DB
- `/settings` route tests in `tests/test_dashboard_app.py` — GET 200, POST saves, DELETE removes
- Profile CV route tests — POST saves experience, DELETE removes experience

---

## File changes summary

| File | Action |
|------|--------|
| `alembic/versions/0002_user_profile_settings.py` | New migration (9 tables) |
| `dashboard/user_data.py` | New module |
| `dashboard/profile_parser.py` | Update `load_profile`/`save_profile` to use `user_data` |
| `dashboard/app.py` | Wire `user_id` into profile/settings routes; add `/settings` routes |
| `scripts/pre_filter.py` | `load_settings()` accepts optional `user_id` |
| `scripts/scan_ats.py` | `scan_ats()` accepts optional `user_id` |
| `scripts/import_offers.py` | Pass `user_id` through to `load_settings` and `scan_ats` |
| `scripts/rescore.py` | Pass `user_id` through to `load_settings` |
| `scripts/daily_report.py` | Pass `user_id` through to `load_settings` |
| `dashboard/templates/settings.html` | New full page |
| `dashboard/templates/partials/settings_search.html` | New partial |
| `dashboard/templates/partials/settings_ats.html` | New partial |
| `dashboard/templates/profile.html` | Add CV section with lang tabs |
| `dashboard/templates/partials/profile_cv_*.html` | New partials (meta, experience, skills, certs, education) |
| `tests/test_user_data.py` | New test file |
