"""Pre-filter: score offers against settings.yaml and drop those below threshold."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from scripts.models import RawOffer

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"

_JUNIOR_PATTERNS = frozenset(["junior", "alternance", "stage", "apprenti", "stagiaire"])

_TECH_SKILLS = frozenset(
    [
        "pytorch",
        "tensorflow",
        "sklearn",
        "scikit-learn",
        "xgboost",
        "lightgbm",
        "hugging face",
        "transformers",
        "fine-tuning",
        "rag",
        "langchain",
        "llm",
        "computer vision",
        "nlp",
        "mlops",
        "mlflow",
        "docker",
        "kubernetes",
        "fastapi",
        "airflow",
        "spark",
        "aws",
        "gcp",
        "azure",
        "postgresql",
        "mongodb",
        "redis",
        "python",
        "sql",
        "rust",
        "typescript",
        "vector search",
        "embedding",
        "retrieval",
        "generative ai",
    ]
)

_QUALITY_PORTALS = frozenset(["lever", "greenhouse", "ashby"])

_COMPANY_NOISE = re.compile(
    r"\b(france|group|groupe|sas|s\.a\.s|inc|ltd|gmbh|f/h|h/f|sa|spa)\b",
    re.IGNORECASE,
)

_EXP_RE = re.compile(r"(\d+)\s*(?:à\s*\d+\s*)?ans?\s+d.expérience", re.IGNORECASE)
_CDI_RE = re.compile(r"\bCDI\b")
_SALARY_RE = re.compile(r"(\d{2,3})\s*[kK€]|\b(\d{4,6})\s*€")


def load_settings(path: Path = _SETTINGS_PATH) -> dict:
    """Load and return the parsed settings.yaml."""
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _normalize_company(name: str) -> str:
    return _COMPANY_NOISE.sub("", name).strip().lower()


def _all_target_companies(settings: dict) -> set[str]:
    companies: set[str] = set()
    for category in settings.get("target_companies", {}).values():
        for name in category:
            companies.add(_normalize_company(name))
    return companies


def score_offer(offer: RawOffer, settings: dict) -> tuple[float, list[str]]:
    """Compute a relevance score and matched tags for a single offer."""
    score = 0.0
    tags: list[str] = []
    title_lower = offer.title.lower()
    company_norm = _normalize_company(offer.company)
    location_lower = (offer.location or "").lower()
    desc_lower = (offer.description or "").lower()

    search_cfg = settings.get("search", {})
    scoring_cfg = settings.get("scoring", {})

    for kw in search_cfg.get("keywords", []):
        if kw.lower() in title_lower:
            score += 1.0
            tags.append(kw)

    target_companies = _all_target_companies(settings)
    if company_norm in target_companies:
        score += 1.0
        tags.append(f"target:{offer.company}")

    search_location = search_cfg.get("location", "").lower()
    if search_location and search_location in location_lower:
        score += 1.0
        tags.append(f"location:{offer.location}")

    for pattern in _JUNIOR_PATTERNS:
        if pattern in title_lower:
            score += 0.5
            tags.append(f"seniority:{pattern}")
            break

    if desc_lower:
        matched_skills = [s for s in _TECH_SKILLS if s in desc_lower]
        skill_bonus = min(len(matched_skills) * 0.1, 1.0)
        if skill_bonus > 0:
            score += skill_bonus
            tags.append(f"skills:{len(matched_skills)}")

    if desc_lower:
        exp_match = _EXP_RE.search(desc_lower)
        if exp_match:
            exp_years = int(exp_match.group(1))
            max_exp = search_cfg.get("experience_max_years", 3)
            if exp_years <= max_exp:
                score += 0.5
                tags.append(f"exp:{exp_years}ans")

    if desc_lower and _CDI_RE.search(offer.description or ""):
        score += 0.3
        tags.append("contract:CDI")

    if desc_lower:
        sal_min = scoring_cfg.get("target_salary_min", 0)
        sal_max = scoring_cfg.get("target_salary_max", 999_999)
        for m in _SALARY_RE.finditer(desc_lower):
            raw = m.group(1) or m.group(2)
            if raw:
                val = int(raw)
                if val < 1000:
                    val *= 1000
                if sal_min <= val <= sal_max:
                    score += 0.3
                    tags.append(f"salary:{val}")
                    break

    if offer.portal in _QUALITY_PORTALS:
        score += 0.3
        tags.append(f"portal:{offer.portal}")

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
