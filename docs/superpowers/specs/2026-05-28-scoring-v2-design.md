# Scoring v2 — Design Spec

**Date:** 2026-05-28
**Scope:** Improve job offer scoring without LLM; rescore all 196 existing DB offers

---

## Problem

86.2% of offers (169/196) are graded F. Root causes:
1. Grade thresholds (D ≥ 3.0) designed for an LLM scoring system, not the keyword-only scorer
2. Job descriptions (~4 200 chars avg) are rich but completely ignored by `score_offer()`
3. 4 settings.yaml keys (`experience_max_years`, `contract`, `target_salary_min/max`) configured but never read
4. Company name matching too strict (e.g. "CAPGEMINI ENGINEERING FRANCE" ≠ "Capgemini Engineering")
5. ATS portals (Lever/Greenhouse/Ashby) produce higher-quality offers but get no bonus

---

## Architecture

Three changes, each independently testable:

1. **`scripts/pre_filter.py`** — add 5 new signals to `score_offer()` + company normalization
2. **`scripts/import_offers.py`** — recalibrate `score_to_grade()` thresholds
3. **`scripts/rescore.py`** — new migration script to rescore existing DB offers

---

## 1. New signals in `score_offer()` — `scripts/pre_filter.py`

### Existing signals (unchanged)

| Signal | Points | Source |
|--------|--------|--------|
| Keyword match in title | +1.0/kw | `offer.title` |
| Company in target_companies | +1.0 | `offer.company` (normalized) |
| Location contains search.location | +1.0 | `offer.location` |
| Junior/alternance in title | +0.5 | `offer.title` |

### New signals

| Signal | Points | Source |
|--------|--------|--------|
| Tech skill in description | +0.1/match, cap +1.0 | `offer.description` |
| Experience required ≤ `experience_max_years` | +0.5 | `offer.description` (regex) |
| CDI mentioned | +0.3 | `offer.description` (regex) |
| Salary in target range | +0.3 | `offer.description` (regex) |
| Portal is ATS quality (lever/greenhouse/ashby) | +0.3 | `offer.portal` |

Score cap unchanged at 5.0.

### Tech skills constant

```python
_TECH_SKILLS = frozenset([
    # ML/DL
    "pytorch", "tensorflow", "sklearn", "scikit-learn", "xgboost", "lightgbm",
    "hugging face", "transformers", "fine-tuning", "rag", "langchain", "llm",
    "computer vision", "nlp", "mlops", "mlflow",
    # Infra / Deploy
    "docker", "kubernetes", "fastapi", "airflow", "spark", "aws", "gcp", "azure",
    "postgresql", "mongodb", "redis",
    # Languages
    "python", "sql", "rust", "typescript",
    # Domains
    "vector search", "embedding", "retrieval", "generative ai",
])
```

### Regex patterns

```python
_EXP_RE = re.compile(r"(\d+)\s*(?:à\s*\d+\s*)?ans?\s+d.expérience", re.IGNORECASE)
_CDI_RE = re.compile(r"\bCDI\b", re.IGNORECASE)
_SALARY_RE = re.compile(r"(\d{2,3})\s*[kK€]|\b(\d{4,6})\s*€")
```

### Company normalization

Strip noisy suffixes before comparing against `target_companies`:

```python
_COMPANY_NOISE = re.compile(
    r"\b(france|group|groupe|sas|s\.a\.s|inc|ltd|gmbh|f/h|h/f|sa|spa)\b",
    re.IGNORECASE,
)

def _normalize_company(name: str) -> str:
    return _COMPANY_NOISE.sub("", name).strip().lower()
```

Applied to both the scraped company name and to each entry in `target_companies` at scoring time.

### Quality portals constant

```python
_QUALITY_PORTALS = frozenset(["lever", "greenhouse", "ashby"])
```

### Defensive defaults (when settings keys are missing)

| Key | Default |
|-----|---------|
| `search.experience_max_years` | 3 |
| `scoring.target_salary_min` | 0 |
| `scoring.target_salary_max` | 999_999 |

### Signal behavior on missing data

- Empty description → all description signals return 0, no exception
- No regex match → signal skipped (no penalty)
- `offer.portal` not in `_QUALITY_PORTALS` → no bonus, no penalty

---

## 2. Recalibrated `score_to_grade()` — `scripts/import_offers.py`

| Grade | Old threshold | New threshold |
|-------|--------------|--------------|
| A | ≥ 4.5 | ≥ 4.0 |
| B | ≥ 4.0 | ≥ 3.0 |
| C | ≥ 3.5 | ≥ 2.0 |
| D | ≥ 3.0 | ≥ 1.0 |
| F | < 3.0 | < 1.0 |

Rationale: with new signals, a typical relevant offer scores 2.0–3.5. Grade F now means truly irrelevant (0 signals matched at all).

---

## 3. Migration script — `scripts/rescore.py`

### Purpose

Rescore all existing DB offers using the new `score_offer()` and update `score_value` + `score_grade` in place. Idempotent.

### Missing data handling for DB offers

The DB does not store `portal` or `location`. For migration:
- **`portal`**: inferred from `offer_url` using substring matching:
  - contains `lever.co` → "lever"
  - contains `greenhouse.io` → "greenhouse"
  - contains `ashby.com` → "ashby"
  - otherwise → "unknown" (no ATS bonus)
- **`location`**: not available retrospectively → defaults to `""` (no Paris bonus, no penalty)
- **`description`**: available in DB → all description signals work

### CLI interface

```bash
python -m scripts.rescore                  # rescore + update DB in place
python -m scripts.rescore --dry-run        # print changes without writing
python -m scripts.rescore --db PATH        # alternative DB path
```

### Dry-run output format

```
[DRY RUN] 196 offers to rescore
  id=12  DATATORII / Lead AI Engineer F/H       : F/1.0 → C/2.5
  id=45  Mistral AI / AI Engineer Product        : F/2.0 → B/3.3
  ...
Summary: F→A: 0, F→B: 8, F→C: 34, F→D: 71, F→F: 56, unchanged: 27
```

### Implementation

Reads all offers from DB, reconstructs a minimal `RawOffer` for each (title, company, description, portal inferred from url), calls `score_offer(offer, settings)`, compares new vs old grade, batches `UPDATE` statements, commits once.

---

## 4. Testing

### `tests/test_pre_filter.py` — new `TestNewSignals` class

| Test | Assertion |
|------|-----------|
| `test_tech_skills_in_description` | 5 skills in desc → score += 0.5 |
| `test_tech_skills_capped_at_1` | 15 skills in desc → bonus capped at +1.0 |
| `test_experience_under_threshold` | "2 ans d'expérience" with max=3 → +0.5 |
| `test_experience_over_threshold` | "5 ans d'expérience" with max=3 → no bonus |
| `test_experience_no_match` | No exp mention → no penalty |
| `test_cdi_in_description` | "CDI" in desc → +0.3 |
| `test_salary_in_range` | "45k€" with target 40k–55k → +0.3 |
| `test_salary_out_of_range` | "80k€" → no bonus |
| `test_company_normalization` | "CAPGEMINI ENGINEERING FRANCE" matches "Capgemini Engineering" |
| `test_ats_portal_bonus` | portal="lever" → +0.3 |
| `test_portal_apec_no_bonus` | portal="apec" → no bonus |

### `tests/test_rescore.py` — new file

| Test | Assertion |
|------|-----------|
| `test_dry_run_no_db_changes` | DB unchanged after `--dry-run` |
| `test_rescore_updates_grades` | F offer with rich desc → grade updated in DB |
| `test_rescore_idempotent` | Two successive runs → same result |
| `test_portal_inferred_from_url` | URL containing `lever.co` → portal="lever" |

### `tests/test_import_offers.py` — additional `score_to_grade` cases

5 new assertions for recalibrated thresholds: 4.0→A, 3.0→B, 2.0→C, 1.0→D, 0.9→F.

---

## 5. Out of scope

- LLM-based scoring
- Storing `portal` or `location` as new DB columns
- Dashboard UI changes (grade colors and filters work unchanged)
- Changing the `consider` threshold in `pre_filter()` (stays at 1.0)
