from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg2.extensions
import yaml

_CONTACT_YAML = Path(__file__).parent.parent / "config" / "contact.yaml"
_PROFILE_MD = Path(__file__).parent.parent / "config" / "profile.md"
_SETTINGS_YAML = Path(__file__).parent.parent / "config" / "settings.yaml"

_PROFILE_KEYS = (
    "name",
    "title",
    "email",
    "phone",
    "location",
    "linkedin",
    "github",
    "profile_md",
)
_SETTINGS_KEYS = (
    "keywords",
    "portal_queries",
    "location",
    "contract",
    "experience_max_years",
    "salary_min",
    "salary_max",
    "target_companies",
    "follow_up_days",
)


def _empty_profile() -> dict[str, Any]:
    return {k: "" for k in _PROFILE_KEYS}


def _empty_settings() -> dict[str, Any]:
    return {
        "keywords": [],
        "portal_queries": [],
        "location": "",
        "contract": "CDI",
        "experience_max_years": 3,
        "salary_min": 0,
        "salary_max": 0,
        "target_companies": [],
        "follow_up_days": 7,
    }


def _migrate_profile_from_files() -> dict[str, Any] | None:
    if not _CONTACT_YAML.exists():
        return None
    with _CONTACT_YAML.open(encoding="utf-8") as f:
        contact = yaml.safe_load(f) or {}
    profile_md = _PROFILE_MD.read_text(encoding="utf-8") if _PROFILE_MD.exists() else ""
    return {
        "name": str(contact.get("name", "") or ""),
        "title": str(contact.get("title", "") or ""),
        "email": str(contact.get("email", "") or ""),
        "phone": str(contact.get("phone", "") or ""),
        "location": str(contact.get("location", "") or ""),
        "linkedin": str(contact.get("linkedin", "") or ""),
        "github": str(contact.get("github", "") or ""),
        "profile_md": profile_md,
    }


def _migrate_settings_from_files() -> dict[str, Any] | None:
    if not _SETTINGS_YAML.exists():
        return None
    with _SETTINGS_YAML.open(encoding="utf-8") as f:
        s = yaml.safe_load(f) or {}
    search = s.get("search", {})
    scoring = s.get("scoring", {})
    targets = s.get("target_companies", {})
    companies: list[str] = []
    for v in targets.values():
        if isinstance(v, list):
            companies.extend(str(x) for x in v)
    return {
        "keywords": list(search.get("keywords", [])),
        "portal_queries": list(search.get("portal_queries", [])),
        "location": str(search.get("location", "") or ""),
        "contract": str(search.get("contract", "CDI") or "CDI"),
        "experience_max_years": int(search.get("experience_max_years", 3)),
        "salary_min": int(scoring.get("target_salary_min", 0)),
        "salary_max": int(scoring.get("target_salary_max", 0)),
        "target_companies": companies,
        "follow_up_days": int(s.get("follow_up_days", 7)),
    }


def get_profile(conn: psycopg2.extensions.connection, user_id: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(_PROFILE_KEYS)} FROM user_profiles WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    if row is not None:
        return dict(zip(_PROFILE_KEYS, row))
    migrated = _migrate_profile_from_files()
    if migrated:
        save_profile(conn, user_id, migrated)
        return migrated
    return _empty_profile()


def save_profile(
    conn: psycopg2.extensions.connection, user_id: str, data: dict[str, Any]
) -> None:
    cols = ", ".join(_PROFILE_KEYS)
    placeholders = ", ".join(["%s"] * len(_PROFILE_KEYS))
    updates = ", ".join(f"{k} = EXCLUDED.{k}" for k in _PROFILE_KEYS)
    values = tuple(data.get(k, "") for k in _PROFILE_KEYS)
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO user_profiles (user_id, {cols}) VALUES (%s, {placeholders})"
            f" ON CONFLICT (user_id) DO UPDATE SET {updates}",
            (user_id, *values),
        )
    conn.commit()


def get_settings(conn: psycopg2.extensions.connection, user_id: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(_SETTINGS_KEYS)} FROM user_settings WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    if row is not None:
        result = dict(zip(_SETTINGS_KEYS, row))
        for k in ("keywords", "portal_queries", "target_companies"):
            if result[k] is None:
                result[k] = []
        return result
    migrated = _migrate_settings_from_files()
    if migrated:
        save_settings(conn, user_id, migrated)
        return migrated
    return _empty_settings()


def save_settings(
    conn: psycopg2.extensions.connection, user_id: str, data: dict[str, Any]
) -> None:
    cols = ", ".join(_SETTINGS_KEYS)
    placeholders = ", ".join(["%s"] * len(_SETTINGS_KEYS))
    updates = ", ".join(f"{k} = EXCLUDED.{k}" for k in _SETTINGS_KEYS)
    values = (
        data.get("keywords", []),
        data.get("portal_queries", []),
        str(data.get("location", "")),
        str(data.get("contract", "CDI")),
        int(data.get("experience_max_years", 3)),
        int(data.get("salary_min", 0)),
        int(data.get("salary_max", 0)),
        data.get("target_companies", []),
        int(data.get("follow_up_days", 7)),
    )
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO user_settings (user_id, {cols}) VALUES (%s, {placeholders})"
            f" ON CONFLICT (user_id) DO UPDATE SET {updates}",
            (user_id, *values),
        )
    conn.commit()
