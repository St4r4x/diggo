from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
import psycopg2.extensions
import yaml

_CONTACT_YAML = Path(__file__).parent.parent / "config" / "contact.yaml"
_PROFILE_MD = Path(__file__).parent.parent / "config" / "profile.md"
_SETTINGS_YAML = Path(__file__).parent.parent / "config" / "settings.yaml"
_ATS_MAP_YAML = Path(__file__).parent.parent / "config" / "ats_map.yaml"

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
    "enabled_portals",
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
        "enabled_portals": [],
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
    if isinstance(targets, dict):
        for v in targets.values():
            if isinstance(v, list):
                companies.extend(str(x) for x in v)
    elif isinstance(targets, list):
        companies = [str(x) for x in targets]
    return {
        "keywords": list(search.get("keywords", [])),
        "enabled_portals": list(search.get("enabled_portals", [])),
        "location": str(search.get("location", "") or ""),
        "contract": str(search.get("contract", "CDI") or "CDI"),
        "experience_max_years": int(search.get("experience_max_years", 3)),
        "salary_min": int(scoring.get("target_salary_min", 0)),
        "salary_max": int(scoring.get("target_salary_max", 0)),
        "target_companies": companies,
        "follow_up_days": int(s.get("follow_up_days", 7)),
    }


def get_profile(conn: psycopg2.extensions.connection, user_id: str) -> dict[str, Any]:
    # Exception to "caller owns commit": auto-migration path commits once, on first login only.
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
        conn.commit()
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


def get_settings(conn: psycopg2.extensions.connection, user_id: str) -> dict[str, Any]:
    # Exception to "caller owns commit": auto-migration path commits once, on first login only.
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(_SETTINGS_KEYS)} FROM user_settings WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    if row is not None:
        result = dict(zip(_SETTINGS_KEYS, row))
        for k in ("keywords", "enabled_portals", "target_companies"):
            if result[k] is None:
                result[k] = []
        return result
    migrated = _migrate_settings_from_files()
    if migrated:
        save_settings(conn, user_id, migrated)
        conn.commit()
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
        data.get("enabled_portals", []),
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


def _fernet() -> Fernet:
    return Fernet(os.environ["SECRET_KEY"].encode())


def get_hf_token(conn: psycopg2.extensions.connection, user_id: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT hf_token_encrypted FROM user_settings WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    if row is None or row[0] is None:
        return None
    try:
        return _fernet().decrypt(bytes(row[0])).decode()
    except InvalidToken:
        return None


def save_hf_token(
    conn: psycopg2.extensions.connection, user_id: str, token: str
) -> None:
    encrypted = _fernet().encrypt(token.encode())
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_settings (user_id, hf_token_encrypted) VALUES (%s, %s)"
            " ON CONFLICT (user_id) DO UPDATE SET hf_token_encrypted = EXCLUDED.hf_token_encrypted",
            (user_id, psycopg2.Binary(encrypted)),
        )


def delete_hf_token(conn: psycopg2.extensions.connection, user_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE user_settings SET hf_token_encrypted = NULL WHERE user_id = %s",
            (user_id,),
        )


def get_onboarding_state(
    conn: psycopg2.extensions.connection, user_id: str
) -> dict[str, Any]:
    """Compute onboarding completeness live from existing profile/CV/settings/token data."""
    profile = get_profile(conn, user_id)
    cv = get_cv(conn, user_id, lang="fr")
    profile_complete = bool(
        profile["name"].strip()
        and profile["email"].strip()
        and cv["meta"]["summary"].strip()
        and len(cv["experience"]) >= 1
        and len(cv["skills"]) >= 1
    )

    settings = get_settings(conn, user_id)
    search_complete = len(settings["keywords"]) >= 1

    hf_token_complete = get_hf_token(conn, user_id) is not None

    return {
        "profile_complete": profile_complete,
        "search_complete": search_complete,
        "hf_token_complete": hf_token_complete,
        "is_complete": profile_complete and search_complete and hf_token_complete,
    }


def _migrate_ats_from_files() -> list[dict[str, str]] | None:
    if not _ATS_MAP_YAML.exists():
        return None
    with _ATS_MAP_YAML.open(encoding="utf-8") as f:
        entries = yaml.safe_load(f) or []
    return [
        {"name": str(e.get("name", "")), "careers_url": str(e.get("careers_url", ""))}
        for e in entries
    ]


def get_ats_targets(
    conn: psycopg2.extensions.connection, user_id: str
) -> list[dict[str, Any]]:
    # Exception to "caller owns commit": auto-migration path commits once, on first login only.
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, careers_url FROM user_ats_targets WHERE user_id = %s ORDER BY id",
            (user_id,),
        )
        rows = cur.fetchall()
    if rows:
        return [{"id": r[0], "name": r[1], "careers_url": r[2]} for r in rows]
    migrated = _migrate_ats_from_files()
    if migrated:
        for entry in migrated:
            add_ats_target(conn, user_id, entry["name"], entry["careers_url"])
        conn.commit()
        return get_ats_targets(conn, user_id)
    return []


def add_ats_target(
    conn: psycopg2.extensions.connection, user_id: str, name: str, careers_url: str
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_ats_targets (user_id, name, careers_url) VALUES (%s, %s, %s) RETURNING id",
            (user_id, name, careers_url),
        )
        new_id: int = cur.fetchone()[0]
    return new_id


def delete_ats_target(
    conn: psycopg2.extensions.connection, user_id: str, target_id: int
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_ats_targets WHERE id = %s AND user_id = %s",
            (target_id, user_id),
        )


_CV_YAML = Path(__file__).parent.parent / "config" / "cv.yaml"


def _migrate_cv_from_files(lang: str = "fr") -> dict[str, Any] | None:
    if not _CV_YAML.exists():
        return None
    with _CV_YAML.open(encoding="utf-8") as f:
        cv = yaml.safe_load(f) or {}
    data = cv.get(lang, cv.get("fr", {}))
    experience = []
    for i, exp in enumerate(data.get("experience", [])):
        experience.append(
            {
                "title": str(exp.get("title", "")),
                "company": str(exp.get("company", "")),
                "type": str(exp.get("type", "")),
                "period": str(exp.get("period", "")),
                "sort_order": i,
                "bullets": [str(b) for b in exp.get("bullets", [])],
            }
        )
    skill_cats = data.get("skill_categories", {})
    skills = []
    sort_i = 0
    for cat, skill_list in skill_cats.items():
        for skill in skill_list or []:
            skills.append(
                {"category": str(cat), "skill": str(skill), "sort_order": sort_i}
            )
            sort_i += 1
    certifications = [
        {
            "name": str(c.get("name", "")),
            "issuer": str(c.get("issuer", "")),
            "year": c.get("year"),
        }
        for c in data.get("certifications", [])
    ]
    education = [
        {
            "degree": str(e.get("degree", "")),
            "school": str(e.get("school", "")),
            "year": e.get("year"),
        }
        for e in data.get("education", [])
    ]
    projects = [
        {
            "name": str(p.get("name", "")),
            "stack": [str(s) for s in p.get("stack", [])],
            "desc": str(p.get("desc", "")),
            "sort_order": i,
        }
        for i, p in enumerate(data.get("projects", []))
    ]
    languages = [
        {"name": str(lang_name), "sort_order": i}
        for i, lang_name in enumerate(data.get("languages", []))
    ]
    hobbies = [
        {"name": str(hobby), "sort_order": i}
        for i, hobby in enumerate(data.get("hobbies", []))
    ]
    return {
        "summary": str(data.get("summary", "")),
        "experience": experience,
        "skills": skills,
        "certifications": certifications,
        "education": education,
        "projects": projects,
        "languages": languages,
        "hobbies": hobbies,
    }


def get_cv(
    conn: psycopg2.extensions.connection, user_id: str, lang: str = "fr"
) -> dict[str, Any]:
    # Exception to "caller owns commit": auto-migration path commits once, on first login only.
    with conn.cursor() as cur:
        cur.execute(
            "SELECT summary FROM user_cv_meta WHERE user_id = %s AND lang = %s",
            (user_id, lang),
        )
        meta_row = cur.fetchone()
        cur.execute(
            "SELECT id, title, company, type, period, sort_order FROM user_experience"
            " WHERE user_id = %s AND lang = %s ORDER BY sort_order",
            (user_id, lang),
        )
        exp_rows = cur.fetchall()
        exp_ids = [row[0] for row in exp_rows]
        bullets_by_exp: dict[int, list[str]] = {exp_id: [] for exp_id in exp_ids}
        if exp_ids:
            cur.execute(
                "SELECT experience_id, text FROM user_experience_bullets"
                " WHERE experience_id = ANY(%s) ORDER BY experience_id, sort_order",
                (exp_ids,),
            )
            for exp_id, text in cur.fetchall():
                bullets_by_exp[exp_id].append(text)
        experience = [
            {
                "id": exp_id,
                "title": title,
                "company": company,
                "type": etype,
                "period": period,
                "sort_order": sort_order,
                "bullets": bullets_by_exp[exp_id],
            }
            for exp_id, title, company, etype, period, sort_order in exp_rows
        ]
        cur.execute(
            "SELECT id, category, skill, sort_order FROM user_skills"
            " WHERE user_id = %s AND lang = %s ORDER BY sort_order",
            (user_id, lang),
        )
        skills = [
            {"id": r[0], "category": r[1], "skill": r[2], "sort_order": r[3]}
            for r in cur.fetchall()
        ]
        cur.execute(
            "SELECT id, name, issuer, year FROM user_certifications WHERE user_id = %s",
            (user_id,),
        )
        certifications = [
            {"id": r[0], "name": r[1], "issuer": r[2], "year": r[3]}
            for r in cur.fetchall()
        ]
        cur.execute(
            "SELECT id, degree, school, year FROM user_education WHERE user_id = %s AND lang = %s",
            (user_id, lang),
        )
        education = [
            {"id": r[0], "degree": r[1], "school": r[2], "year": r[3]}
            for r in cur.fetchall()
        ]
        cur.execute(
            'SELECT id, name, stack, "desc", sort_order FROM user_projects'
            " WHERE user_id = %s AND lang = %s ORDER BY sort_order",
            (user_id, lang),
        )
        projects = [
            {"id": r[0], "name": r[1], "stack": r[2], "desc": r[3], "sort_order": r[4]}
            for r in cur.fetchall()
        ]
        cur.execute(
            "SELECT id, name, sort_order FROM user_languages"
            " WHERE user_id = %s AND lang = %s ORDER BY sort_order",
            (user_id, lang),
        )
        languages = [
            {"id": r[0], "name": r[1], "sort_order": r[2]} for r in cur.fetchall()
        ]
        cur.execute(
            "SELECT id, name, sort_order FROM user_hobbies"
            " WHERE user_id = %s AND lang = %s ORDER BY sort_order",
            (user_id, lang),
        )
        hobbies = [
            {"id": r[0], "name": r[1], "sort_order": r[2]} for r in cur.fetchall()
        ]

    if not (
        meta_row
        or experience
        or skills
        or certifications
        or education
        or projects
        or languages
        or hobbies
    ):
        migrated = _migrate_cv_from_files(lang)
        if migrated:
            save_cv_meta(conn, user_id, lang, migrated["summary"])
            save_experience(conn, user_id, lang, migrated["experience"])
            save_skills(conn, user_id, lang, migrated["skills"])
            save_certifications(conn, user_id, migrated["certifications"])
            save_education(conn, user_id, lang, migrated["education"])
            save_projects(conn, user_id, lang, migrated["projects"])
            save_languages(conn, user_id, lang, migrated["languages"])
            save_hobbies(conn, user_id, lang, migrated["hobbies"])
            conn.commit()
            return get_cv(conn, user_id, lang)

    return {
        "meta": {"summary": meta_row[0] if meta_row else ""},
        "experience": experience,
        "skills": skills,
        "certifications": certifications,
        "education": education,
        "projects": projects,
        "languages": languages,
        "hobbies": hobbies,
    }


def save_cv_meta(
    conn: psycopg2.extensions.connection, user_id: str, lang: str, summary: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_cv_meta (user_id, lang, summary) VALUES (%s, %s, %s)"
            " ON CONFLICT (user_id, lang) DO UPDATE SET summary = EXCLUDED.summary",
            (user_id, lang, summary),
        )


def save_experience(
    conn: psycopg2.extensions.connection,
    user_id: str,
    lang: str,
    entries: list[dict[str, Any]],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM user_experience WHERE user_id = %s AND lang = %s",
            (user_id, lang),
        )
        old_ids = [r[0] for r in cur.fetchall()]
        if old_ids:
            cur.execute(
                "DELETE FROM user_experience_bullets WHERE experience_id = ANY(%s)",
                (old_ids,),
            )
        cur.execute(
            "DELETE FROM user_experience WHERE user_id = %s AND lang = %s",
            (user_id, lang),
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cur.execute(
                "INSERT INTO user_experience (user_id, lang, title, company, type, period, sort_order)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    user_id,
                    lang,
                    entry.get("title", ""),
                    entry.get("company", ""),
                    entry.get("type", ""),
                    entry.get("period", ""),
                    entry.get("sort_order", 0),
                ),
            )
            exp_id: int = cur.fetchone()[0]
            for i, bullet in enumerate(entry.get("bullets", [])):
                cur.execute(
                    "INSERT INTO user_experience_bullets (experience_id, text, sort_order) VALUES (%s, %s, %s)",
                    (exp_id, bullet, i),
                )


def save_skills(
    conn: psycopg2.extensions.connection,
    user_id: str,
    lang: str,
    entries: list[dict[str, Any]],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_skills WHERE user_id = %s AND lang = %s",
            (user_id, lang),
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cur.execute(
                "INSERT INTO user_skills (user_id, lang, category, skill, sort_order) VALUES (%s, %s, %s, %s, %s)",
                (
                    user_id,
                    lang,
                    entry["category"],
                    entry["skill"],
                    entry.get("sort_order", 0),
                ),
            )


def save_certifications(
    conn: psycopg2.extensions.connection, user_id: str, entries: list[dict[str, Any]]
) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM user_certifications WHERE user_id = %s", (user_id,))
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cur.execute(
                "INSERT INTO user_certifications (user_id, name, issuer, year) VALUES (%s, %s, %s, %s)",
                (user_id, entry["name"], entry.get("issuer", ""), entry.get("year")),
            )


def delete_experience(
    conn: psycopg2.extensions.connection, user_id: str, exp_id: int
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_experience_bullets"
            " WHERE experience_id IN ("
            "   SELECT id FROM user_experience WHERE id = %s AND user_id = %s"
            ")",
            (exp_id, user_id),
        )
        cur.execute(
            "DELETE FROM user_experience WHERE id = %s AND user_id = %s",
            (exp_id, user_id),
        )


def save_education(
    conn: psycopg2.extensions.connection,
    user_id: str,
    lang: str,
    entries: list[dict[str, Any]],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_education WHERE user_id = %s AND lang = %s",
            (user_id, lang),
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cur.execute(
                "INSERT INTO user_education (user_id, lang, degree, school, year) VALUES (%s, %s, %s, %s, %s)",
                (
                    user_id,
                    lang,
                    entry.get("degree", ""),
                    entry.get("school", ""),
                    entry.get("year"),
                ),
            )


def save_projects(
    conn: psycopg2.extensions.connection,
    user_id: str,
    lang: str,
    entries: list[dict[str, Any]],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_projects WHERE user_id = %s AND lang = %s",
            (user_id, lang),
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cur.execute(
                'INSERT INTO user_projects (user_id, lang, name, stack, "desc", sort_order)'
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    user_id,
                    lang,
                    entry.get("name", ""),
                    entry.get("stack", []),
                    entry.get("desc", ""),
                    entry.get("sort_order", 0),
                ),
            )


def save_languages(
    conn: psycopg2.extensions.connection,
    user_id: str,
    lang: str,
    entries: list[dict[str, Any]],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_languages WHERE user_id = %s AND lang = %s",
            (user_id, lang),
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cur.execute(
                "INSERT INTO user_languages (user_id, lang, name, sort_order) VALUES (%s, %s, %s, %s)",
                (user_id, lang, entry.get("name", ""), entry.get("sort_order", 0)),
            )


def save_hobbies(
    conn: psycopg2.extensions.connection,
    user_id: str,
    lang: str,
    entries: list[dict[str, Any]],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_hobbies WHERE user_id = %s AND lang = %s",
            (user_id, lang),
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cur.execute(
                "INSERT INTO user_hobbies (user_id, lang, name, sort_order) VALUES (%s, %s, %s, %s)",
                (user_id, lang, entry.get("name", ""), entry.get("sort_order", 0)),
            )
