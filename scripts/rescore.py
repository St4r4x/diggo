"""Rescore all existing DB offers using the updated score_offer() function.

Usage:
    python -m scripts.rescore [--dry-run] [--db PATH]
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path

from scripts.import_offers import score_to_grade
from scripts.models import RawOffer
from scripts.pre_filter import load_settings, score_offer

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent / "dashboard" / "data" / "applications.db"


def _infer_portal(url: str) -> str:
    url_lower = url.lower()
    if "lever.co" in url_lower:
        return "lever"
    if "greenhouse.io" in url_lower:
        return "greenhouse"
    if "ashby.com" in url_lower:
        return "ashby"
    return "unknown"


def rescore(
    conn: sqlite3.Connection, dry_run: bool = False, user_id: str | None = None
) -> dict:
    settings = load_settings(user_id=user_id)
    rows = conn.execute(
        "SELECT id, company, role, offer_url, score_grade, score_value, description "
        "FROM applications"
    ).fetchall()

    updates: list[tuple[str, float, int]] = []
    summary: dict[str, int] = {"total": len(rows), "changed": 0}

    for row in rows:
        id_, company, role, offer_url, old_grade, old_score, description = row
        portal = _infer_portal(offer_url or "")
        offer = RawOffer(
            title=role or "",
            company=company or "",
            url=offer_url or "",
            portal=portal,
            location="",
            description=description or "",
        )
        new_score, _ = score_offer(offer, settings)
        new_grade = score_to_grade(new_score)
        if new_grade != old_grade or abs(new_score - old_score) > 0.001:
            updates.append((new_grade, new_score, id_))
            summary["changed"] += 1
            logger.info(
                "  id=%-4d  %-40s : %s/%.1f -> %s/%.1f",
                id_,
                f"{company} / {role}"[:40],
                old_grade,
                old_score,
                new_grade,
                new_score,
            )

    if not dry_run and updates:
        conn.executemany(
            "UPDATE applications SET score_grade = ?, score_value = ? WHERE id = ?",
            updates,
        )
        conn.commit()

    return summary


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Rescore all DB offers with updated scorer"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print changes without writing"
    )
    parser.add_argument("--db", default=str(_DEFAULT_DB), metavar="PATH")
    parser.add_argument(
        "--user-id",
        default=None,
        metavar="UUID",
        help="Load settings from DB for this user",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    prefix = "[DRY RUN] " if args.dry_run else ""
    logger.info("%sRescoring offers in %s", prefix, args.db)

    stats = rescore(conn, dry_run=args.dry_run, user_id=args.user_id)
    conn.close()

    action = "Would update" if args.dry_run else "Updated"
    print(f"\n{prefix}Total: {stats['total']} offers -- {action}: {stats['changed']}")


if __name__ == "__main__":
    main()
