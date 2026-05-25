#!/usr/bin/env python3
"""Render cover letter HTML template to PDF using WeasyPrint + Jinja2."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "cover-letter-fr"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


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
    }


def render_html(context: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("cover-letter.html.j2")
    return template.render(**context)


def generate_pdf(context: dict, offer: str, output_date: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = offer.lower().replace(" ", "-")
    output_path = OUTPUT_DIR / f"cover-letter-{slug}-{output_date}.pdf"
    html_content = render_html(context)
    css_path = TEMPLATE_DIR / "cover-letter.css"
    HTML(string=html_content, base_url=str(TEMPLATE_DIR)).write_pdf(
        str(output_path),
        stylesheets=[str(css_path)],
    )
    return output_path


def default_context(company: str = "Mistral AI", role: str = "AI Engineer") -> dict:
    return build_cover_letter_context(
        name="Your Name",
        title="AI/ML Engineer",
        email="you@example.com",
        phone="+33 6 00 00 00 00",
        location="Paris (disponible fin 2026)",
        date_str=str(date.today()),
        company=company,
        role=role,
        recipient="Madame, Monsieur,",
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
            "{company, role, recipient, paragraphs, date_str}"
        ),
    )
    args = parser.parse_args()

    if args.context_file:
        with open(args.context_file, "r", encoding="utf-8") as fh:
            extra = json.load(fh)
        ctx = default_context(
            company=extra.get("company") or "Mistral AI",
            role=extra.get("role") or "AI Engineer",
        )
        if "recipient" in extra:
            ctx["recipient"] = extra["recipient"]
        if "paragraphs" in extra:
            ctx["paragraphs"] = extra["paragraphs"]
        if "date_str" in extra:
            ctx["date_str"] = extra["date_str"]
    else:
        ctx = default_context()

    path = generate_pdf(ctx, offer=args.offer, output_date=args.date)
    print(f"Cover letter generated: {path}")
