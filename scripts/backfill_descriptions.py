"""Backfill missing job descriptions, using public APIs where available, Playwright otherwise."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol

import httpx
from playwright.async_api import Page, async_playwright

from scripts.description_parser import parse_description
from scripts.import_offers import infer_portal_from_url

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
        # Lever HTML uses <strong style="font-size:24px"> not <h2>/<h3>, so plain text
        # is better for heuristic splitting.  Prefer descriptionPlain; fall back to HTML.
        plain = (data.get("descriptionPlain") or "").strip()
        if len(plain) >= MIN_DESC_LENGTH:
            return plain[:8000]
        html = (data.get("description") or "").strip()
        return html[:8000] if len(html) >= MIN_DESC_LENGTH else ""


class GreenhouseApiExtractor:
    """Greenhouse public boards API — `content` field is HTML, no auth required."""

    needs_browser = False

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
        html = unescape(data.get("content") or "").strip()
        return html[:8000] if html else ""


class ApecApiExtractor:
    """APEC internal webservice — discovered via network interception, no auth required.

    Builds ParsedDescription directly from structured API fields:
      - texteHtml          → mission
      - texteHtmlProfil    → profil
      - competences[]      → stack  (SAVOIR_FAIRE type only)
      - texteHtmlEntreprise → avantages
      - salaireTexte       → salaire
    Returns a JSON-serialised ParsedDescription (not raw text) so _save_parsed
    can store it directly without re-parsing.
    The offer ID includes an optional uppercase letter suffix (e.g. 178734687W).
    """

    needs_browser = False

    _OFFRE_RE = re.compile(r"/detail-offre/(\d+[A-Z]?)", re.IGNORECASE)
    _API = "https://www.apec.fr/cms/webservices/offre/public?numeroOffre={}"

    async def extract(self, client: httpx.AsyncClient, url: str) -> str:
        from scripts.models import ParsedDescription

        m = self._OFFRE_RE.search(url)
        if not m:
            return ""
        api_url = self._API.format(m.group(1))
        try:
            r = await client.get(
                api_url,
                timeout=15,
                headers={**_HEADERS, "Referer": url},
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.debug("APEC API error for %s: %s", url[:80], exc)
            return ""

        mission = _html_to_text(data.get("texteHtml") or "")
        profil = _html_to_text(data.get("texteHtmlProfil") or "")
        avantages = _html_to_text(data.get("texteHtmlEntreprise") or "")
        salaire = (data.get("salaireTexte") or "").strip()

        # Competences: keep only SAVOIR_FAIRE (tools/techs), join as comma list
        stack_items = [
            c["libelle"]
            for c in (data.get("competences") or [])
            if c.get("type") == "SAVOIR_FAIRE"
        ]
        stack = ", ".join(stack_items)

        pd = ParsedDescription(
            mission=mission,
            profil=profil,
            stack=stack,
            avantages=avantages,
            salaire=salaire,
        )
        # Return JSON so _save_parsed stores it directly (no text re-parsing needed)
        return pd.to_json() if mission else ""


class AshbyJsonLdExtractor:
    """Ashby: HTML is server-rendered and embeds a JSON-LD JobPosting block with the full description."""

    needs_browser = False

    _JSONLD_RE = re.compile(
        r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.DOTALL
    )

    async def extract(self, client: httpx.AsyncClient, url: str) -> str:
        try:
            r = await client.get(url, timeout=15)
            r.raise_for_status()
        except Exception as exc:
            logger.debug("Ashby fetch error for %s: %s", url[:80], exc)
            return ""
        for m in self._JSONLD_RE.finditer(r.text):
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            if data.get("@type") == "JobPosting":
                html = (data.get("description") or "").strip()
                return html[:8000] if html else ""
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


def _is_valid_json(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def get_extractor(
    url: str,
) -> HttpExtractor | BrowserExtractor | None:
    if "lever.co" in url:
        return LeverApiExtractor()
    if "greenhouse.io" in url:
        return GreenhouseApiExtractor()
    if "apec.fr" in url:
        return ApecApiExtractor()
    if "ashbyhq.com" in url:
        return AshbyJsonLdExtractor()
    if "indeed.com" in url:
        return IndeedExtractor()
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT id, offer_url, COALESCE(portal, '') AS portal,
                  COALESCE(description, '') AS description
           FROM applications
           WHERE length(description) < 50
              OR NOT json_valid(description)
              OR (
                   json_valid(description)
                   AND json_extract(description, '$.profil') = ''
                   AND json_extract(description, '$.stack') = ''
                   AND json_extract(description, '$.avantages') = ''
              )
              OR (
                   portal = 'apec'
                   AND json_valid(description)
                   AND json_extract(description, '$.stack') = ''
              )
           ORDER BY id"""
    ).fetchall()
    logger.info("%d offers to backfill", len(rows))

    updated = 0
    skipped = 0
    extractor_cache = {url: get_extractor(url) for _, url, _, _ in rows}
    browser_needed = any(
        e is not None and e.needs_browser for e in extractor_cache.values()
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
            for offer_id, url, portal, existing_desc in rows:
                # Infer and persist portal for legacy empty-portal rows
                inferred = infer_portal_from_url(url) if not portal else portal
                if inferred != portal:
                    conn.execute(
                        "UPDATE applications SET portal=? WHERE id=?",
                        (inferred, offer_id),
                    )
                    portal = inferred

                def _save_parsed(desc: str) -> None:
                    nonlocal updated
                    # ApecApiExtractor returns a pre-built ParsedDescription JSON —
                    # store it directly without re-parsing.
                    if _is_valid_json(desc):
                        dj = desc
                    else:
                        dj = parse_description(desc, portal).to_json()
                    conn.execute(
                        "UPDATE applications SET description=? WHERE id=?",
                        (dj, offer_id),
                    )
                    updated += 1
                    logger.info("  -> %d chars saved as JSON", len(dj))

                # If we already have a long plain-text description, re-parse it
                # directly without hitting the network (handles expired APEC offers).
                if (
                    not _is_valid_json(existing_desc)
                    and len(existing_desc) >= MIN_DESC_LENGTH
                ):
                    logger.info(
                        "[%d] re-parsing existing plain text (%d chars)",
                        offer_id,
                        len(existing_desc),
                    )
                    _save_parsed(existing_desc)
                    continue

                extractor = extractor_cache[url]
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
                    _save_parsed(desc)
                else:
                    logger.info(
                        "  -> too short or empty (%d chars), skipping", len(desc)
                    )
        finally:
            if browser:
                await browser.close()
            if pw_ctx and pw:
                await pw_ctx.__aexit__(None, None, None)

    conn.commit()
    conn.close()
    logger.info(
        "Done: %d/%d updated | %d skipped (no extractor)",
        updated,
        len(rows),
        skipped,
    )


if __name__ == "__main__":
    asyncio.run(main())
