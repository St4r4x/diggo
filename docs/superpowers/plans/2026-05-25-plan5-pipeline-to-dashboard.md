# Plan 5 — Pipeline → Dashboard Glue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the loop between the Python scan pipeline and the Go dashboard by adding a script that runs the full pipeline and inserts new offers into the tracker SQLite database, plus a `run_daily.sh` that chains the whole thing.

**Architecture:** `scripts/import_offers.py` runs the existing scan→dedup→pre_filter pipeline and writes `RawOffer` rows directly into `dashboard/data/applications.db` using Python's `sqlite3` stdlib (same file the Go dashboard reads). Dedup against existing rows by `offer_url`. `run_daily.sh` chains `daily_report.py` then `import_offers.py` in one command.

**Tech Stack:** Python 3, sqlite3 (stdlib), asyncio, existing `scripts/` pipeline modules, bash

---

## Key reference: DB schema (must match Go's db.go exactly)

```sql
CREATE TABLE IF NOT EXISTS applications (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    company            TEXT    NOT NULL,
    role               TEXT    NOT NULL,
    offer_url          TEXT    NOT NULL DEFAULT '',
    detection_date     TEXT    NOT NULL,
    score_grade        TEXT    NOT NULL DEFAULT '',
    score_value        REAL    NOT NULL DEFAULT 0.0,
    status             TEXT    NOT NULL DEFAULT 'À envoyer',
    send_date          TEXT,
    contacts           TEXT    NOT NULL DEFAULT '',
    notes              TEXT    NOT NULL DEFAULT '',
    cv_path            TEXT    NOT NULL DEFAULT '',
    cover_letter_path  TEXT    NOT NULL DEFAULT '',
    follow_up_date     TEXT
)
```

## RawOffer → Application field mapping

| RawOffer field | DB column | Notes |
|---|---|---|
| `company` | `company` | direct |
| `title` | `role` | direct |
| `url` | `offer_url` | direct |
| `date_posted` or `date.today()` | `detection_date` | ISO format `YYYY-MM-DD` |
| derived from `score` | `score_grade` | A≥4.5, B≥4.0, C≥3.5, D≥3.0, F<3.0 |
| `score` | `score_value` | direct |
| hardcoded | `status` | always `"À envoyer"` |
| all other columns | `''` / `NULL` | left blank for user to fill |

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/import_offers.py` | Create | `score_to_grade`, `existing_urls`, `insert_offer`, `import_offers`, `main` CLI |
| `tests/test_import_offers.py` | Create | Unit tests for all pure functions + `import_offers` with tmp SQLite |
| `run_daily.sh` | Create | Bash script chaining `daily_report.py` + `import_offers.py` |

---

### Task 1: TDD — scripts/import_offers.py

**Files:**
- Create: `tests/test_import_offers.py`
- Create: `scripts/import_offers.py`

Venv is at `.venv/` — always use `.venv/bin/pytest` and `.venv/bin/python`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_import_offers.py`:

```python
"""Tests for import_offers: score_to_grade, existing_urls, insert_offer, import_offers."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from scripts.import_offers import (
    existing_urls,
    import_offers,
    insert_offer,
    score_to_grade,
)
from scripts.models import RawOffer

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS applications (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    company            TEXT    NOT NULL,
    role               TEXT    NOT NULL,
    offer_url          TEXT    NOT NULL DEFAULT '',
    detection_date     TEXT    NOT NULL,
    score_grade        TEXT    NOT NULL DEFAULT '',
    score_value        REAL    NOT NULL DEFAULT 0.0,
    status             TEXT    NOT NULL DEFAULT 'À envoyer',
    send_date          TEXT,
    contacts           TEXT    NOT NULL DEFAULT '',
    notes              TEXT    NOT NULL DEFAULT '',
    cv_path            TEXT    NOT NULL DEFAULT '',
    cover_letter_path  TEXT    NOT NULL DEFAULT '',
    follow_up_date     TEXT
)
"""


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(_CREATE_TABLE_SQL)
    return conn


class TestScoreToGrade:
    def test_a_at_4_5(self) -> None:
        assert score_to_grade(4.5) == "A"

    def test_a_at_5_0(self) -> None:
        assert score_to_grade(5.0) == "A"

    def test_b_at_4_0(self) -> None:
        assert score_to_grade(4.0) == "B"

    def test_b_at_4_4(self) -> None:
        assert score_to_grade(4.4) == "B"

    def test_c_at_3_5(self) -> None:
        assert score_to_grade(3.5) == "C"

    def test_d_at_3_0(self) -> None:
        assert score_to_grade(3.0) == "D"

    def test_f_below_3_0(self) -> None:
        assert score_to_grade(2.9) == "F"

    def test_f_at_zero(self) -> None:
        assert score_to_grade(0.0) == "F"


class TestExistingUrls:
    def test_empty_db_returns_empty_set(self) -> None:
        conn = _make_conn()
        assert existing_urls(conn) == set()

    def test_returns_url_from_row(self) -> None:
        conn = _make_conn()
        conn.execute(
            "INSERT INTO applications (company, role, offer_url, detection_date) VALUES (?, ?, ?, ?)",
            ("Acme", "Dev", "https://example.com/1", "2026-05-25"),
        )
        assert "https://example.com/1" in existing_urls(conn)

    def test_ignores_empty_url_rows(self) -> None:
        conn = _make_conn()
        conn.execute(
            "INSERT INTO applications (company, role, offer_url, detection_date) VALUES (?, ?, ?, ?)",
            ("Acme", "Dev", "", "2026-05-25"),
        )
        assert existing_urls(conn) == set()


class TestInsertOffer:
    def test_inserts_correct_fields(self) -> None:
        conn = _make_conn()
        offer = RawOffer(
            title="AI Engineer",
            company="Mistral AI",
            url="https://wttj.co/jobs/123",
            portal="wtfj",
            location="Paris",
            date_posted=date(2026, 5, 20),
            score=4.2,
        )
        insert_offer(conn, offer)
        row = conn.execute(
            "SELECT company, role, offer_url, detection_date, score_grade, score_value, status FROM applications"
        ).fetchone()
        assert row[0] == "Mistral AI"
        assert row[1] == "AI Engineer"
        assert row[2] == "https://wttj.co/jobs/123"
        assert row[3] == "2026-05-20"
        assert row[4] == "B"
        assert abs(row[5] - 4.2) < 0.001
        assert row[6] == "À envoyer"

    def test_uses_today_when_date_posted_is_none(self) -> None:
        conn = _make_conn()
        offer = RawOffer(title="Dev", company="Co", url="https://x.com/1", portal="p")
        insert_offer(conn, offer)
        row = conn.execute("SELECT detection_date FROM applications").fetchone()
        assert row[0] == date.today().isoformat()


class TestImportOffers:
    def test_inserts_new_offers(self, tmp_path) -> None:
        db_path = tmp_path / "test.db"
        offers = [
            RawOffer(title="AI Engineer", company="Acme", url="https://x.com/1", portal="p", score=4.0),
            RawOffer(title="ML Engineer", company="Beta", url="https://x.com/2", portal="p", score=3.5),
        ]
        inserted, skipped = import_offers(offers, db_path)
        assert inserted == 2
        assert skipped == 0

    def test_skips_duplicate_url_on_second_run(self, tmp_path) -> None:
        db_path = tmp_path / "test.db"
        offer = RawOffer(title="AI Engineer", company="Acme", url="https://x.com/1", portal="p", score=4.0)
        import_offers([offer], db_path)
        inserted, skipped = import_offers([offer], db_path)
        assert inserted == 0
        assert skipped == 1

    def test_empty_url_offers_always_inserted(self, tmp_path) -> None:
        db_path = tmp_path / "test.db"
        offer = RawOffer(title="AI Engineer", company="Acme", url="", portal="p", score=4.0)
        import_offers([offer], db_path)
        inserted, skipped = import_offers([offer], db_path)
        assert inserted == 1
        assert skipped == 0

    def test_creates_db_file_if_missing(self, tmp_path) -> None:
        db_path = tmp_path / "subdir" / "new.db"
        assert not db_path.exists()
        import_offers([], db_path)
        assert db_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/test_import_offers.py -v
```

Expected: `ImportError: cannot import name 'score_to_grade' from 'scripts.import_offers'`

- [ ] **Step 3: Implement scripts/import_offers.py**

Create `scripts/import_offers.py`:

```python
"""Import pipeline offers into the application tracker SQLite DB.

Runs the full scan→dedup→pre_filter pipeline and inserts new offers
into dashboard/data/applications.db as 'À envoyer' applications.
Offers already present (matched by non-empty offer_url) are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
from datetime import date
from pathlib import Path

from scripts.dedup import deduplicate
from scripts.models import RawOffer
from scripts.pre_filter import load_settings, pre_filter
from scripts.scan_portals import list_portal_ids, run_scan

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent / "dashboard" / "data" / "applications.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS applications (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    company            TEXT    NOT NULL,
    role               TEXT    NOT NULL,
    offer_url          TEXT    NOT NULL DEFAULT '',
    detection_date     TEXT    NOT NULL,
    score_grade        TEXT    NOT NULL DEFAULT '',
    score_value        REAL    NOT NULL DEFAULT 0.0,
    status             TEXT    NOT NULL DEFAULT 'À envoyer',
    send_date          TEXT,
    contacts           TEXT    NOT NULL DEFAULT '',
    notes              TEXT    NOT NULL DEFAULT '',
    cv_path            TEXT    NOT NULL DEFAULT '',
    cover_letter_path  TEXT    NOT NULL DEFAULT '',
    follow_up_date     TEXT
)
"""


def score_to_grade(score: float) -> str:
    if score >= 4.5:
        return "A"
    if score >= 4.0:
        return "B"
    if score >= 3.5:
        return "C"
    if score >= 3.0:
        return "D"
    return "F"


def existing_urls(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT offer_url FROM applications WHERE offer_url != ''"
    ).fetchall()
    return {row[0] for row in rows}


def insert_offer(conn: sqlite3.Connection, offer: RawOffer) -> None:
    detection = (
        offer.date_posted.isoformat() if offer.date_posted else date.today().isoformat()
    )
    conn.execute(
        """INSERT INTO applications
           (company, role, offer_url, detection_date, score_grade, score_value,
            status, send_date, contacts, notes, cv_path, cover_letter_path, follow_up_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, NULL, '', '', '', '', NULL)""",
        (
            offer.company,
            offer.title,
            offer.url,
            detection,
            score_to_grade(offer.score),
            offer.score,
            "À envoyer",
        ),
    )


def import_offers(offers: list[RawOffer], db_path: Path) -> tuple[int, int]:
    """Insert new offers into DB. Returns (inserted, skipped)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_CREATE_TABLE_SQL)
        urls = existing_urls(conn)
        inserted = 0
        skipped = 0
        for offer in offers:
            if offer.url and offer.url in urls:
                skipped += 1
                logger.debug("Skip (exists): %s @ %s", offer.title, offer.company)
            else:
                insert_offer(conn, offer)
                if offer.url:
                    urls.add(offer.url)
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted, skipped


async def _run_pipeline(settings: dict) -> list[RawOffer]:
    keyword_list: list[str] = settings.get("search", {}).get("keywords", ["AI Engineer"])
    keywords = keyword_list[0] if keyword_list else "AI Engineer"
    location: str = settings.get("search", {}).get("location", "Paris")
    portal_ids = list_portal_ids()
    logger.info(
        "Scanning %d portals for '%s' in %s", len(portal_ids), keywords, location
    )
    raw = await run_scan(portal_ids, keywords=keywords, location=location)
    logger.info("Scraped %d raw offers", len(raw))
    deduped = deduplicate(raw)
    logger.info("After dedup: %d offers", len(deduped))
    filtered = pre_filter(deduped, settings)
    logger.info("After pre-filter: %d offers", len(filtered))
    return filtered


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Import pipeline offers into the application tracker DB"
    )
    parser.add_argument(
        "--db", default=str(_DEFAULT_DB), metavar="PATH", help="Path to SQLite DB"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print offers without inserting into DB",
    )
    args = parser.parse_args()

    settings = load_settings()
    offers = asyncio.run(_run_pipeline(settings))
    logger.info("Pipeline produced %d offers", len(offers))

    if args.dry_run:
        for o in offers:
            grade = score_to_grade(o.score)
            print(f"[{grade}/{o.score:.1f}] {o.title} @ {o.company} — {o.url}")
        print(f"\nTotal: {len(offers)} offers (dry run, nothing inserted)")
        return

    inserted, skipped = import_offers(offers, Path(args.db))
    print(f"Imported {inserted} new offers, skipped {skipped} already present")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/test_import_offers.py -v
```

Expected:
```
PASSED tests/test_import_offers.py::TestScoreToGrade::test_a_at_4_5
PASSED tests/test_import_offers.py::TestScoreToGrade::test_a_at_5_0
PASSED tests/test_import_offers.py::TestScoreToGrade::test_b_at_4_0
PASSED tests/test_import_offers.py::TestScoreToGrade::test_b_at_4_4
PASSED tests/test_import_offers.py::TestScoreToGrade::test_c_at_3_5
PASSED tests/test_import_offers.py::TestScoreToGrade::test_d_at_3_0
PASSED tests/test_import_offers.py::TestScoreToGrade::test_f_below_3_0
PASSED tests/test_import_offers.py::TestScoreToGrade::test_f_at_zero
PASSED tests/test_import_offers.py::TestExistingUrls::test_empty_db_returns_empty_set
PASSED tests/test_import_offers.py::TestExistingUrls::test_returns_url_from_row
PASSED tests/test_import_offers.py::TestExistingUrls::test_ignores_empty_url_rows
PASSED tests/test_import_offers.py::TestInsertOffer::test_inserts_correct_fields
PASSED tests/test_import_offers.py::TestInsertOffer::test_uses_today_when_date_posted_is_none
PASSED tests/test_import_offers.py::TestImportOffers::test_inserts_new_offers
PASSED tests/test_import_offers.py::TestImportOffers::test_skips_duplicate_url_on_second_run
PASSED tests/test_import_offers.py::TestImportOffers::test_empty_url_offers_always_inserted
PASSED tests/test_import_offers.py::TestImportOffers::test_creates_db_file_if_missing
17 passed
```

- [ ] **Step 5: Run the full test suite — no regressions**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/ -v
```

All previously passing 61 tests must still pass (total: 78).

- [ ] **Step 6: Commit**

```bash
git add scripts/import_offers.py tests/test_import_offers.py
git commit -m "feat: add import_offers pipeline-to-dashboard glue with TDD"
```

---

### Task 2: run_daily.sh + tag v0.5.0

**Files:**
- Create: `run_daily.sh`

- [ ] **Step 1: Create run_daily.sh**

Create `run_daily.sh` at the project root:

```bash
#!/usr/bin/env bash
# Daily job search pipeline: scan portals → generate report → import to dashboard
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATE=$(date +%Y-%m-%d)

echo "=== career-ops-fr daily run — $DATE ==="

echo "[1/2] Generating daily report..."
.venv/bin/python scripts/daily_report.py

echo "[2/2] Importing offers into dashboard DB..."
.venv/bin/python scripts/import_offers.py

echo "Done — open the dashboard to review new offers."
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x run_daily.sh
```

- [ ] **Step 3: Smoke-test --dry-run to verify the script is importable**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/python scripts/import_offers.py --dry-run 2>&1 | head -5
```

Expected: INFO log lines from the pipeline starting up (Playwright will time out on portals — that's fine for a dry-run smoke test; no errors from import_offers itself).

- [ ] **Step 4: Run the full test suite one final time**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/ -v
```

All 78 tests must pass.

- [ ] **Step 5: Commit**

```bash
git add run_daily.sh
git commit -m "feat: add run_daily.sh to chain scan, report, and import"
```

- [ ] **Step 6: Push and tag**

Check the remote name first:
```bash
git remote -v
```

Then push and tag:
```bash
git push github.com-personal HEAD:master
git tag v0.5.0 -m "Plan 5 complete: pipeline to dashboard glue"
git push github.com-personal v0.5.0
```

Expected: tag `v0.5.0` on `git@github.com-personal:St4r4x/career-ops-fr.git`.
