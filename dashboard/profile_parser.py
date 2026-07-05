from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import psycopg2.extensions
import yaml

import user_data

_PROFILE_MD = Path(__file__).parent.parent / "config" / "profile.md"
_CONTACT_YAML = Path(__file__).parent.parent / "config" / "contact.yaml"


def _parse_contact(path: Path) -> dict[str, str]:
    if not path.exists():
        return {
            "name": "",
            "title": "",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin": "",
            "github": "",
        }
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {
        k: str(data.get(k, "") or "")
        for k in ("name", "title", "email", "phone", "location", "linkedin", "github")
    }


def _split_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current = line[3:].strip()
            lines = []
        elif current is not None:
            lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return sections


def _parse_experience(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    heading_re = re.compile(r"^### (.+?) — (.+?) \((.+?), (.+)\)$")
    for line in text.splitlines():
        m = heading_re.match(line)
        if m:
            if current is not None:
                entries.append(current)
            current = {
                "title": m.group(1).strip(),
                "company": m.group(2).strip(),
                "type": m.group(3).strip(),
                "period": m.group(4).strip(),
                "bullets": [],
            }
        elif line.startswith("- ") and current is not None:
            current["bullets"].append(line[2:].strip())
    if current is not None:
        entries.append(current)
    return entries


def _parse_skills(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("### "):
            current = line[4:].strip()
            result[current] = []
        elif line.startswith("- ") and current is not None:
            result[current].append(line[2:].strip())
    return result


def _parse_education(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    edu_re = re.compile(r"^- \*\*(.+?)\*\* — (.+?) \((.+?)\)$")
    for line in text.splitlines():
        m = edu_re.match(line)
        if m:
            entries.append(
                {
                    "degree": m.group(1).strip(),
                    "school": m.group(2).strip(),
                    "period": m.group(3).strip(),
                }
            )
    return entries


def _parse_projects(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    proj_re = re.compile(r"^- \*\*(.+?)\*\*: (.+)$")
    for line in text.splitlines():
        m = proj_re.match(line)
        if m:
            entries.append(
                {
                    "name": m.group(1).strip(),
                    "description": m.group(2).strip(),
                }
            )
    return entries


def _parse_profile_md(path: Path) -> dict[str, Any]:
    empty: dict[str, Any] = {
        "summary": "",
        "experience": [],
        "skills": {},
        "education": [],
        "certifications": [],
        "projects": [],
    }
    if not path.exists():
        return empty
    with path.open(encoding="utf-8") as f:
        text = f.read()
    sections = _split_sections(text)
    return {
        "summary": sections.get("Summary", "").strip(),
        "experience": _parse_experience(sections.get("Experience", "")),
        "skills": _parse_skills(sections.get("Skills", "")),
        "education": _parse_education(sections.get("Education", "")),
        "certifications": [
            line[2:].strip()
            for line in sections.get("Certifications & Training", "").splitlines()
            if line.startswith("- ")
        ],
        "projects": _parse_projects(sections.get("Personal Projects", "")),
    }


def _load_profile_from_files() -> dict[str, Any]:
    contact = _parse_contact(_CONTACT_YAML)
    md_data = _parse_profile_md(_PROFILE_MD)
    return {"contact": contact, **md_data}


def _serialize_profile_md(data: dict[str, Any]) -> str:
    c = data.get("contact", {})
    lines: list[str] = [
        f"# Profile — {c.get('name', '')}",
        "",
        "## Contact",
        f"- Email: {c.get('email', '')}",
        f"- Phone: {c.get('phone', '')}",
        f"- Location: {c.get('location', '')}",
        f"- LinkedIn: {c.get('linkedin', '')}",
        f"- GitHub: {c.get('github', '')}",
        "",
        "## Summary",
        data.get("summary", ""),
        "",
        "## Experience",
        "",
    ]
    for exp in data.get("experience", []):
        lines.append(
            f"### {exp['title']} — {exp['company']} ({exp['type']}, {exp['period']})"
        )
        for b in exp.get("bullets", []):
            lines.append(f"- {b}")
        lines.append("")

    lines += ["## Education"]
    for edu in data.get("education", []):
        lines.append(f"- **{edu['degree']}** — {edu['school']} ({edu['period']})")
    lines.append("")

    lines += ["## Certifications & Training"]
    for cert in data.get("certifications", []):
        lines.append(f"- {cert}")
    lines.append("")

    lines += ["## Skills", ""]
    for category, skills in data.get("skills", {}).items():
        lines.append(f"### {category}")
        for skill in skills:
            lines.append(f"- {skill}")
        lines.append("")

    lines += ["## Personal Projects", ""]
    for proj in data.get("projects", []):
        lines.append(f"- **{proj['name']}**: {proj['description']}")
    lines.append("")

    return "\n".join(lines)


def _save_profile_to_files(data: dict[str, Any]) -> None:
    c = data.get("contact", {})
    contact_data = {
        k: c.get(k, "")
        for k in ("name", "title", "email", "phone", "location", "linkedin", "github")
    }
    _CONTACT_YAML.parent.mkdir(parents=True, exist_ok=True)
    with _CONTACT_YAML.open("w", encoding="utf-8") as f:
        yaml.dump(contact_data, f, allow_unicode=True, default_flow_style=False)
    md_content = _serialize_profile_md(data)
    _PROFILE_MD.parent.mkdir(parents=True, exist_ok=True)
    with _PROFILE_MD.open("w", encoding="utf-8") as f:
        f.write(md_content)


def load_profile(conn: psycopg2.extensions.connection, user_id: str) -> dict[str, Any]:
    profile = user_data.get_profile(conn, user_id)
    return {
        "contact": {
            k: profile[k]
            for k in (
                "name",
                "title",
                "email",
                "phone",
                "location",
                "linkedin",
                "github",
            )
        },
        "profile_md": profile["profile_md"],
        # ponytail: compat shim — profile.html partials still use these; cleared in Task 7
        "summary": "",
        "experience": [],
        "skills": {},
        "education": [],
        "certifications": [],
        "projects": [],
    }


def save_profile(
    conn: psycopg2.extensions.connection, user_id: str, data: dict[str, Any]
) -> None:
    contact = data.get("contact", {})
    user_data.save_profile(
        conn,
        user_id,
        {
            "name": contact.get("name", ""),
            "title": contact.get("title", ""),
            "email": contact.get("email", ""),
            "phone": contact.get("phone", ""),
            "location": contact.get("location", ""),
            "linkedin": contact.get("linkedin", ""),
            "github": contact.get("github", ""),
            "profile_md": data.get("profile_md", ""),
        },
    )
