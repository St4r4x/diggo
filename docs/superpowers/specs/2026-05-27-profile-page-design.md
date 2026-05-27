# Profile Page — Design Spec

## Goal

Add a `/profile` page to the dashboard that displays and edits the candidate profile — reading from `config/profile.md` and `config/contact.yaml`, and writing back to those files on save.

## Architecture

New route `/profile` on the FastAPI dashboard. The page follows the same full-page pattern as `/stats` (no HTMX partial — full page reload on GET). Edit actions use HTMX POST endpoints that return updated section partials, keeping the rest of the page intact.

`config/profile.md` is parsed on each GET request into a structured dict. Each save endpoint receives form data for one section, merges it into the full structure, and rewrites `profile.md` (and `contact.yaml` for the contact section).

## File Structure

- **Create:** `dashboard/profile_parser.py` — parse `profile.md` + `contact.yaml` into a structured dict; serialize back to Markdown
- **Modify:** `dashboard/app.py` — add GET `/profile` route + POST routes per section
- **Create:** `dashboard/templates/profile.html` — full page template
- **Create:** `dashboard/templates/partials/profile_contact.html` — contact section partial
- **Create:** `dashboard/templates/partials/profile_summary.html` — summary section partial
- **Create:** `dashboard/templates/partials/profile_experience.html` — experience section partial
- **Create:** `dashboard/templates/partials/profile_skills.html` — skills section partial
- **Create:** `dashboard/templates/partials/profile_education.html` — education + certifications partial
- **Create:** `dashboard/templates/partials/profile_projects.html` — personal projects partial
- **Create:** `tests/test_profile_parser.py` — unit tests for the parser
- **Create:** `tests/test_profile_routes.py` — route tests

## Data Model

`profile_parser.py` exposes two functions:

```python
def load_profile() -> dict:
    """Parse profile.md + contact.yaml into a structured dict."""

def save_profile(data: dict) -> None:
    """Serialize structured dict back to profile.md + contact.yaml."""
```

The structured dict shape:

```python
{
  "contact": {
    "name": str, "title": str, "email": str,
    "phone": str, "location": str, "linkedin": str, "github": str
  },
  "summary": str,
  "experience": [
    {
      "title": str, "company": str, "type": str,
      "period": str, "bullets": list[str]
    }
  ],
  "skills": {
    "Machine Learning & Deep Learning": list[str],
    "Computer Vision": list[str],
    # ... other categories
  },
  "education": [
    {"degree": str, "school": str, "period": str}
  ],
  "certifications": list[str],
  "projects": [
    {"name": str, "description": str}
  ]
}
```

## Parsing Strategy

`profile.md` uses a predictable heading structure (`##` for top-level sections, `###` for subsections). The parser reads the file line by line and uses `##`/`###` markers to split into sections. Within each section, the parser applies section-specific logic:

- **Summary**: plain text block after `## Summary`
- **Experience**: `###` heading = one job; bullets = `- ` lines
- **Skills**: `###` heading = category name; `- ` lines = skill items
- **Education**: `- **Degree** — School (Period)` pattern
- **Certifications**: `- Item` lines under `## Certifications & Training`
- **Personal Projects**: `- **Name**: description` pattern

`contact.yaml` is loaded with `yaml.safe_load`. Saves write back with `yaml.dump`.

The serializer reconstructs `profile.md` from the dict in a fixed, predictable order — preserving the exact section structure the file always had.

## Routes

| Method | Path | Body | Returns |
|--------|------|------|---------|
| GET | `/profile` | — | `profile.html` (full page) |
| POST | `/profile/contact` | form fields | `profile_contact.html` partial |
| POST | `/profile/summary` | `summary` textarea | `profile_summary.html` partial |
| POST | `/profile/experience` | JSON-encoded list | `profile_experience.html` partial |
| POST | `/profile/skills` | JSON-encoded dict | `profile_skills.html` partial |
| POST | `/profile/education` | JSON-encoded list | `profile_education.html` partial |
| POST | `/profile/projects` | JSON-encoded list | `profile_projects.html` partial |

Each POST endpoint: loads current profile, merges the submitted section, saves, returns the updated partial with a `✓ Sauvegardé` flash message (fades after 2s via Tailwind + inline JS).

## UI Layout

`profile.html` — full page, same `base.html` layout:

- **Header block**: name + title (from contact) on the left, email + github on the right — read-only, updated when contact section is saved
- **Accordion sections** (one per section, all collapsed by default except Summary):
  - Toggle button: section title + item count (e.g. "Expériences (4 postes)"), chevron
  - Body: structured form for that section
  - Each section has its own "Sauvegarder" button that fires `hx-post` on the section endpoint

### Section form details

**Contact** — 7 inputs in a 2-col grid, `hx-post="/profile/contact"`

**Summary** — single `<textarea rows="4">`, `hx-post="/profile/summary"`

**Experience** — list of job cards. Each card: 4 inputs (2-col grid) + bullets textarea (one bullet per line). "Ajouter un poste" button appends a blank card via HTMX or inline JS. "Supprimer" button on each card. `hx-post="/profile/experience"` sends the full serialized list.

**Skills** — grouped by category. Each category shows skill tags with ✕ to remove + inline input to add new skill. "Ajouter une catégorie" at the bottom. `hx-post="/profile/skills"` sends full dict.

**Education** — list of degree cards (degree, school, period). Add/remove. Below: certifications as a simple textarea (one per line). `hx-post="/profile/education"`.

**Projects** — list of project cards (name + description textarea). Add/remove. `hx-post="/profile/projects"`.

## Navigation

Add "Profil" link to `base.html` nav, after "Stats":

```html
<a href="/profile" ...>Profil</a>
```

Active state: violet underline when `request.url.path == "/profile"`.

## Error Handling

- `config/profile.md` missing: GET `/profile` returns a page with a warning banner "Fichier profile.md introuvable — créez `config/profile.md` à partir de `config/profile.md.example`" and all sections empty but editable (saving creates the file).
- `config/contact.yaml` missing: same treatment, falls back to empty contact dict.
- Parse error on a section: that section shows raw textarea fallback instead of structured form.

## Testing

`tests/test_profile_parser.py`:
- `test_load_contact_from_yaml` — parses contact.yaml correctly
- `test_load_summary` — extracts summary text
- `test_load_experience_entries` — correct count, fields, bullets
- `test_load_skills_categories` — correct category names and item lists
- `test_load_education_and_certs` — degrees + certs parsed
- `test_load_projects` — name/description extraction
- `test_roundtrip` — load → save → load produces identical dict

`tests/test_profile_routes.py`:
- `test_profile_page_loads` — GET `/profile` returns 200
- `test_save_contact` — POST `/profile/contact` updates contact.yaml
- `test_save_summary` — POST `/profile/summary` updates profile.md summary
- `test_save_experience` — POST `/profile/experience` updates experience section

## Constraints

- `profile.md` serialization must preserve all existing sections in the same order — no data loss on save
- No JavaScript framework — plain HTMX + minimal inline JS for add/remove card interactions
- Stays within the existing Tailwind CDN + HTMX 1.9.12 stack
- `config/contact.yaml` and `config/profile.md` remain gitignored — the page works locally only
