"""Check if a job posting URL is still active.

HTTP-first, zero browser, zero LLM.
Uses httpx (already in requirements).
"""

from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

_EXPIRED_URL_RE = re.compile(
    r"[?&/](expired|not[-_]found|error|closed|removed|unavailable)",
    re.IGNORECASE,
)

_EXPIRED_BODY_PATTERNS: list[str] = [
    # French
    "offre expirée",
    "offre pourvue",
    "poste pourvu",
    "ce poste n'est plus disponible",
    "cette offre a expiré",
    "offre clôturée",
    # English
    "job no longer available",
    "position has been filled",
    "this job has expired",
    "job has been removed",
    "no longer accepting",
    "this job is no longer available",
    "this position has been filled",
]

_HEAD_TIMEOUT = 8
_GET_TIMEOUT = 15
_MAX_BODY_BYTES = 50_000


def check_liveness(url: str, *, timeout: int = _GET_TIMEOUT) -> tuple[str, str]:
    """Return (status, reason).

    status: "active" | "expired" | "uncertain"
    reason: short string explaining the decision
    """
    if not url or not url.startswith(("http://", "https://")):
        return "uncertain", "no_url"

    if _EXPIRED_URL_RE.search(url):
        return "expired", "url_pattern"

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                return "expired", "http_404"
            if resp.status_code == 410:
                return "expired", "http_410"

            body = resp.text[:_MAX_BODY_BYTES].lower()

            for pattern in _EXPIRED_BODY_PATTERNS:
                if pattern in body:
                    return "expired", f"body_pattern:{pattern[:30]}"

            return "active", "ok"

    except (
        httpx.ConnectError,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        httpx.TooManyRedirects,
        httpx.InvalidURL,
    ) as exc:
        logger.debug("Liveness check uncertain for %s: %s", url, exc)
        return "uncertain", f"network_error:{type(exc).__name__}"
