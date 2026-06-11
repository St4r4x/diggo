# Mode: rescore-offers

Use this mode after changing `config/settings.yaml` to recompute scores for all existing offers.

## When to use

- After changing `scoring.target_salary_min` or `scoring.target_salary_max`
- After adding or removing companies from `target_companies`
- After changing `search.keywords`
- When scores feel stale or miscalibrated

## How to run

```bash
# Dry run — preview changes without writing to DB
python scripts/rescore.py --dry-run

# Apply rescoring
python scripts/rescore.py

# Rescore a specific DB file
python scripts/rescore.py --db /path/to/applications.db
```

## What it does

1. Reads `config/settings.yaml` for current scoring config
2. Fetches all offers from the DB
3. Re-runs `score_offer()` from `scripts/pre_filter.py` on each offer's description
4. Updates `score_value` and `score_grade` in the DB
5. Prints a summary of grade distribution changes

## Expected output

```
Rescored 156 offers:
  A: 12 → 15 (+3)
  B: 34 → 31 (−3)
  C: 67 → 70 (+3)
  D: 30 → 28 (−2)
  F: 13 → 12 (−1)
```
