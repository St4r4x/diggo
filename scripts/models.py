"""Shared data models for career-ops-fr portal scanning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class RawOffer:
    """A job offer as scraped from a portal, before any scoring."""

    title: str
    company: str
    url: str
    portal: str
    location: Optional[str] = None
    date_posted: Optional[date] = None
    score: float = 0.0
    tags: list[str] = field(default_factory=list)

    def dedup_key(self) -> str:
        title_norm = self.title.lower().strip()
        company_norm = self.company.lower().strip()
        return f"{title_norm}||{company_norm}"
