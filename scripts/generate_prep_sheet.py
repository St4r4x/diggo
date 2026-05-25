#!/usr/bin/env python3
"""Render interview prep sheet HTML template to PDF using WeasyPrint + Jinja2."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "prep-sheet-fr"
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def build_prep_sheet_context(
    company: str,
    role: str,
    date_str: str,
    company_summary: str,
    tech_stack: list[str],
    questions: list[dict],
) -> dict:
    return {
        "company": company,
        "role": role,
        "date_str": date_str,
        "company_summary": company_summary,
        "tech_stack": tech_stack,
        "questions": questions,
    }


def render_html(context: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("prep-sheet.html.j2")
    return template.render(**context)


def generate_pdf(context: dict, offer: str, output_date: str) -> Path:
    slug = offer.lower().replace(" ", "-")
    out_dir = OUTPUT_DIR / f"{slug}-{output_date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"prep-sheet-{slug}-{output_date}.pdf"
    html_content = render_html(context)
    css_path = TEMPLATE_DIR / "prep-sheet.css"
    HTML(string=html_content, base_url=str(TEMPLATE_DIR)).write_pdf(
        str(output_path),
        stylesheets=[str(css_path)],
    )
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate interview prep sheet PDF")
    parser.add_argument("--offer", required=True, help="Company or offer slug")
    parser.add_argument("--date", default=str(date.today()), help="Date YYYY-MM-DD")
    parser.add_argument(
        "--context-file",
        required=True,
        metavar="PATH",
        help="JSON: {company, role, date_str, company_summary, tech_stack, questions}",
    )
    args = parser.parse_args()

    with open(args.context_file, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    ctx = build_prep_sheet_context(
        company=data["company"],
        role=data["role"],
        date_str=data.get("date_str", args.date),
        company_summary=data.get("company_summary", ""),
        tech_stack=data.get("tech_stack", []),
        questions=data.get("questions", []),
    )
    path = generate_pdf(ctx, offer=args.offer, output_date=args.date)
    print(f"Prep sheet generated: {path}")
