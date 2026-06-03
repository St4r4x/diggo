#!/usr/bin/env python3
"""Render CV HTML template to PDF using WeasyPrint + Jinja2."""

import argparse
import re as _re
from datetime import date
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

_ATS_REPLACEMENTS: list[tuple[str, str]] = [
    ("—", "--"),  # em-dash
    ("–", "-"),  # en-dash
    ("‘", "'"),  # left single quote
    ("’", "'"),  # right single quote
    ("“", '"'),  # left double quote
    ("”", '"'),  # right double quote
    (" ", " "),  # non-breaking space
    ("​", ""),  # zero-width space
    ("‌", ""),  # zero-width non-joiner
    ("﻿", ""),  # BOM
]

_STYLE_SCRIPT_RE = _re.compile(
    r"(<(?:style|script)[^>]*>)(.*?)(</(?:style|script)>)",
    _re.DOTALL | _re.IGNORECASE,
)


def _normalize_for_ats(html: str) -> str:
    """Replace typographic characters that break ATS parsers, preserving style/script blocks."""
    protected: list[str] = []

    def _protect(m: _re.Match) -> str:
        protected.append(m.group(0))
        return f"\x00PROTECTED{len(protected) - 1}\x00"

    masked = _STYLE_SCRIPT_RE.sub(_protect, html)
    for old, new in _ATS_REPLACEMENTS:
        masked = masked.replace(old, new)
    for i, block in enumerate(protected):
        masked = masked.replace(f"\x00PROTECTED{i}\x00", block)
    return masked


TEMPLATE_DIR_FR = Path(__file__).parent.parent / "templates" / "cv-fr"
TEMPLATE_DIR_EN = Path(__file__).parent.parent / "templates" / "cv-en"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
_CONTACT_FILE = Path(__file__).parent.parent / "config" / "contact.yaml"
_CV_FILE = Path(__file__).parent.parent / "config" / "cv.yaml"


def _load_contact() -> dict:
    if _CONTACT_FILE.exists():
        with _CONTACT_FILE.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {}


def _load_cv(lang: str = "fr") -> dict:
    if _CV_FILE.exists():
        with _CV_FILE.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
            return data.get(lang, data.get("fr", {}))
    return {}


def build_cv_context(
    name: str,
    title: str,
    email: str,
    phone: str,
    location: str,
    summary: str,
    experience: list[dict],
    skills: list[str],
    highlighted_skills: list[str],
    education: list[dict],
    languages: list[str],
    linkedin: str = "",
    github: str = "",
    hobbies: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "title": title,
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": linkedin,
        "github": github,
        "summary": summary,
        "experience": experience,
        "skills": skills,
        "highlighted_skills": highlighted_skills,
        "education": education,
        "languages": languages,
        "hobbies": hobbies or [],
    }


def render_html(context: dict, lang: str = "fr") -> str:
    template_dir = TEMPLATE_DIR_EN if lang == "en" else TEMPLATE_DIR_FR
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("cv.html.j2")
    return template.render(**context)


def generate_pdf(context: dict, offer: str, output_date: str, lang: str = "fr") -> Path:
    template_dir = TEMPLATE_DIR_EN if lang == "en" else TEMPLATE_DIR_FR
    slug = offer.lower().replace(" ", "-")
    out_dir = OUTPUT_DIR / f"{slug}-{output_date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "-en" if lang == "en" else ""
    output_path = out_dir / f"cv-{slug}-{output_date}{suffix}.pdf"
    html_content = _normalize_for_ats(render_html(context, lang=lang))
    css_path = template_dir / "cv.css"
    HTML(string=html_content, base_url=str(template_dir)).write_pdf(
        str(output_path),
        stylesheets=[str(css_path)],
    )
    return output_path


def default_context(lang: str = "fr") -> dict:
    """Load CV context from config/cv.yaml (gitignored). Falls back to empty values if missing."""
    c = _load_contact()
    cv = _load_cv(lang)
    location = c.get("location", "")
    if lang == "en":
        location = location.replace("disponible fin 2026", "available end of 2026")
    return build_cv_context(
        name=c.get("name", "Your Name"),
        title=c.get("title", "AI/ML Engineer"),
        email=c.get("email", "you@example.com"),
        phone=c.get("phone", ""),
        location=location,
        linkedin=c.get("linkedin", ""),
        github=c.get("github", ""),
        summary=cv.get("summary", ""),
        experience=cv.get("experience", []),
        skills=cv.get("skills", []),
        highlighted_skills=[],
        education=cv.get("education", []),
        languages=cv.get("languages", []),
        hobbies=cv.get("hobbies", []),
    )


def default_context_en() -> dict:
    """Kept for backwards compatibility — delegates to default_context(lang='en')."""
    return default_context(lang="en")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate tailored CV PDF")
    parser.add_argument(
        "--offer", required=True, help="Company or offer name (used in filename)"
    )
    parser.add_argument(
        "--date",
        default=str(date.today()),
        help="Date string for filename (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--highlighted",
        nargs="*",
        default=[],
        help="Skills to highlight in the CV",
    )
    parser.add_argument(
        "--lang",
        choices=["fr", "en"],
        default="fr",
        help="CV language: fr (default) or en",
    )
    args = parser.parse_args()

    ctx = default_context(lang=args.lang)
    ctx["highlighted_skills"] = args.highlighted
    path = generate_pdf(ctx, offer=args.offer, output_date=args.date, lang=args.lang)
    print(f"PDF generated: {path}")
