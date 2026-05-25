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
from scripts.scan_ats import scan_ats
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
    search_cfg: dict = settings.get("search", {})
    keyword_list: list[str] = search_cfg.get("keywords", ["AI Engineer"])
    portal_queries: list[str] = search_cfg.get(
        "portal_queries", [keyword_list[0]] if keyword_list else ["AI Engineer"]
    )
    location: str = search_cfg.get("location", "Paris")
    portal_ids = list_portal_ids()
    logger.info(
        "Scanning %d portals with %d queries in %s",
        len(portal_ids),
        len(portal_queries),
        location,
    )
    portal_raw: list[RawOffer] = []
    for query in portal_queries:
        batch = await run_scan(portal_ids, keywords=query, location=location)
        logger.info("Query '%s': %d raw offers", query, len(batch))
        portal_raw.extend(batch)
    logger.info("Scraped %d raw offers from portals (before dedup)", len(portal_raw))
    ats_raw = await scan_ats(keywords=keyword_list)
    logger.info("Scraped %d raw offers from ATS", len(ats_raw))
    raw = portal_raw + ats_raw
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
