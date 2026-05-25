"""Pre-filter: score offers against settings.yaml and drop those below threshold.

Scoring rubric (max 5.0):
- +1.0 per keyword from search.keywords found in the offer title (case-insensitive)
- +1.0 if the company appears in any target_companies list (case-insensitive)
- +1.0 if the offer location contains the search.location string (case-insensitive)
- +0.5 if the title contains a junior/apprenti/alternance indicator
- Score capped at 5.0
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from scripts.models import RawOffer

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"

_JUNIOR_PATTERNS = frozenset(["junior", "alternance", "stage", "apprenti", "stagiaire"])


def load_settings(path: Path = _SETTINGS_PATH) -> dict:
    """Load and return the parsed settings.yaml."""
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _all_target_companies(settings: dict) -> set[str]:
    companies: set[str] = set()
    for category in settings.get("target_companies", {}).values():
        for name in category:
            companies.add(name.lower())
    return companies


def score_offer(offer: RawOffer, settings: dict) -> tuple[float, list[str]]:
    """Compute a relevance score and matched tags for a single offer."""
    score = 0.0
    tags: list[str] = []
    title_lower = offer.title.lower()
    company_lower = offer.company.lower()
    location_lower = (offer.location or "").lower()

    search_keywords: list[str] = settings.get("search", {}).get("keywords", [])
    for kw in search_keywords:
        if kw.lower() in title_lower:
            score += 1.0
            tags.append(kw)

    target_companies = _all_target_companies(settings)
    if company_lower in target_companies:
        score += 1.0
        tags.append(f"target:{offer.company}")

    search_location: str = settings.get("search", {}).get("location", "").lower()
    if search_location and search_location in location_lower:
        score += 1.0
        tags.append(f"location:{offer.location}")

    for pattern in _JUNIOR_PATTERNS:
        if pattern in title_lower:
            score += 0.5
            tags.append(f"seniority:{pattern}")
            break

    return min(score, 5.0), tags


def pre_filter(offers: list[RawOffer], settings: dict) -> list[RawOffer]:
    """Score all offers and return only those meeting the consider threshold."""
    threshold: float = (
        settings.get("scoring", {}).get("thresholds", {}).get("consider", 3.0)
    )

    kept: list[RawOffer] = []
    for offer in offers:
        score, tags = score_offer(offer, settings)
        offer.score = score
        offer.tags = tags
        if score >= threshold:
            kept.append(offer)
        else:
            logger.debug(
                "Dropped [score=%.1f]: %s @ %s", score, offer.title, offer.company
            )

    logger.info(
        "Pre-filter: kept %d / %d offers (threshold %.1f)",
        len(kept),
        len(offers),
        threshold,
    )
    return kept
