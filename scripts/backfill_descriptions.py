"""Backfill missing job descriptions, using public APIs where available, Playwright otherwise."""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol

import httpx
from playwright.async_api import Page, async_playwright

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "dashboard" / "data" / "applications.db"
CHROME_PATH = "/usr/bin/google-chrome-stable"
NAV_TIMEOUT = 20_000
SELECTOR_TIMEOUT = 10_000
MIN_DESC_LENGTH = 100

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}


# ---------------------------------------------------------------------------
# HTML → plain text
# ---------------------------------------------------------------------------


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return " ".join(self._parts).strip()


def _html_to_text(html: str) -> str:
    # Greenhouse returns doubly-encoded HTML entities — unescape once before parsing
    p = _TextExtractor()
    p.feed(unescape(html))
    return p.text()


# ---------------------------------------------------------------------------
# Extractor protocol — two flavours:
#   HttpExtractor.extract(client, url) -> str   (no browser needed)
#   BrowserExtractor.extract(page, url) -> str  (Playwright required)
# ---------------------------------------------------------------------------


class HttpExtractor(Protocol):
    needs_browser: bool  # always False

    async def extract(self, client: httpx.AsyncClient, url: str) -> str: ...


class BrowserExtractor(Protocol):
    needs_browser: bool  # always True

    async def extract(self, page: Page, url: str) -> str: ...


# ---------------------------------------------------------------------------
# HTTP extractors  (no browser)
# ---------------------------------------------------------------------------


class LeverApiExtractor:
    """Lever public REST API — returns full JSON with HTML description, no auth."""

    needs_browser = False

    _UUID_RE = re.compile(r"lever\.co/([^/]+)/([0-9a-f-]{36})", re.IGNORECASE)

    async def extract(self, client: httpx.AsyncClient, url: str) -> str:
        m = self._UUID_RE.search(url)
        if not m:
            return ""
        company, job_id = m.group(1), m.group(2)
        api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
        try:
            r = await client.get(api_url, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.debug("Lever API error for %s: %s", url[:80], exc)
            return ""
        # Prefer plain text; fall back to HTML → text
        plain = (data.get("descriptionPlain") or "").strip()
        if len(plain) >= MIN_DESC_LENGTH:
            return plain
        html = (data.get("description") or "").strip()
        return _html_to_text(html) if html else ""


class GreenhouseApiExtractor:
    """Greenhouse public boards API — champ `content` HTML, no auth."""

    needs_browser = False

    # job-boards.greenhouse.io/{company}/jobs/{id}
    _PATH_RE = re.compile(r"greenhouse\.io/([^/]+)/jobs/(\d+)", re.IGNORECASE)

    async def extract(self, client: httpx.AsyncClient, url: str) -> str:
        m = self._PATH_RE.search(url)
        if not m:
            return ""
        company, job_id = m.group(1), m.group(2)
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}"
        try:
            r = await client.get(api_url, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.debug("Greenhouse API error for %s: %s", url[:80], exc)
            return ""
        html = (data.get("content") or "").strip()
        return _html_to_text(html) if html else ""


# ---------------------------------------------------------------------------
# Browser extractors  (Playwright required)
# ---------------------------------------------------------------------------


class ApecExtractor:
    """APEC: Angular custom element — no public API, browser required."""

    needs_browser = True

    async def extract(self, page: Page, url: str) -> str:
        await page.goto(url, timeout=NAV_TIMEOUT, wait_until="networkidle")
        try:
            await page.wait_for_selector(
                "apec-poste-informations", timeout=SELECTOR_TIMEOUT
            )
            return (await page.locator("apec-poste-informations").inner_text()).strip()
        except Exception:
            return ""


class AshbyBrowserExtractor:
    """Ashby: SPA with tabbed layout — content in the Overview tabpanel."""

    needs_browser = True

    _SELECTORS = [
        "[role='tabpanel']",
        "[data-testid='job-description']",
        ".ashby-job-posting-brief-description",
        ".posting-description",
    ]

    async def extract(self, page: Page, url: str) -> str:
        await page.goto(url, timeout=NAV_TIMEOUT, wait_until="networkidle")
        for sel in self._SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=SELECTOR_TIMEOUT)
                text = (await page.locator(sel).inner_text()).strip()
                if len(text) >= MIN_DESC_LENGTH:
                    return text
            except Exception:
                continue
        return ""


class IndeedExtractor:
    """Indeed rc/clk: extract jk= param, reconstruct canonical page URL."""

    needs_browser = True

    _JK_RE = re.compile(r"[?&]jk=([a-f0-9]+)")

    async def extract(self, page: Page, url: str) -> str:
        m = self._JK_RE.search(url)
        if not m:
            return ""
        canonical = f"https://fr.indeed.com/voir-emploi?jk={m.group(1)}"
        await page.goto(canonical, timeout=NAV_TIMEOUT, wait_until="networkidle")
        for sel in [
            "#jobDescriptionText",
            ".jobsearch-jobDescriptionText",
            "[data-testid='jobsearch-JobComponent-description']",
        ]:
            try:
                await page.wait_for_selector(sel, timeout=SELECTOR_TIMEOUT)
                text = (await page.locator(sel).inner_text()).strip()
                if len(text) >= MIN_DESC_LENGTH:
                    return text
            except Exception:
                continue
        return ""


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def get_extractor(
    url: str,
) -> HttpExtractor | BrowserExtractor | None:
    if "lever.co" in url:
        return LeverApiExtractor()
    if "greenhouse.io" in url:
        return GreenhouseApiExtractor()
    if "apec.fr" in url:
        return ApecExtractor()
    if "ashbyhq.com" in url:
        return AshbyBrowserExtractor()
    if "indeed.com" in url:
        return IndeedExtractor()
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, offer_url FROM applications"
        " WHERE length(description) < 50"
        " ORDER BY id"
    ).fetchall()
    logger.info("%d offers to backfill", len(rows))

    updated = 0
    skipped = 0
    browser_needed = any(
        (e := get_extractor(url)) is not None and e.needs_browser for _, url in rows
    )

    async with httpx.AsyncClient(headers=_HEADERS) as http_client:
        # Lazy-init browser only if at least one URL needs it
        pw_ctx = async_playwright() if browser_needed else None
        pw = await pw_ctx.__aenter__() if pw_ctx else None
        browser = (
            await pw.chromium.launch(
                headless=True,
                executable_path=CHROME_PATH,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            if pw
            else None
        )
        browser_context = (
            await browser.new_context(
                user_agent=_HEADERS["User-Agent"],
                locale="fr-FR",
            )
            if browser
            else None
        )
        page = await browser_context.new_page() if browser_context else None

        try:
            for offer_id, url in rows:
                extractor = get_extractor(url)
                if extractor is None:
                    logger.warning("[%d] No extractor for: %s", offer_id, url[:80])
                    skipped += 1
                    continue

                logger.info(
                    "[%d] %-26s %s", offer_id, type(extractor).__name__, url[:80]
                )
                try:
                    if extractor.needs_browser:
                        assert page is not None
                        desc = await extractor.extract(page, url)
                    else:
                        desc = await extractor.extract(http_client, url)
                except Exception as exc:
                    logger.warning("[%d] Error: %s", offer_id, exc)
                    desc = ""

                if len(desc) >= MIN_DESC_LENGTH:
                    conn.execute(
                        "UPDATE applications SET description=? WHERE id=?",
                        (desc, offer_id),
                    )
                    conn.commit()
                    updated += 1
                    logger.info("  -> %d chars saved", len(desc))
                else:
                    logger.info(
                        "  -> too short or empty (%d chars), skipping", len(desc)
                    )
        finally:
            if browser:
                await browser.close()
            if pw_ctx and pw:
                await pw_ctx.__aexit__(None, None, None)

    conn.close()
    logger.info(
        "Done: %d/%d updated | %d skipped (no extractor)",
        updated,
        len(rows),
        skipped,
    )


if __name__ == "__main__":
    asyncio.run(main())
