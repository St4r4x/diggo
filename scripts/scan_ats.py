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
from html import unescape
from pathlib import Path
from typing import Optional

import httpx
import yaml

from scripts.models import RawOffer

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    return " ".join(unescape(_HTML_TAG_RE.sub(" ", html)).split())


_DEFAULT_ATS_MAP = Path(__file__).parent.parent / "config" / "ats_map.yaml"
_TIMEOUT = 10.0
_RETRY_BACKOFF = [1.0, 2.0, 4.0]  # seconds between attempts
_RETRY_ATTEMPTS = len(_RETRY_BACKOFF)


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout: float = _TIMEOUT,
) -> httpx.Response:
    """GET url with up to _RETRY_ATTEMPTS retries and exponential backoff.

    4xx errors (except 429) are not retried — they are definitive failures.
    """
    last_exc: Exception | None = None
    for attempt, backoff in enumerate(_RETRY_BACKOFF, start=1):
        try:
            resp = await client.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            if (
                isinstance(exc, httpx.HTTPStatusError)
                and exc.response.status_code < 500
                and exc.response.status_code != 429
            ):
                raise
            last_exc = exc
            if attempt < _RETRY_ATTEMPTS:
                logger.warning(
                    "Attempt %d/%d failed for %s: %s — retrying in %.1fs",
                    attempt,
                    _RETRY_ATTEMPTS,
                    url,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
    assert last_exc is not None
    raise last_exc


class GreenhouseProvider:
    id = "greenhouse"

    @staticmethod
    async def fetch(
        company_name: str, slug: str, client: httpx.AsyncClient
    ) -> list[RawOffer]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        try:
            resp = await _fetch_with_retry(client, url)
        except Exception as exc:
            logger.warning(
                "[greenhouse/%s] Request failed after retries: %s", slug, exc
            )
            return []
        jobs = resp.json().get("jobs", [])

        async def _fetch_gh_job(j: dict) -> Optional[RawOffer]:
            title = j.get("title", "").strip()
            job_url = j.get("absolute_url", "").strip()
            location = (j.get("location") or {}).get("name", "").strip() or None
            job_id = j.get("id")
            if not title:
                return None
            description = ""
            if job_id:
                detail_url = (
                    f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}"
                )
                try:
                    detail_resp = await _fetch_with_retry(client, detail_url)
                    description = _strip_html(detail_resp.json().get("content", ""))[
                        :8000
                    ]
                except Exception:
                    pass
            return RawOffer(
                title=title,
                company=company_name,
                url=job_url,
                portal="greenhouse",
                location=location,
                description=description,
            )

        results = await asyncio.gather(
            *[_fetch_gh_job(j) for j in jobs], return_exceptions=True
        )
        return [r for r in results if isinstance(r, RawOffer)]


class LeverProvider:
    id = "lever"

    @staticmethod
    async def fetch(
        company_name: str, slug: str, client: httpx.AsyncClient
    ) -> list[RawOffer]:
        url = f"https://api.lever.co/v0/postings/{slug}"
        try:
            resp = await _fetch_with_retry(client, url)
        except Exception as exc:
            logger.warning("[lever/%s] Request failed after retries: %s", slug, exc)
            return []
        jobs = resp.json()
        if not isinstance(jobs, list):
            return []

        async def _fetch_lever_job(j: dict) -> Optional[RawOffer]:
            title = j.get("text", "").strip()
            job_url = j.get("hostedUrl", "").strip()
            location = (j.get("categories") or {}).get("location", "").strip() or None
            if not title:
                return None
            description = ""
            posting_id = job_url.rstrip("/").rsplit("/", 1)[-1] if job_url else ""
            if posting_id:
                detail_url = f"https://api.lever.co/v0/postings/{slug}/{posting_id}"
                try:
                    detail_resp = await _fetch_with_retry(client, detail_url)
                    detail = detail_resp.json()
                    description = (
                        detail.get("descriptionPlain")
                        or detail.get("description")
                        or ""
                    )[:8000]
                except Exception:
                    pass
            return RawOffer(
                title=title,
                company=company_name,
                url=job_url,
                portal="lever",
                location=location,
                description=description,
            )

        results = await asyncio.gather(
            *[_fetch_lever_job(j) for j in jobs], return_exceptions=True
        )
        return [r for r in results if isinstance(r, RawOffer)]


class AshbyProvider:
    id = "ashby"

    @staticmethod
    async def fetch(
        company_name: str, slug: str, client: httpx.AsyncClient
    ) -> list[RawOffer]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        try:
            resp = await _fetch_with_retry(client, url)
        except Exception as exc:
            logger.warning("[ashby/%s] Request failed after retries: %s", slug, exc)
            return []
        jobs = resp.json().get("jobs", [])
        offers = []
        for j in jobs:
            title = j.get("title", "").strip()
            job_url = j.get("jobUrl", "").strip()
            location = (j.get("location") or "").strip() or None
            if not title:
                continue
            description = (j.get("descriptionBody") or j.get("descriptionPlain") or "")[
                :8000
            ]
            offers.append(
                RawOffer(
                    title=title,
                    company=company_name,
                    url=job_url,
                    portal="ashby",
                    location=location,
                    description=description,
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
    user_id: Optional[str] = None,
) -> list[RawOffer]:
    """Scan all companies in ats_map.yaml and return RawOffer list.

    company_filter: if set, only scan that company (case-insensitive match on name).
    keywords: if set, keep only offers whose title contains at least one keyword
              (case-insensitive substring match).
    user_id: if set, load ATS targets from DB instead of the YAML file.
    """
    if user_id is not None:
        try:
            import os
            import sys

            import psycopg2

            sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))
            import user_data as _ud

            db_url = os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
            )
            conn = psycopg2.connect(db_url)
            try:
                entries = _ud.get_ats_targets(conn, user_id)
            finally:
                conn.close()
        except Exception as e:
            logger.warning("DB ATS targets load failed, falling back to file: %s", e)
            entries = _load_ats_map(ats_map_path)
    else:
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
