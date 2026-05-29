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


TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "cv-fr"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
_CONTACT_FILE = Path(__file__).parent.parent / "config" / "contact.yaml"


def _load_contact() -> dict:
    if _CONTACT_FILE.exists():
        with _CONTACT_FILE.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
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
    }


def render_html(context: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("cv.html.j2")
    return template.render(**context)


def generate_pdf(context: dict, offer: str, output_date: str) -> Path:
    slug = offer.lower().replace(" ", "-")
    out_dir = OUTPUT_DIR / f"{slug}-{output_date}"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"cv-{slug}-{output_date}.pdf"
    html_content = _normalize_for_ats(render_html(context))
    css_path = TEMPLATE_DIR / "cv.css"
    HTML(string=html_content, base_url=str(TEMPLATE_DIR)).write_pdf(
        str(output_path),
        stylesheets=[str(css_path)],
    )
    return output_path


def default_context() -> dict:
    c = _load_contact()
    return build_cv_context(
        name=c.get("name", "Your Name"),
        title=c.get("title", "AI/ML Engineer"),
        email=c.get("email", "you@example.com"),
        phone=c.get("phone", ""),
        location=c.get("location", ""),
        linkedin=c.get("linkedin", ""),
        github=c.get("github", ""),
        summary=(
            "AI/ML Engineer avec expérience en production : Computer Vision, LLM/RAG, "
            "inférence edge. Alternance chez NeuralVision (2023–2026). "
            "Master of Science IA (2026). Ancienne carrière en management d'équipe (8 ans)."
        ),
        experience=[
            {
                "title": "AI/ML Engineer",
                "company": "NeuralVision",
                "type": "Alternance",
                "period": "Janvier 2025 – Présent",
                "bullets": [
                    "Système d'inférence edge temps réel sur Jetson Orin NX (ARM64) — détection de chute, action recognition",
                    "Pipeline de benchmark YOLO + RTMPose pour optimiser le F1-score sur détection de posture",
                    "Fine-tuning VideoMAE sur AWS SageMaker Spot (A10G, bf16) avec S3 manifests",
                    "Outil d'annotation multi-utilisateurs (FiftyOne + SQLite)",
                    "CI/CD GitHub Actions, Docker multi-arch, GHCR",
                ],
            },
            {
                "title": "AI Designer",
                "company": "NeuralVision",
                "type": "Alternance",
                "period": "Septembre 2023 – Janvier 2025",
                "bullets": [
                    "Pipelines Computer Vision avec OpenMMLab et Vision Transformers",
                    "Fine-tuning de modèles, analyse de données",
                ],
            },
            {
                "title": "AI Developer",
                "company": "GoodBarber",
                "type": "Stage",
                "period": "Avril 2023 – Juin 2023",
                "bullets": [
                    "Intégration LLM dans un backend Django/Python",
                    "Tests unitaires, Docker",
                ],
            },
            {
                "title": "Responsable de rayon",
                "company": "Fnac Ajaccio",
                "type": "CDI",
                "period": "Avril 2015 – Septembre 2023",
                "bullets": [
                    "Management d'équipe, gestion des stocks, reporting, planning",
                ],
            },
        ],
        skills=[
            "Python",
            "PyTorch",
            "HuggingFace Transformers",
            "VideoMAE",
            "YOLO v11",
            "OpenMMLab",
            "Vision Transformer",
            "RTMPose",
            "LLM/RAG",
            "FastAPI",
            "Docker",
            "CI/CD",
            "GitHub Actions",
            "AWS SageMaker",
            "MLflow",
            "Jetson Orin NX",
            "Playwright",
            "Agile/Scrum",
        ],
        highlighted_skills=[],
        education=[
            {
                "degree": "Master of Science BIHAR",
                "school": "Aflokkat / ESIA",
                "period": "2024–2026",
            },
            {
                "degree": "Web and AI Designer Certification",
                "school": "Aflokkat / ESIA",
                "period": "2023–2024",
            },
            {
                "degree": "AI Developer Certification",
                "school": "Aflokkat / ESIA",
                "period": "2022–2023",
            },
        ],
        languages=["Français (natif)", "Anglais (professionnel)"],
    )


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
    args = parser.parse_args()

    ctx = default_context()
    ctx["highlighted_skills"] = args.highlighted
    path = generate_pdf(ctx, offer=args.offer, output_date=args.date)
    print(f"PDF generated: {path}")
