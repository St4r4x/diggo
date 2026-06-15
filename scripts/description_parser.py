"""Parse raw job description text into structured fields per portal."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from scripts.models import ParsedDescription


# ---------------------------------------------------------------------------
# HTML -> plain text helper
# ---------------------------------------------------------------------------


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return " ".join(p for p in self._parts if p.strip()).strip()


def _html_to_text(html: str) -> str:
    p = _TextCollector()
    p.feed(html)
    return p.text()


# ---------------------------------------------------------------------------
# HTML heading splitter (Lever / Greenhouse / Ashby)
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"<h[234][^>]*>(.*?)</h[234]>", re.IGNORECASE | re.DOTALL)

_MISSION_HEADINGS = re.compile(
    r"about\s+the\s+role|about\s+the\s+job|the\s+role|missions?|poste|à\s+propos\s+du\s+poste",
    re.IGNORECASE,
)
_PROFIL_HEADINGS = re.compile(
    r"requirements?|qualifications?|profil|what\s+you.ll\s+bring|who\s+you\s+are",
    re.IGNORECASE,
)
_STACK_HEADINGS = re.compile(
    r"tech\s+stack|technologies|stack|outils|tools",
    re.IGNORECASE,
)
_AVANTAGES_HEADINGS = re.compile(
    r"what\s+we\s+offer|benefits?|perks?|avantages?|we\s+offer|package|compensation",
    re.IGNORECASE,
)


def _parse_html_headings(raw: str) -> ParsedDescription:
    sections: list[tuple[str, str]] = []
    for m in _HEADING_RE.finditer(raw):
        heading_text = _html_to_text(m.group(1))
        start = m.end()
        next_h = _HEADING_RE.search(raw, start)
        body_end = next_h.start() if next_h else len(raw)
        body = _html_to_text(raw[start:body_end]).strip()
        sections.append((heading_text, body))

    pd = ParsedDescription()
    for heading, body in sections:
        if _MISSION_HEADINGS.search(heading):
            pd.mission = (pd.mission + " " + body).strip()
        elif _PROFIL_HEADINGS.search(heading):
            pd.profil = (pd.profil + " " + body).strip()
        elif _STACK_HEADINGS.search(heading):
            pd.stack = (pd.stack + " " + body).strip()
        elif _AVANTAGES_HEADINGS.search(heading):
            pd.avantages = (pd.avantages + " " + body).strip()

    if not any([pd.mission, pd.profil, pd.stack, pd.avantages]):
        pd.mission = _html_to_text(raw).strip()

    return pd


# ---------------------------------------------------------------------------
# APEC parser (plain text blob, French section markers)
# ---------------------------------------------------------------------------

_APEC_PROFIL_RE = re.compile(r"profil\s+recherch[eé]", re.IGNORECASE)
_APEC_AVANTAGES_RE = re.compile(
    r"avantages?|b[eé]n[eé]fices?|ce\s+que\s+nous\s+offrons?|package", re.IGNORECASE
)
# Markers that delimit non-mission sections but are NOT mapped to avantages.
_APEC_OTHER_RE = re.compile(r"l.entreprise|à\s+propos", re.IGNORECASE)
# APEC prepends a metadata block before the actual description.
_APEC_DESCRIPTIF_RE = re.compile(r"descriptif\s+du\s+poste", re.IGNORECASE)
_APEC_SALAIRE_RE = re.compile(r"salaire\s*\n([^\n]+)", re.IGNORECASE)
_APEC_TELETRAVAIL_RE = re.compile(r"t[eé]l[eé]travail\s*\n([^\n]+)", re.IGNORECASE)


def _parse_apec(raw: str) -> ParsedDescription:
    pd = ParsedDescription()

    # Extract salaire and télétravail from the metadata header before trimming.
    sal_m = _APEC_SALAIRE_RE.search(raw)
    if sal_m:
        pd.salaire = sal_m.group(1).strip()
    tt_m = _APEC_TELETRAVAIL_RE.search(raw)
    if tt_m:
        pd.contrat = tt_m.group(1).strip()

    # Trim the metadata header — take only text from "Descriptif du poste" onward.
    desc_m = _APEC_DESCRIPTIF_RE.search(raw)
    body = raw[desc_m.end() :].strip() if desc_m else raw

    profil_m = _APEC_PROFIL_RE.search(body)
    avantages_m = _APEC_AVANTAGES_RE.search(body)
    other_m = _APEC_OTHER_RE.search(body)

    # Build cut-points from all known section starters.
    markers = {m.start(): m for m in [profil_m, avantages_m, other_m] if m is not None}
    cut_points = sorted(markers.keys())

    if not cut_points:
        pd.mission = body.strip()
        return pd

    pd.mission = body[: cut_points[0]].strip()

    for i, start in enumerate(cut_points):
        end = cut_points[i + 1] if i + 1 < len(cut_points) else len(body)
        chunk = body[start:end].strip()
        m = markers[start]
        if m is profil_m:
            pd.profil = chunk
        elif m is avantages_m:
            pd.avantages = chunk
        # _APEC_OTHER_RE chunks (company blurbs, etc.) are intentionally discarded.

    return pd


# ---------------------------------------------------------------------------
# Heuristic plain-text parser (Indeed / WTTJ / LinkedIn / Glassdoor)
# ---------------------------------------------------------------------------

_HEURISTIC_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:"
    r"missions?\s*:?"
    r"|responsabilit[eé]s?\s*:?"
    r"|poste\s*:?"
    r"|profil\s+recherch[eé]\s*:?"
    r"|profil\s*:?"
    r"|requirements?\s*:?"
    r"|qualifications?\s*:?"
    r"|stack\s+technique\s*:?"
    r"|tech(?:nologies|nical)?\s+stack\s*:?"
    r"|outils?\s*:?"
    r"|avantages?\s*:?"
    r"|b[eé]n[eé]fices?\s*:?"
    r"|benefits?\s*:?"
    r"|what\s+we\s+offer\s*:?"
    r"|package\s*:?"
    r")\s*\n",
    re.IGNORECASE,
)

_SECTION_MISSION = re.compile(r"missions?|responsabilit[eé]s?|poste", re.IGNORECASE)
_SECTION_PROFIL = re.compile(r"profil|requirements?|qualifications?", re.IGNORECASE)
_SECTION_STACK = re.compile(r"stack|technologies|outils?", re.IGNORECASE)
_SECTION_AVANTAGES = re.compile(
    r"avantages?|b[eé]n[eé]fices?|benefits?|what\s+we\s+offer|package", re.IGNORECASE
)


def _parse_heuristic(raw: str) -> ParsedDescription:
    matches = list(_HEURISTIC_SECTION_RE.finditer(raw))

    pd = ParsedDescription()
    if not matches:
        pd.mission = raw.strip()
        return pd

    before = raw[: matches[0].start()].strip()
    if before:
        pd.mission = before

    for i, m in enumerate(matches):
        label = m.group(0).strip().rstrip(":").strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[start:end].strip()

        if _SECTION_MISSION.search(label):
            pd.mission = (pd.mission + " " + body).strip()
        elif _SECTION_PROFIL.search(label):
            pd.profil = (pd.profil + " " + body).strip()
        elif _SECTION_STACK.search(label):
            pd.stack = (pd.stack + " " + body).strip()
        elif _SECTION_AVANTAGES.search(label):
            pd.avantages = (pd.avantages + " " + body).strip()
        else:
            pd.mission = (pd.mission + " " + body).strip()

    if not pd.mission:
        pd.mission = raw.strip()

    return pd


# ---------------------------------------------------------------------------
# Generic fallback
# ---------------------------------------------------------------------------


def _parse_generic(raw: str) -> ParsedDescription:
    pd = ParsedDescription()
    pd.mission = raw.strip()
    return pd


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

_HTML_PORTALS = frozenset({"lever", "greenhouse", "ashby"})
_HEURISTIC_PORTALS = frozenset({"indeed", "wttj", "linkedin", "glassdoor"})


def parse_description(raw: str, portal: str) -> ParsedDescription:
    """Parse a raw description string into structured fields.

    Dispatches to a portal-specific parser; falls back to generic.
    """
    if not raw:
        return ParsedDescription()
    portal_lower = portal.lower()
    if portal_lower == "apec":
        return _parse_apec(raw)
    if portal_lower in _HTML_PORTALS:
        return _parse_html_headings(raw)
    if portal_lower in _HEURISTIC_PORTALS:
        return _parse_heuristic(raw)
    return _parse_generic(raw)
