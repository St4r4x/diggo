# Plan 4 — Cover Letter PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cover letter PDF generation (HTML/CSS template + Python script) mirroring the existing CV PDF workflow.

**Architecture:** A Jinja2 HTML template (`templates/cover-letter-fr/`) is rendered to PDF via WeasyPrint, exactly as `generate_pdf.py` does for the CV. A new `scripts/generate_cover_letter.py` exposes `build_cover_letter_context`, `render_html`, `generate_pdf` and a CLI with `--offer`, `--date`, `--context-file` (JSON). The `modes/generate-cover-letter.md` mode is updated to call the script.

**Tech Stack:** Python 3, Jinja2 3.1.4, WeasyPrint 62.3.0, pytest 8.2.2

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `templates/cover-letter-fr/cover-letter.html.j2` | Create | A4 letter layout (sender, date, recipient, subject, body paragraphs) |
| `templates/cover-letter-fr/cover-letter.css` | Create | Print-optimised A4 CSS (matches CV style) |
| `scripts/generate_cover_letter.py` | Create | `build_cover_letter_context`, `render_html`, `generate_pdf`, CLI |
| `tests/test_generate_cover_letter.py` | Create | Unit tests for context builder and HTML renderer |
| `modes/generate-cover-letter.md` | Modify | Add step to call `generate_cover_letter.py` after writing `.md` |

---

### Task 1: HTML/CSS cover letter template

**Files:**
- Create: `templates/cover-letter-fr/cover-letter.html.j2`
- Create: `templates/cover-letter-fr/cover-letter.css`

No automated tests for the template itself — it is visually verified in Task 2.

- [ ] **Step 1: Create the Jinja2 HTML template**

Create `templates/cover-letter-fr/cover-letter.html.j2` with this exact content:

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="cover-letter.css">
</head>
<body>

<div class="sender">
  <div class="sender-name">{{ name }}</div>
  <div class="sender-info">{{ email }} &nbsp;·&nbsp; {{ phone }} &nbsp;·&nbsp; {{ location }}</div>
</div>

<div class="meta">
  <div class="date">{{ date_str }}</div>
  <div class="recipient-block">
    <div class="company">{{ company }}</div>
    {% if role %}<div class="role">{{ role }}</div>{% endif %}
  </div>
</div>

<div class="subject">
  Objet&nbsp;: Candidature — {{ role }}{% if company %} chez {{ company }}{% endif %}
</div>

<div class="salutation">{{ recipient }}</div>

{% for para in paragraphs %}
<p>{{ para }}</p>
{% endfor %}

<div class="closing">
  <p>Dans l'attente de votre retour, je reste disponible pour un entretien.</p>
  <p class="signature">{{ name }}</p>
</div>

</body>
</html>
```

- [ ] **Step 2: Create the CSS stylesheet**

Create `templates/cover-letter-fr/cover-letter.css` with this exact content:

```css
/* Print-optimised A4 cover letter */
@page {
  size: A4;
  margin: 20mm 22mm;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Arial', sans-serif;
  font-size: 10.5pt;
  color: #222;
  line-height: 1.6;
}

.sender { margin-bottom: 20px; }

.sender-name {
  font-size: 13pt;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.sender-info {
  font-size: 9pt;
  color: #555;
  margin-top: 3px;
}

.meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 24px;
}

.date { font-size: 9.5pt; color: #555; }
.company { font-weight: 600; font-size: 10pt; }
.role { font-size: 9.5pt; color: #555; }

.subject {
  font-weight: 700;
  margin-bottom: 20px;
  font-size: 10.5pt;
}

.salutation { margin-bottom: 16px; }

p {
  margin-bottom: 14px;
  text-align: justify;
}

.closing { margin-top: 24px; }

.signature {
  margin-top: 16px;
  font-weight: 700;
}
```

- [ ] **Step 3: Commit the templates**

```bash
git add templates/cover-letter-fr/
git commit -m "feat: add cover letter HTML/CSS template"
```

---

### Task 2: TDD — scripts/generate_cover_letter.py

**Files:**
- Create: `tests/test_generate_cover_letter.py`
- Create: `scripts/generate_cover_letter.py`

Context: The existing CV script is at `scripts/generate_pdf.py`. The pattern is identical: `build_*_context` → `render_html` → `generate_pdf`. The venv is at `.venv/` in the project root; always use `.venv/bin/pytest`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_generate_cover_letter.py`:

```python
"""Tests for generate_cover_letter pure helpers (no PDF write, no filesystem)."""

from scripts.generate_cover_letter import build_cover_letter_context, render_html


def test_build_cover_letter_context_returns_required_keys():
    ctx = build_cover_letter_context(
        name="Arnaud Thery",
        title="AI/ML Engineer",
        email="test@test.com",
        phone="0600000000",
        location="Paris",
        date_str="2026-05-25",
        company="Mistral AI",
        role="AI Engineer",
        recipient="Madame, Monsieur,",
        paragraphs=["Para 1.", "Para 2.", "Para 3."],
    )
    assert ctx["name"] == "Arnaud Thery"
    assert ctx["company"] == "Mistral AI"
    assert ctx["role"] == "AI Engineer"
    assert ctx["paragraphs"] == ["Para 1.", "Para 2.", "Para 3."]


def test_render_html_contains_name_and_company():
    ctx = build_cover_letter_context(
        name="Arnaud Thery",
        title="AI/ML Engineer",
        email="test@test.com",
        phone="0600000000",
        location="Paris",
        date_str="2026-05-25",
        company="Mistral AI",
        role="AI Engineer",
        recipient="Madame, Monsieur,",
        paragraphs=["First paragraph.", "Second paragraph.", "Third paragraph."],
    )
    html = render_html(ctx)
    assert "Arnaud Thery" in html
    assert "Mistral AI" in html
    assert "AI Engineer" in html
    assert "First paragraph." in html


def test_render_html_contains_all_paragraphs():
    paragraphs = ["Para A.", "Para B.", "Para C."]
    ctx = build_cover_letter_context(
        name="Test",
        title="Engineer",
        email="a@b.com",
        phone="0600000000",
        location="Paris",
        date_str="2026-05-25",
        company="Acme",
        role="Dev",
        recipient="Madame, Monsieur,",
        paragraphs=paragraphs,
    )
    html = render_html(ctx)
    for para in paragraphs:
        assert para in html


def test_render_html_empty_role_omits_role_div():
    ctx = build_cover_letter_context(
        name="Test",
        title="Engineer",
        email="a@b.com",
        phone="0600000000",
        location="Paris",
        date_str="2026-05-25",
        company="Acme",
        role="",
        recipient="Madame, Monsieur,",
        paragraphs=["Only para."],
    )
    html = render_html(ctx)
    assert "Acme" in html
    assert 'class="role"' not in html
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/test_generate_cover_letter.py -v
```

Expected: `ImportError: cannot import name 'build_cover_letter_context'`

- [ ] **Step 3: Implement scripts/generate_cover_letter.py**

Create `scripts/generate_cover_letter.py`:

```python
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
        name="Arnaud Thery",
        title="AI/ML Engineer",
        email="St4r4x@gmail.com",
        phone="+33 6 61624819",
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
            company=extra.get("company", ""),
            role=extra.get("role", ""),
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/test_generate_cover_letter.py -v
```

Expected output:
```
PASSED tests/test_generate_cover_letter.py::test_build_cover_letter_context_returns_required_keys
PASSED tests/test_generate_cover_letter.py::test_render_html_contains_name_and_company
PASSED tests/test_generate_cover_letter.py::test_render_html_contains_all_paragraphs
PASSED tests/test_generate_cover_letter.py::test_render_html_empty_role_omits_role_div
4 passed
```

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/ -v
```

Expected: all previously passing tests still pass.

- [ ] **Step 6: Smoke-test the PDF output**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/python scripts/generate_cover_letter.py \
  --offer "test-company" \
  --date "2026-05-25"
```

Expected: `Cover letter generated: output/cover-letter-test-company-2026-05-25.pdf`
Verify the file exists: `ls -lh output/cover-letter-test-company-2026-05-25.pdf`

- [ ] **Step 7: Commit**

```bash
git add scripts/generate_cover_letter.py tests/test_generate_cover_letter.py
git commit -m "feat: add cover letter PDF generator with TDD"
```

---

### Task 3: Update modes/generate-cover-letter.md

**Files:**
- Modify: `modes/generate-cover-letter.md`

The mode currently saves a `.md` only and has no PDF step. We add a step 7 that calls the script, and update step 6 so the output folder matches the existing `output/` convention.

- [ ] **Step 1: Replace the file content**

Write `modes/generate-cover-letter.md` with this exact content:

```markdown
# generate-cover-letter

Write a tailored cover letter for a specific job offer. Called from Claude Code CLI.

## Input

- Job description (pasted) or score report path
- Company name and role title

## Instructions

1. Read `config/profile.md` for Arnaud's background and tone.
2. Read the job description / score report to identify:
   - What the company builds / its mission
   - The 2–3 most important technical requirements
   - Any specific "why us" angle (tech, mission, product, team)
3. Write the cover letter in the language of the job posting (French if French, English if English).
4. Structure: 3 short paragraphs, < 300 words total:
   - **Para 1 (hook):** Why this company specifically — one concrete reason tied to their product or mission. No generic "Je suis passionné par l'IA".
   - **Para 2 (proof):** 2 specific experiences from profile.md that directly address the top 2 requirements. Use numbers or outcomes where possible.
   - **Para 3 (close):** Short, confident close. Mention availability (fin 2026 / dès que possible).
5. Tone: direct, professional, no filler phrases ("Je suis motivé", "passionné", etc.)
6. Save the draft text to `output/<company-slug>-<date>/cover-letter.md` for reference.
7. Build a JSON context file at `/tmp/cl-context.json`:

```json
{
  "company": "<company name>",
  "role": "<role title>",
  "recipient": "Madame, Monsieur,",
  "date_str": "<YYYY-MM-DD>",
  "paragraphs": [
    "<paragraph 1 text>",
    "<paragraph 2 text>",
    "<paragraph 3 text>"
  ]
}
```

8. Generate the PDF:

```bash
python scripts/generate_cover_letter.py \
  --offer "<company-slug>" \
  --date "<YYYY-MM-DD>" \
  --context-file /tmp/cl-context.json
```

9. Confirm: `Cover letter generated: output/cover-letter-<slug>-<date>.pdf`
   Remind the user to open and visually verify the PDF before sending.

## Constraints

- Never mention skills not in `config/profile.md`
- Never use: "Je suis très motivé", "passionné par", "je me permets de", "dans l'espoir de"
- Max 300 words
- Must cite at least one specific project from profile.md by name
```

- [ ] **Step 2: Commit**

```bash
git add modes/generate-cover-letter.md
git commit -m "feat: wire generate-cover-letter mode to PDF script"
```

---

### Task 4: Tag and push

- [ ] **Step 1: Run the full test suite one last time**

```bash
cd /home/missia03/Projects/career-ops-fr
.venv/bin/pytest tests/ -v
```

All tests must pass.

- [ ] **Step 2: Push and tag**

```bash
git push github.com-personal HEAD:master
git tag v0.4.0 -m "Plan 4 complete: cover letter PDF generation"
git push github.com-personal v0.4.0
```

Expected: tag `v0.4.0` visible on `git@github.com-personal:St4r4x/career-ops-fr.git`.
