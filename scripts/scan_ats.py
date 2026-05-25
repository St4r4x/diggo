"""ATS Scanner: queries Greenhouse, Lever, and Ashby public JSON APIs.

No Playwright -- pure httpx async HTTP. Provider is auto-detected from
the careers_url pattern in config/ats_map.yaml.

Usage:
    python scripts/scan_ats.py
    python scripts/scan_ats.py --company "Mistral AI"
    python scripts/scan_ats.py --keywords "AI Engineer" "Machine Learning"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

import httpx
import yaml

from scripts.models import RawOffer

logger = logging.getLogger(__name__)

_DEFAULT_ATS_MAP = Path(__file__).parent.parent / "config" / "ats_map.yaml"
_TIMEOUT = 10.0


class GreenhouseProvider:
    id = "greenhouse"

    @staticmethod
    async def fetch(
        company_name: str, slug: str, client: httpx.AsyncClient
    ) -> list[RawOffer]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        try:
            resp = await client.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("[greenhouse/%s] Request failed: %s", slug, exc)
            return []
        jobs = resp.json().get("jobs", [])
        offers = []
        for j in jobs:
            title = j.get("title", "").strip()
            job_url = j.get("absolute_url", "").strip()
            location = (j.get("location") or {}).get("name", "").strip() or None
            if not title:
                continue
            offers.append(
                RawOffer(
                    title=title,
                    company=company_name,
                    url=job_url,
                    portal="greenhouse",
                    location=location,
                )
            )
        return offers


class LeverProvider:
    id = "lever"

    @staticmethod
    async def fetch(
        company_name: str, slug: str, client: httpx.AsyncClient
    ) -> list[RawOffer]:
        url = f"https://api.lever.co/v0/postings/{slug}"
        try:
            resp = await client.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("[lever/%s] Request failed: %s", slug, exc)
            return []
        jobs = resp.json()
        if not isinstance(jobs, list):
            return []
        offers = []
        for j in jobs:
            title = j.get("text", "").strip()
            job_url = j.get("hostedUrl", "").strip()
            location = (j.get("categories") or {}).get("location", "").strip() or None
            if not title:
                continue
            offers.append(
                RawOffer(
                    title=title,
                    company=company_name,
                    url=job_url,
                    portal="lever",
                    location=location,
                )
            )
        return offers


class AshbyProvider:
    id = "ashby"

    @staticmethod
    async def fetch(
        company_name: str, slug: str, client: httpx.AsyncClient
    ) -> list[RawOffer]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        try:
            resp = await client.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("[ashby/%s] Request failed: %s", slug, exc)
            return []
        jobs = resp.json().get("jobs", [])
        offers = []
        for j in jobs:
            title = j.get("title", "").strip()
            job_url = j.get("jobUrl", "").strip()
            location = (j.get("location") or "").strip() or None
            if not title:
                continue
            offers.append(
                RawOffer(
                    title=title,
                    company=company_name,
                    url=job_url,
                    portal="ashby",
                    location=location,
                )
            )
        return offers


_PROVIDER_PATTERNS: list[tuple[re.Pattern, type]] = [
    (re.compile(r"greenhouse\.io/([^/?#]+)"), GreenhouseProvider),
    (re.compile(r"jobs\.lever\.co/([^/?#]+)"), LeverProvider),
    (re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)"), AshbyProvider),
]


def resolve_provider(entry: dict) -> Optional[tuple[type, str]]:
    """Return (ProviderClass, slug) or None if URL is not recognised."""
    url = entry.get("careers_url", "")
    if not url:
        return None
    for pattern, provider_cls in _PROVIDER_PATTERNS:
        m = pattern.search(url)
        if m:
            return provider_cls, m.group(1)
    return None


def _load_ats_map(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, list) else []


async def scan_ats(
    ats_map_path: Path = _DEFAULT_ATS_MAP,
    *,
    company_filter: Optional[str] = None,
    keywords: Optional[list[str]] = None,
) -> list[RawOffer]:
    """Scan all companies in ats_map.yaml and return RawOffer list.

    company_filter: if set, only scan that company (case-insensitive match on name).
    keywords: if set, keep only offers whose title contains at least one keyword
              (case-insensitive substring match).
    """
    entries = _load_ats_map(ats_map_path)
    if company_filter:
        entries = [
            e for e in entries if e.get("name", "").lower() == company_filter.lower()
        ]

    all_offers: list[RawOffer] = []
    async with httpx.AsyncClient() as client:
        tasks = []
        meta = []
        for entry in entries:
            resolved = resolve_provider(entry)
            if resolved is None:
                logger.warning(
                    "[ats] Unknown provider for '%s' -- skipping", entry.get("name")
                )
                continue
            provider_cls, slug = resolved
            tasks.append(provider_cls.fetch(entry["name"], slug, client))
            meta.append(entry["name"])

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(meta, results):
            if isinstance(result, Exception):
                logger.error("[ats/%s] Fetch failed: %s", name, result)
            else:
                all_offers.extend(result)

    if keywords:
        kw_lower = [k.lower() for k in keywords]
        all_offers = [
            o for o in all_offers if any(kw in o.title.lower() for kw in kw_lower)
        ]

    logger.info("[ats] Total offers fetched: %d", len(all_offers))
    return all_offers


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Scan ATS job boards for target companies"
    )
    parser.add_argument(
        "--company", default=None, metavar="NAME", help="Filter to a single company"
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=None,
        metavar="KW",
        help="Only show offers matching these keywords (case-insensitive)",
    )
    args = parser.parse_args()

    offers = asyncio.run(scan_ats(company_filter=args.company, keywords=args.keywords))
    for o in offers:
        print(f"[{o.portal}] {o.title} @ {o.company} -- {o.url}")
    print(f"\nTotal: {len(offers)} offers")


if __name__ == "__main__":
    main()
