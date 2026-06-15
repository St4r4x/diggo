"""Shared data models for career-ops-fr portal scanning."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date


@dataclass
class ParsedDescription:
    """Structured fields extracted from a raw job description."""

    mission: str = ""
    profil: str = ""
    stack: str = ""
    avantages: str = ""
    contrat: str = ""
    salaire: str = ""


@dataclass
class RawOffer:
    """A job offer as scraped from a portal, before any scoring."""

    title: str
    company: str
    url: str
    portal: str
    location: str | None = None
    date_posted: date | None = None
    score: float = 0.0
    tags: list[str] = field(default_factory=list)
    description: str = ""
    parsed_description: ParsedDescription | None = None

    def dedup_key(self) -> str:
        title_norm = self.title.lower().strip()
        company_norm = self.company.lower().strip()
        return f"{title_norm}||{company_norm}"


def strip_html(html: str) -> str:
    """Strip HTML tags and collapse whitespace to plain text."""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()
