"""Daily report generator.

Runs the full pipeline (scan → dedup → pre_filter) and writes a Markdown
report to reports/daily-YYYY-MM-DD.md.

Usage:
    python scripts/daily_report.py
    python scripts/daily_report.py --date 2026-05-25
    python scripts/daily_report.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date
from pathlib import Path

from scripts.dedup import deduplicate
from scripts.models import RawOffer
from scripts.pre_filter import load_settings, pre_filter
from scripts.scan_portals import list_portal_ids, run_scan

logger = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).parent.parent / "reports"
_RECOMMEND_THRESHOLD = 4.0
_CONSIDER_THRESHOLD = 3.0


def report_path(report_date: date) -> Path:
    """Return the Path where the daily report will be written."""
    return _REPORTS_DIR / f"daily-{report_date.isoformat()}.md"


def render_report(offers: list[RawOffer], *, report_date: date) -> str:
    """Render the daily report as a Markdown string."""
    recommend = sorted(
        [o for o in offers if o.score >= _RECOMMEND_THRESHOLD],
        key=lambda o: o.score,
        reverse=True,
    )
    consider = sorted(
        [o for o in offers if _CONSIDER_THRESHOLD <= o.score < _RECOMMEND_THRESHOLD],
        key=lambda o: o.score,
        reverse=True,
    )

    lines: list[str] = [
        f"# Daily Report — {report_date.isoformat()}",
        "",
        f"**Total offers:** {len(offers)}  |  "
        f"**Recommend:** {len(recommend)}  |  "
        f"**Consider:** {len(consider)}",
        "",
        "---",
        "",
    ]

    if not offers:
        lines.append("_No offers matched the pre-filter threshold today._")
        return "\n".join(lines)

    lines.append(f"## Recommend ({len(recommend)})")
    lines.append("")
    if recommend:
        for offer in recommend:
            lines.extend(_render_offer_entry(offer))
    else:
        lines.append("_No offers in this category._")
        lines.append("")

    lines.append(f"## Consider ({len(consider)})")
    lines.append("")
    if consider:
        for offer in consider:
            lines.extend(_render_offer_entry(offer))
    else:
        lines.append("_No offers in this category._")
        lines.append("")

    return "\n".join(lines)


def _render_offer_entry(offer: RawOffer) -> list[str]:
    date_str = offer.date_posted.isoformat() if offer.date_posted else "N/A"
    tags_str = ", ".join(offer.tags) if offer.tags else "—"
    location_str = offer.location or "N/A"

    return [
        f"### [{offer.title}]({offer.url})",
        f"- **Company:** {offer.company}",
        f"- **Portal:** `{offer.portal}`",
        f"- **Location:** {location_str}",
        f"- **Posted:** {date_str}",
        f"- **Score:** {offer.score:.1f} / 5.0",
        f"- **Tags:** {tags_str}",
        "",
    ]


async def _run_pipeline(settings: dict) -> list[RawOffer]:
    keywords: str = settings.get("search", {}).get("keywords", ["AI Engineer"])[0]
    location: str = settings.get("search", {}).get("location", "Paris")
    portal_ids = list_portal_ids()

    logger.info(
        "Starting scan of %d portals for '%s' in %s",
        len(portal_ids),
        keywords,
        location,
    )
    raw_offers = await run_scan(portal_ids, keywords=keywords, location=location)
    logger.info("Scraped %d raw offers", len(raw_offers))

    deduped = deduplicate(raw_offers)
    logger.info("After dedup: %d offers", len(deduped))

    filtered = pre_filter(deduped, settings)
    logger.info("After pre-filter: %d offers", len(filtered))

    return filtered


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="Generate daily job offers report")
    parser.add_argument("--date", metavar="YYYY-MM-DD", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report_date = date.fromisoformat(args.date) if args.date else date.today()
    settings = load_settings()

    offers = asyncio.run(_run_pipeline(settings))
    report_md = render_report(offers, report_date=report_date)

    if args.dry_run:
        print(report_md)
    else:
        path = report_path(report_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report_md, encoding="utf-8")
        print(f"Report written to {path}")
        print(f"Total: {len(offers)} offers")


if __name__ == "__main__":
    main()
