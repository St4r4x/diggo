"""Portal scanner: loads portal configs and scrapes job offers via Playwright."""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote_plus, urlencode, urljoin, urlparse, urlunparse

import yaml

from scripts.models import RawOffer

logger = logging.getLogger(__name__)

_PORTALS_DIR = Path(__file__).parent.parent / "portals" / "fr"

_FRENCH_MONTHS: dict[str, int] = {
    "janvier": 1,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
}


def parse_date_string(raw: str) -> Optional[date]:
    if not raw or not raw.strip():
        return None
    cleaned = raw.strip()
    lower = cleaned.lower()
    if lower in ("aujourd'hui", "today", "aujourd"):
        return date.today()
    if lower in ("hier", "yesterday"):
        return date.today() - timedelta(days=1)
    iso_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", cleaned)
    if iso_match:
        try:
            return date(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3)),
            )
        except ValueError:
            return None
    french_match = re.fullmatch(
        r"(\d{1,2})\s+([a-záéèêîôùûüç]+)\s+(\d{4})", cleaned, re.IGNORECASE
    )
    if french_match:
        day = int(french_match.group(1))
        month_name = french_match.group(2).lower()
        year = int(french_match.group(3))
        month = _FRENCH_MONTHS.get(month_name)
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                return None
    return None


def build_search_url(template: str, *, keywords: str, location: str) -> str:
    return template.format(
        keywords=quote_plus(keywords),
        location=quote_plus(location),
    )


def extract_offer_from_card_data(
    card_data: dict[str, str],
    *,
    portal_id: str,
    base_url: str = "",
) -> Optional[RawOffer]:
    title = card_data.get("title", "").strip()
    company = card_data.get("company", "").strip()
    raw_url = card_data.get("url", "").strip()
    location = card_data.get("location", "").strip() or None
    raw_date = card_data.get("date", "").strip()

    if not title:
        return None

    if raw_url and not raw_url.startswith("http") and base_url:
        raw_url = urljoin(base_url, raw_url)

    return RawOffer(
        title=title,
        company=company,
        url=raw_url,
        portal=portal_id,
        location=location,
        date_posted=parse_date_string(raw_date),
    )


def load_portal_config(portal_id: str) -> dict:
    path = _PORTALS_DIR / f"{portal_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Portal config not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def list_portal_ids() -> list[str]:
    return sorted(p.stem for p in _PORTALS_DIR.glob("*.yaml"))


async def _card_text(card, sel: str) -> str:
    if not sel:
        return ""
    try:
        el = await card.query_selector(sel)
        return (await el.inner_text()).strip() if el else ""
    except Exception:
        return ""


async def _card_href(card, sel: str) -> str:
    if not sel:
        return ""
    try:
        el = await card.query_selector(sel)
        return (await el.get_attribute("href") or "").strip() if el else ""
    except Exception:
        return ""


async def _card_datetime(card, sel: str) -> str:
    if not sel:
        return ""
    try:
        el = await card.query_selector(sel)
        if el:
            dt = await el.get_attribute("datetime")
            if dt:
                return dt.strip()
            return (await el.inner_text()).strip()
        return ""
    except Exception:
        return ""


async def scrape_portal(portal_id: str, keywords: str, location: str) -> list[RawOffer]:
    from playwright.async_api import async_playwright

    config = load_portal_config(portal_id)
    selectors = config["selectors"]
    pagination = config["pagination"]
    base_url = config["base_url"]
    pagination_type = pagination["type"]
    page_size = pagination.get("page_size", 10)
    offers: list[RawOffer] = []

    async with async_playwright() as pw:
        browser = await pw.firefox.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"
                )
            )
            page = await context.new_page()
            url = build_search_url(
                config["search_url_template"], keywords=keywords, location=location
            )
            current_page = 0
            max_pages = pagination.get("max_pages", 3)

            while current_page < max_pages:
                # next_button portals: after page 0, navigation is done by clicking — skip goto
                if not (current_page > 0 and pagination_type == "next_button"):
                    logger.info(
                        "[%s] Navigating to page %d: %s",
                        portal_id,
                        current_page + 1,
                        url,
                    )
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=30_000)
                    except Exception as exc:
                        logger.warning("[%s] Navigation error: %s", portal_id, exc)
                        break

                try:
                    await page.wait_for_selector(
                        selectors["offer_card"], timeout=10_000
                    )
                except Exception:
                    logger.warning(
                        "[%s] No offer cards found on page %d",
                        portal_id,
                        current_page + 1,
                    )
                    break

                if pagination_type == "scroll":
                    await page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight)"
                    )
                    await page.wait_for_load_state("networkidle")

                cards = await page.query_selector_all(selectors["offer_card"])
                logger.info(
                    "[%s] Found %d cards on page %d",
                    portal_id,
                    len(cards),
                    current_page + 1,
                )

                for card in cards:
                    card_data = {
                        "title": await _card_text(card, selectors["title"]),
                        "company": await _card_text(card, selectors["company"]),
                        "url": await _card_href(card, selectors["url"]),
                        "location": await _card_text(
                            card, selectors.get("location", "")
                        ),
                        "date": await _card_datetime(card, selectors.get("date", "")),
                    }
                    offer = extract_offer_from_card_data(
                        card_data, portal_id=portal_id, base_url=base_url
                    )
                    if offer:
                        offers.append(offer)

                if pagination_type == "next_button":
                    next_btn = await page.query_selector(pagination["next_selector"])
                    if not next_btn:
                        break
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle")
                    current_page += 1
                elif pagination_type == "page_param":
                    current_page += 1
                    parsed = urlparse(url)
                    params = parse_qs(parsed.query)
                    params[pagination["page_param"]] = [str(current_page * page_size)]
                    new_query = urlencode({k: v[0] for k, v in params.items()})
                    url = urlunparse(parsed._replace(query=new_query))
                elif pagination_type == "scroll":
                    current_page += 1
                else:
                    break
        finally:
            await browser.close()

    logger.info("[%s] Total offers scraped: %d", portal_id, len(offers))
    return offers


async def run_scan(
    portal_ids: list[str], keywords: str, location: str
) -> list[RawOffer]:
    tasks = [scrape_portal(pid, keywords, location) for pid in portal_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_offers: list[RawOffer] = []
    for pid, result in zip(portal_ids, results):
        if isinstance(result, Exception):
            logger.error("[%s] Scrape failed: %s", pid, result)
        else:
            all_offers.extend(result)
    return all_offers


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="Scrape French job portals")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--portal", metavar="ID", help="Scrape a single portal")
    group.add_argument("--all", action="store_true", help="Scrape all portals")
    parser.add_argument("--keywords", default="AI Engineer")
    parser.add_argument("--location", default="Paris")
    args = parser.parse_args()

    portal_ids = list_portal_ids() if args.all else [args.portal]
    offers = asyncio.run(
        run_scan(portal_ids, keywords=args.keywords, location=args.location)
    )
    for offer in offers:
        print(f"[{offer.portal}] {offer.title} @ {offer.company} — {offer.url}")
    print(f"\nTotal: {len(offers)} offers")


if __name__ == "__main__":
    main()
