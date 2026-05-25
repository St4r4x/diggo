"""Deduplication of job offers across portals.

Two offers are considered duplicates when their normalized title+company key is
identical.  Normalization:
- Lowercase
- Unicode accent stripping (NFD decomposition + ASCII encoding)
- Punctuation removal (only alphanumeric and spaces kept)
- Collapse multiple spaces to one
"""

from __future__ import annotations

import re
import unicodedata

from scripts.models import RawOffer


def _remove_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def normalize_key(title: str, company: str) -> str:
    """Build a normalized deduplication key from title and company.

    Args:
        title: Raw job title string.
        company: Raw company name string.

    Returns:
        A normalized key string: ``"<title>||<company>"``.
    """

    def _normalize(text: str) -> str:
        text = text.strip().lower()
        text = _remove_accents(text)
        text = re.sub(r"[^a-z0-9 ]", " ", text)
        text = re.sub(r" {2,}", " ", text).strip()
        return text

    return f"{_normalize(title)}||{_normalize(company)}"


def deduplicate(offers: list[RawOffer]) -> list[RawOffer]:
    """Remove duplicate offers, keeping the first occurrence per unique key.

    Args:
        offers: List of raw offers, potentially containing duplicates.

    Returns:
        Deduplicated list of ``RawOffer``, in original order of first occurrence.
    """
    seen: set[str] = set()
    unique: list[RawOffer] = []
    for offer in offers:
        key = normalize_key(offer.title, offer.company)
        if key not in seen:
            seen.add(key)
            unique.append(offer)
    return unique
