# Structured Description Parsing — Design Spec

**Date:** 2026-06-15  
**Status:** Approved

## Goal

Replace the single flat `description` text blob with a 6-field structured `ParsedDescription` JSON, parsed per-portal using deterministic heuristics. Improves scoring precision, enables auto-population of prep sheet / cover letter generators, and exposes sectioned descriptions in the dashboard.

---

## Data Model

### New dataclass `ParsedDescription` in `scripts/models.py`

```python
@dataclass
class ParsedDescription:
    mission: str = ""
    profil: str = ""
    stack: str = ""
    avantages: str = ""
    contrat: str = ""
    salaire: str = ""
```

### `RawOffer` changes

Add `parsed_description: ParsedDescription | None = None`. The existing `description: str` field is kept in-memory as the raw text buffer during the scrape→parse→filter pipeline. It is no longer written to the database.

### SQLite `applications` table

Two changes via `ALTER TABLE` migration:

1. Column `description TEXT NOT NULL DEFAULT ''` — now stores the JSON-serialised `ParsedDescription`:
   ```json
   {"mission": "...", "profil": "...", "stack": "...", "avantages": "...", "contrat": "...", "salaire": "..."}
   ```
   Legacy rows (plain text) are handled gracefully: any reader that calls `json.loads()` wraps in a try/except and falls back to displaying the raw text.

2. Column `portal TEXT NOT NULL DEFAULT ''` — required by `backfill_descriptions.py` to dispatch to the correct per-portal parser.

---

## New Module: `scripts/description_parser.py`

**Public interface:**

```python
def parse_description(raw: str, portal: str) -> ParsedDescription: ...
```

Dispatches to a portal-specific parser. Falls back to `_parse_generic` for unknown portals.

### Per-portal strategies

| Portal | Strategy |
|--------|----------|
| `apec` | Re-split the concatenated blob on known French section markers (e.g. "Profil recherché", "L'entreprise") using regex |
| `lever` | Split HTML on `<h3>`/`<h4>` headings ("About the role", "Requirements", "What we offer") |
| `greenhouse` | Same as Lever — `<h2>`/`<h3>` HTML headings |
| `ashby` | JSON-LD `description` field is HTML — same heading-based split |
| `indeed` | Plain text, no reliable structure — regex heuristics on French/English section keywords |
| `wtfj` / `linkedin` / `glassdoor` | Same heuristic approach as Indeed |
| `_generic` | Fallback: put everything in `mission`, leave other fields empty |

For `ApecApiExtractor`: keep the existing concatenation. `_parse_apec` re-splits the blob — simpler than changing the extractor's return type.

---

## Integration Points

### `import_offers.py` — `insert_offer()`

Before inserting:
1. If `offer.parsed_description` is already populated (ATS path) → serialise to JSON.
2. Otherwise → call `parse_description(offer.description, offer.portal)` → serialise.
3. Write the JSON to the `description` column and `offer.portal` to the `portal` column.

### `backfill_descriptions.py`

After extracting raw text: call `parse_description(raw_text, portal)` and save the JSON. Reads the `portal` column from the DB (added by the migration).

### `pre_filter.py`

Add a helper `_desc_blob(offer: RawOffer) -> str`:

```python
def _desc_blob(offer: RawOffer) -> str:
    if offer.parsed_description:
        pd = offer.parsed_description
        return " ".join(filter(None, [pd.mission, pd.profil, pd.stack, pd.avantages, pd.contrat, pd.salaire]))
    return offer.description or ""
```

Every occurrence of `offer.description or ""` in `score_offer()` is replaced by `_desc_blob(offer)`. No scoring logic changes.

### `dashboard/app.py`

When reading `description` from the DB:
- Try `json.loads(description)` → construct `ParsedDescription` → display 6 sections.
- On `json.JSONDecodeError` (legacy rows) → display raw text as before.

### Generators (`generate_prep_sheet.py`, `generate_cover_letter.py`)

Out of scope for this iteration. Left as a TODO: auto-populate `tech_stack` from `parsed_description.stack` and `company_summary` from `parsed_description.mission`.

---

## Migration

Single SQL migration at application startup (idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS` or guarded by a try/except on `OperationalError`):

```sql
ALTER TABLE applications ADD COLUMN portal TEXT NOT NULL DEFAULT '';
```

The `description` column already exists — its content changes meaning (text → JSON) but the column is kept as-is.

---

## Testing

- `tests/test_description_parser.py` — one test per portal parser with fixture strings; assert each field is correctly extracted
- `tests/test_pre_filter.py` — extend existing tests to pass offers with `parsed_description` set; verify `_desc_blob` produces the same scoring outcomes as the old blob path
- `tests/test_import_offers.py` — verify `insert_offer` writes valid JSON to `description` and populates `portal`

---

## Out of Scope

- LLM-based parsing (future option if deterministic parsers prove too fragile)
- Auto-populating prep sheet / cover letter generators from `ParsedDescription`
- Retroactive backfill of all existing DB rows (can be done via `backfill_descriptions.py` after the migration)
