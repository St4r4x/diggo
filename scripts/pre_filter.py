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

_REMOTE_RE = re.compile(
    r"remote|full.remote|télétravail|teletravail|hybride|hybrid", re.IGNORECASE
)


def _is_location_compatible(location: str, target: str) -> bool:
    """Return True if the offer location is acceptable given the target location.

    Passes when: location is empty, offer is remote/hybrid, or target appears
    anywhere in the offer location string (case-insensitive).
    """
    if not location:
        return True
    if _REMOTE_RE.search(location):
        return True
    return target.lower() in location.lower()


_COMPANY_NOISE = re.compile(
    r"\b(france|group|groupe|sas|s\.a\.s|inc|ltd|gmbh|f/h|h/f|sa|spa)\b",
    re.IGNORECASE,
)

# Covers "2 ans d'expérience", "2 années d'expérience", "Minimum 2 ans" (WTTJ), "2 years of experience"
_EXP_RE = re.compile(
    r"(?:minimum\s+)?(\d+)\s*(?:\+|à\s*\d+\s*)?ann?[eé]es?\s+d.exp[eé]rience"
    r"|(?:minimum\s+)?(\d+)\s*(?:\+|à\s*\d+\s*)?ans?\s+d.exp[eé]rience"
    r"|minimum\s+(\d+)\s+ans?"
    r"|(\d+)\+?\s*years?\s+of\s+experience",
    re.IGNORECASE,
)
_CDI_RE = re.compile(r"\bCDI\b")
# Detects explicit instruction to submit CV/application in English (not just "fluent in English")
_CV_EN_RE = re.compile(
    r"(?:submit|send|provide|write|prepare)\s+(?:your\s+)?(?:cv|resume|application)\s+in\s+english"
    r"|cv\s+in\s+english"
    r"|resume\s+in\s+english"
    r"|english\s+(?:cv|resume)\s+(?:required|only|preferred)"
    r"|candidature\s+en\s+anglais"
    r"|dossier\s+en\s+anglais",
    re.IGNORECASE,
)
# Covers "45k€", "45K", "45keuro", "45 000 €"
_SALARY_RE = re.compile(
    r"(\d{2,3})\s*[kK€]|(\d{2,3})\s*keuro|\b(\d{4,6})\s*€", re.IGNORECASE
)
_MONTHS_13_RE = re.compile(r"13[eè]me?\s*mois|treizi[eè]me\s*mois", re.IGNORECASE)
# Covers "15 RTT", "RTT" alone (presence), "RTTs"
_RTT_RE = re.compile(r"(\d+)\s*RTTs?|\bRTTs?\b", re.IGNORECASE)
# Covers "titre-restaurant", "ticket restaurant", "swile"
_TR_RE = re.compile(r"titre[\s-]restaurant|ticket[\s-]restaurant|swile", re.IGNORECASE)
_INTERESSEMENT_RE = re.compile(r"int[eé]ressement|participation", re.IGNORECASE)

# Salary reconstruction constants (French employment law reference values)
_DEFAULT_RTT_DAYS = 10  # assumed RTT days when "RTT" present without count
_ANNUAL_WORKING_DAYS = 218  # French legal working days (basis for RTT/TR calculation)
_MEAL_TICKET_VALUE_PER_DAY = 9.0  # average meal ticket face value (€/day)
_INTERESSEMENT_RATE = 0.05  # assumed intéressement/participation rate (5%)


def _desc_blob(offer: RawOffer) -> str:
    """Return a flat text string for regex scoring, from parsed or raw description."""
    if offer.parsed_description is not None:
        pd = offer.parsed_description
        return " ".join(
            filter(
                None,
                [pd.mission, pd.profil, pd.stack, pd.avantages, pd.contrat, pd.salaire],
            )
        )
    return offer.description or ""


def load_settings(path: Path = _SETTINGS_PATH, user_id: str | None = None) -> dict:
    """Load settings from DB (if user_id given) or fall back to settings.yaml."""
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
                return _ud.get_settings(conn, user_id)
            finally:
                conn.close()
        except Exception:
            pass
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _normalize_company(name: str) -> str:
    return _COMPANY_NOISE.sub("", name).strip().lower()


def _all_target_companies(settings: dict) -> set[str]:
    companies: set[str] = set()
    for category in settings.get("target_companies", {}).values():
        for name in category:
            companies.add(_normalize_company(name))
    return companies


def _score_salary(
    desc: str, desc_lower: str, scoring_cfg: dict
) -> tuple[float, str | None]:
    """Reconstruct French annual package and return (score_delta, tag_or_None)."""
    sal_min = scoring_cfg.get("target_salary_min", 0)
    sal_max = scoring_cfg.get("target_salary_max", 999_999)

    m = _SALARY_RE.search(desc_lower)
    if not m:
        return 0.0, None

    if m.group(1):
        # "45k€" / "45K" shorthand → thousands
        base_annual = int(m.group(1)) * 1000
    elif m.group(2):
        # "50 keuro" shorthand → thousands
        base_annual = int(m.group(2)) * 1000
    elif m.group(3):
        # Raw number "45 000 €" — monthly if < 10 000, else annual
        raw_val = int(m.group(3))
        if raw_val < 10_000:
            multiplier = 13 if _MONTHS_13_RE.search(desc_lower) else 12
            base_annual = raw_val * multiplier
        else:
            base_annual = raw_val
    else:
        return 0.0, None

    rtt_match = _RTT_RE.search(desc_lower)
    if rtt_match and rtt_match.group(1):
        rtt_days = int(rtt_match.group(1))
    elif rtt_match:
        rtt_days = _DEFAULT_RTT_DAYS
    else:
        rtt_days = 0
    rtt_val = rtt_days * base_annual / _ANNUAL_WORKING_DAYS if rtt_days else 0.0

    tr_val = (
        _ANNUAL_WORKING_DAYS * _MEAL_TICKET_VALUE_PER_DAY
        if _TR_RE.search(desc_lower)
        else 0.0
    )

    int_val = (
        base_annual * _INTERESSEMENT_RATE
        if _INTERESSEMENT_RE.search(desc_lower)
        else 0.0
    )

    total = base_annual + rtt_val + tr_val + int_val
    tag = f"salary:{int(total)}"

    if sal_min <= total <= sal_max:
        return 0.5, tag
    return -0.3, tag


def _score_legitimacy(desc: str, desc_lower: str) -> tuple[float, list[str]]:
    """Return (penalty, tags) based on offer quality signals. Penalty capped at -0.5."""
    penalty = 0.0
    tags: list[str] = []

    if len(desc) < 300:
        penalty -= 0.5
        tags.append("legitimacy:thin_desc")

    if not any(skill in desc_lower for skill in _TECH_SKILLS):
        penalty -= 0.3
        tags.append("legitimacy:no_tech")

    if not _SALARY_RE.search(desc_lower):
        penalty -= 0.2
        tags.append("legitimacy:no_salary")

    capped = max(penalty, -0.5)
    if capped <= -0.3:
        tags.append("legitimacy:suspicious")

    return capped, tags


def score_offer(offer: RawOffer, settings: dict) -> tuple[float, list[str]]:
    """Compute a relevance score and matched tags for a single offer."""
    score = 0.0
    tags: list[str] = []
    title_lower = offer.title.lower()
    company_norm = _normalize_company(offer.company)
    location_lower = (offer.location or "").lower()
    desc_lower = _desc_blob(offer).lower()

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
            # _EXP_RE has 4 capture groups — take the first non-None
            raw_exp = next(g for g in exp_match.groups() if g is not None)
            exp_years = int(raw_exp)
            max_exp = search_cfg.get("experience_max_years", 3)
            if exp_years <= max_exp:
                score += 0.5
                tags.append(f"exp:{exp_years}ans")

    if desc_lower and _CDI_RE.search(_desc_blob(offer)):
        score += 0.3
        tags.append("contract:CDI")

    if desc_lower:
        sal_delta, sal_tag = _score_salary(_desc_blob(offer), desc_lower, scoring_cfg)
        if sal_delta != 0.0:
            score += sal_delta
            if sal_tag:
                tags.append(sal_tag)

    if offer.portal in _QUALITY_PORTALS:
        score += 0.3
        tags.append(f"portal:{offer.portal}")

    if desc_lower:
        leg_delta, leg_tags = _score_legitimacy(_desc_blob(offer), desc_lower)
        if leg_delta != 0.0:
            score += leg_delta
            tags.extend(leg_tags)

    if desc_lower and _CV_EN_RE.search(_desc_blob(offer)):
        tags.append("lang:cv_en_required")

    return min(score, 5.0), tags


def pre_filter(offers: list[RawOffer], settings: dict) -> list[RawOffer]:
    """Score all offers and return only those meeting the consider threshold."""
    threshold: float = (
        settings.get("scoring", {}).get("thresholds", {}).get("consider", 3.0)
    )
    location_filter = settings.get("search", {}).get("location", "")
    filter_by_location = bool(location_filter)
    kept: list[RawOffer] = []
    for offer in offers:
        if filter_by_location and not _is_location_compatible(
            offer.location or "", location_filter
        ):
            logger.debug(
                "Dropped [location]: %s @ %s (location=%r)",
                offer.title,
                offer.company,
                offer.location,
            )
            continue
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
