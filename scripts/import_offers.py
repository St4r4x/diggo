"""Import pipeline offers into the application tracker PostgreSQL DB.

Runs the full scan→dedup→pre_filter pipeline and inserts new offers
into the applications table as 'À envoyer' applications.
Offers already present (matched by non-empty offer_url) are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=False)

from scripts.dedup import deduplicate, normalize_offer_url
from scripts.description_parser import parse_description
from scripts.liveness import check_liveness
from scripts.models import RawOffer
from scripts.pre_filter import load_settings, pre_filter
from scripts.scan_ats import scan_ats
from scripts.scan_portals import list_portal_ids, run_scan

logger = logging.getLogger(__name__)

_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://career:career@localhost:5432/career"
)

_HOSTNAME_TO_PORTAL: dict[str, str] = {
    "www.apec.fr": "apec",
    "apec.fr": "apec",
    "jobs.lever.co": "lever",
    "api.lever.co": "lever",
    "job-boards.greenhouse.io": "greenhouse",
    "boards-api.greenhouse.io": "greenhouse",
    "jobs.ashbyhq.com": "ashby",
}


def infer_portal_from_url(url: str) -> str:
    if not url:
        return ""
    host = urlparse(url).hostname or ""
    return _HOSTNAME_TO_PORTAL.get(host, "")


def score_to_grade(score: float) -> str:
    if score >= 4.0:
        return "A"
    if score >= 3.0:
        return "B"
    if score >= 2.0:
        return "C"
    if score >= 1.0:
        return "D"
    return "F"


def existing_urls(conn: psycopg2.extensions.connection, user_id: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT offer_url, portal FROM applications"
            " WHERE offer_url != '' AND user_id = %s",
            (user_id,),
        )
        rows = cur.fetchall()
    return {normalize_offer_url(row[0], row[1]) for row in rows}


def insert_offer(
    conn: psycopg2.extensions.connection, offer: RawOffer, user_id: str
) -> None:
    detection = (
        offer.date_posted.isoformat() if offer.date_posted else date.today().isoformat()
    )
    portal = offer.portal or infer_portal_from_url(offer.url or "")
    parsed = offer.parsed_description or parse_description(offer.description, portal)
    description_json = parsed.to_json()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO applications"
            " (user_id, company, role, offer_url, detection_date, score_grade,"
            "  score_value, status, send_date, contacts, notes, cv_path,"
            "  cover_letter_path, follow_up_date, description, portal)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, '', '', '', '', NULL, %s, %s)",
            (
                user_id,
                offer.company,
                offer.title,
                offer.url,
                detection,
                score_to_grade(offer.score),
                offer.score,
                "À envoyer",
                description_json,
                portal,
            ),
        )


def import_offers(offers: list[RawOffer], user_id: str) -> tuple[int, int]:
    """Insert new offers for user_id. Returns (inserted, skipped)."""
    conn = psycopg2.connect(_DATABASE_URL)
    try:
        conn.autocommit = False
        urls = existing_urls(conn, user_id)
        inserted = 0
        skipped = 0
        for offer in offers:
            canonical = normalize_offer_url(offer.url or "", offer.portal)
            if canonical and canonical in urls:
                if offer.description:
                    description_json = parse_description(
                        offer.description, offer.portal
                    ).to_json()
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE applications SET description = %s"
                            " WHERE offer_url = %s AND description = '' AND user_id = %s",
                            (description_json, offer.url, user_id),
                        )
                skipped += 1
                logger.debug("Skip (exists): %s @ %s", offer.title, offer.company)
            else:
                insert_offer(conn, offer, user_id)
                if canonical:
                    urls.add(canonical)
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted, skipped


def import_offers_with_liveness(
    offers: list[RawOffer],
    user_id: str,
) -> tuple[int, int, int]:
    """Insert new offers for user_id, skipping expired ones. Returns (inserted, skipped, expired)."""
    conn = psycopg2.connect(_DATABASE_URL)
    try:
        conn.autocommit = False
        urls = existing_urls(conn, user_id)
        inserted = 0
        skipped = 0
        expired_count = 0
        for offer in offers:
            canonical = normalize_offer_url(offer.url or "", offer.portal)
            if canonical and canonical in urls:
                skipped += 1
                continue
            if offer.url:
                status, reason = check_liveness(offer.url)
                if status == "expired":
                    logger.info(
                        "Skip (expired %s): %s @ %s", reason, offer.title, offer.company
                    )
                    expired_count += 1
                    continue
            insert_offer(conn, offer, user_id)
            if canonical:
                urls.add(canonical)
            inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted, skipped, expired_count


def expire_stale_offers(user_id: str) -> int:
    """Check liveness of all 'À envoyer' offers for user_id and mark expired ones as 'Abandonnée'.

    Returns the number of offers marked as abandoned.
    """
    conn = psycopg2.connect(_DATABASE_URL)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, offer_url FROM applications"
                " WHERE status = 'À envoyer' AND offer_url != '' AND user_id = %s",
                (user_id,),
            )
            rows = cur.fetchall()
        abandoned = 0
        for row_id, url in rows:
            status, reason = check_liveness(url)
            if status == "expired":
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE applications SET status = 'Abandonnée' WHERE id = %s AND user_id = %s",
                        (row_id, user_id),
                    )
                logger.info("Expired (liveness %s): id=%d url=%s", reason, row_id, url)
                abandoned += 1
        conn.commit()
    finally:
        conn.close()
    return abandoned


async def _run_pipeline(
    settings: dict, *, skip_descriptions: bool = False, user_id: str | None = None
) -> list[RawOffer]:
    # settings.yaml nests these under "search"; DB-backed settings are flat
    search_cfg: dict = settings.get("search", settings)
    keyword_list: list[str] = search_cfg.get("keywords", ["AI Engineer"])
    location: str = search_cfg.get("location", "Paris")
    enabled_portals: list[str] = search_cfg.get("enabled_portals") or []
    portal_ids = list_portal_ids()
    if enabled_portals:
        portal_ids = [p for p in portal_ids if p in enabled_portals]
    logger.info(
        "Scanning %d portals with %d queries in %s",
        len(portal_ids),
        len(keyword_list),
        location,
    )
    portal_raw: list[RawOffer] = []
    batches = await asyncio.gather(
        *[run_scan(portal_ids, keywords=q, location=location) for q in keyword_list],
        return_exceptions=True,
    )
    for query, batch in zip(keyword_list, batches):
        if isinstance(batch, Exception):
            logger.error("Portal query '%s' failed: %s", query, batch)
        else:
            logger.info("Query '%s': %d raw offers", query, len(batch))
            portal_raw.extend(batch)
    logger.info("Scraped %d raw offers from portals (before dedup)", len(portal_raw))
    ats_raw = await scan_ats(keywords=keyword_list, user_id=user_id)
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
        "--user-id",
        required=True,
        metavar="UUID",
        help="Supabase user UUID to scope inserted offers",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print offers without inserting into DB",
    )
    parser.add_argument(
        "--check-liveness",
        action="store_true",
        help="Skip offers whose URL is expired before inserting",
    )
    args = parser.parse_args()

    settings = load_settings(user_id=args.user_id)
    offers = asyncio.run(_run_pipeline(settings, user_id=args.user_id))
    logger.info("Pipeline produced %d offers", len(offers))

    if args.dry_run:
        for o in offers:
            grade = score_to_grade(o.score)
            print(f"[{grade}/{o.score:.1f}] {o.title} @ {o.company} — {o.url}")
        print(f"\nTotal: {len(offers)} offers (dry run, nothing inserted)")
        return

    if args.check_liveness:
        inserted, skipped, expired = import_offers_with_liveness(offers, args.user_id)
        print(
            f"Imported {inserted} new offers, skipped {skipped} existing, "
            f"{expired} expired"
        )
    else:
        inserted, skipped = import_offers(offers, args.user_id)
        print(f"Imported {inserted} new offers, skipped {skipped} already present")


if __name__ == "__main__":
    main()
