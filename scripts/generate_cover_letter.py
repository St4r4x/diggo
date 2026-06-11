#!/usr/bin/env python3
"""Render cover letter HTML template to PDF using WeasyPrint + Jinja2."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML


TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "cover-letter-fr"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
_CONTACT_FILE = Path(__file__).parent.parent / "config" / "contact.yaml"


def _load_contact() -> dict:
    if _CONTACT_FILE.exists():
        with _CONTACT_FILE.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {}


def build_cover_letter_context(
    name: str,
    title: str,
    email: str,
    phone: str,
    location: str,
    date_str: str,
    company: str,
    role: str,
    recipient: str,
    paragraphs: list[str],
    lang: str = "fr",
) -> dict:
    return {
        "name": name,
        "title": title,
        "email": email,
        "phone": phone,
        "location": location,
        "date_str": date_str,
        "company": company,
        "role": role,
        "recipient": recipient,
        "paragraphs": paragraphs,
        "lang": lang,
    }


def _normalize_for_ats(html: str) -> str:
    """Return HTML unchanged — hook reserved for future ATS sanitisation."""
    return html


def render_html(context: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("cover-letter.html.j2")
    return template.render(**context)


def generate_pdf(context: dict, offer: str, output_date: str) -> Path:
    slug = offer.lower().replace(" ", "-")
    out_dir = OUTPUT_DIR / f"{slug}-{output_date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"cover-letter-{slug}-{output_date}.pdf"
    html_content = _normalize_for_ats(render_html(context))
    css_path = TEMPLATE_DIR / "cover-letter.css"
    HTML(string=html_content, base_url=str(TEMPLATE_DIR)).write_pdf(
        str(output_path),
        stylesheets=[str(css_path)],
    )
    return output_path


def default_context(
    company: str = "Mistral AI", role: str = "AI Engineer", lang: str = "fr"
) -> dict:
    c = _load_contact()
    location = c.get("location", "")
    if lang == "en":
        location = location.replace("disponible fin 2026", "available end of 2026")
    return build_cover_letter_context(
        name=c.get("name", "Your Name"),
        title=c.get("title", "AI/ML Engineer"),
        email=c.get("email", "you@example.com"),
        phone=c.get("phone", ""),
        location=location,
        date_str=str(date.today()),
        company=company,
        role=role,
        recipient="Madame, Monsieur," if lang == "fr" else "Dear Hiring Team,",
        paragraphs=[
            (
                "Exemple de paragraphe d'accroche — à personnaliser selon "
                "l'entreprise et le poste visé."
            ),
            (
                "Exemple de paragraphe de preuves — deux expériences concrètes "
                "alignées sur les exigences du poste."
            ),
            (
                "Disponible dès fin 2026, je serais ravi d'échanger sur ce poste "
                "lors d'un entretien."
            ),
        ],
        lang=lang,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate tailored cover letter PDF")
    parser.add_argument(
        "--offer", required=True, help="Company or offer slug (used in filename)"
    )
    parser.add_argument(
        "--date", default=str(date.today()), help="Date string YYYY-MM-DD"
    )
    parser.add_argument(
        "--context-file",
        default=None,
        metavar="PATH",
        help=(
            "JSON file with cover letter content: "
            "{company, role, recipient, paragraphs, date_str, lang}"
        ),
    )
    parser.add_argument(
        "--lang",
        choices=["fr", "en"],
        default="fr",
        help="Letter language: fr (default) or en",
    )
    args = parser.parse_args()

    if args.context_file:
        with open(args.context_file, "r", encoding="utf-8") as fh:
            extra = json.load(fh)
        lang = extra.get("lang") or args.lang
        ctx = default_context(
            company=extra.get("company") or "Mistral AI",
            role=extra.get("role") or "AI Engineer",
            lang=lang,
        )
        if "recipient" in extra:
            ctx["recipient"] = extra["recipient"]
        if "paragraphs" in extra:
            ctx["paragraphs"] = extra["paragraphs"]
        if "date_str" in extra:
            ctx["date_str"] = extra["date_str"]
        if "subject" in extra:
            ctx["subject"] = extra["subject"]
        if "closing_line" in extra:
            ctx["closing_line"] = extra["closing_line"]
    else:
        ctx = default_context(lang=args.lang)

    path = generate_pdf(ctx, offer=args.offer, output_date=args.date)
    print(f"Cover letter generated: {path}")
