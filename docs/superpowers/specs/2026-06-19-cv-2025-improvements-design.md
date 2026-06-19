# CV 2025 Improvements — Design Spec

**Date:** 2026-06-19
**Status:** Approved
**Scope:** `cv.yaml`, `generate_pdf.py`, `templates/cv-fr/`, `templates/cv-en/`, `config/cv.yaml.example`, `tests/test_generate_pdf.py`

---

## Context

The current CV has three weaknesses vs. 2025 ATS/recruiter best practices:
1. `skills` is a flat list — no category grouping, no structure
2. No certifications section (AWS, GCP, Kubernetes are highly valued)
3. `experience` bullets are free text — no structured `stack` field per role

This spec covers the minimum changes to address all three.

---

## Data model — `cv.yaml`

### Skills: flat list → categorised dict

**Before:**
```yaml
skills:
  - Python
  - PyTorch
  - Docker
```

**After:**
```yaml
skill_categories:
  IA/ML:    [PyTorch, HuggingFace, OpenCV]
  Cloud:    [Docker, GCP, Kubernetes]
  Langages: [Python, SQL, Bash]
  Outils:   [Git, FastAPI, MLflow]
```

- The key `skills` is **removed** and replaced by `skill_categories` (breaking change, intentional — `cv.yaml` is gitignored personal data).
- Category names are **free-form strings** chosen by the user (Option A — fixed set offered as example, not enforced).
- Order of categories is preserved (insertion order, YAML dict).

### Certifications: new optional field

```yaml
certifications:
  - name: "Google Cloud Professional ML Engineer"
    issuer: "Google"
    year: 2025
  - name: "AWS Certified Developer"
    issuer: "Amazon"
    year: 2024
```

- Entirely optional — omitting it skips the section in the rendered CV.
- Fields: `name` (string), `issuer` (string), `year` (int).

### Stack per experience entry: new optional field

```yaml
experience:
  - title: "AI/ML Engineer"
    company: "..."
    type: "Alternance"
    period: "..."
    stack: [Python, PyTorch, FastAPI, Docker]
    bullets:
      - "..."
```

- Optional per entry — omitting `stack` on a role simply renders no tags for that role.

---

## `generate_pdf.py` changes

### `build_cv_context` signature

- `skills: list[str]` → `skill_categories: dict[str, list[str]]`
- New parameter: `certifications: list[dict] | None = None` (default `None`)
- `stack` lives inside each `experience` dict — no new top-level parameter needed

### `default_context`

Reads from `cv.yaml`:
```python
skill_categories=cv.get("skill_categories", {}),
certifications=cv.get("certifications", None),
```

### `--highlighted` flag

No signature change. `highlighted_skills` remains `list[str]`. The Jinja2 template iterates over all skills across all categories and checks `skill in highlighted_skills` — same comparison, works transparently.

---

## Templates — `cv-fr/cv.html.j2` and `cv-en/cv.html.j2`

### Skills section (replaces flat grid)

```html
<div class="section">
  <div class="section-title">Compétences</div>  {# or "Skills" in EN #}
  {% for category, items in skill_categories.items() %}
  <div class="skill-category">
    <span class="skill-category-label">{{ category }}</span>
    {% for skill in items %}
    <span class="skill-tag {% if skill in highlighted_skills %}highlight{% endif %}">{{ skill }}</span>
    {% endfor %}
  </div>
  {% endfor %}
</div>
```

### Certifications section (after Skills, before Formation/Education)

```html
{% if certifications %}
<div class="section">
  <div class="section-title">Certifications</div>  {# same label in EN #}
  {% for cert in certifications %}
  <div class="cert-line">
    <span class="cert-name">{{ cert.name }}</span>
    <span class="cert-meta">{{ cert.issuer }} &nbsp;·&nbsp; {{ cert.year }}</span>
  </div>
  {% endfor %}
</div>
{% endif %}
```

### Stack tags per experience entry (after bullets)

```html
{% if job.stack %}
<div class="stack-tags">
  {% for tech in job.stack %}
  <span class="stack-tag">{{ tech }}</span>
  {% endfor %}
</div>
{% endif %}
```

---

## CSS changes (both `cv.css` files)

```css
.skill-category {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
}

.skill-category-label {
  font-size: 8.5pt;
  font-weight: 700;
  color: #444;
  min-width: 70px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.cert-line {
  display: flex;
  justify-content: space-between;
  margin-bottom: 3px;
  font-size: 9.5pt;
}

.cert-meta {
  font-size: 9pt;
  color: #777;
}

.cert-name {
  font-weight: 600;
}

.stack-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 4px;
}

.stack-tag {
  background: #e8f0fe;
  border-radius: 3px;
  padding: 1px 5px;
  font-size: 8pt;
  color: #2a4ab5;
}
```

- `.stack-tag` uses a blue tint to visually distinguish from `.skill-tag` (grey).
- `.skill-category-label` has `min-width: 70px` so categories of different lengths don't misalign tags.

---

## `config/cv.yaml.example`

Updated to use `skill_categories` (replacing `skills`), add `certifications` block, and add `stack` to at least one experience entry — both `fr` and `en` sections.

---

## Tests — `tests/test_generate_pdf.py`

- Replace all calls passing `skills=["Python", ...]` with `skill_categories={"Langages": ["Python", ...]}`.
- Add a test case for `certifications` present vs. absent.
- Add a test case for a job with `stack` vs. without.

---

## Out of scope

- Years of experience per skill (not requested)
- ATS text export (handled by existing `_normalize_for_ats`)
- Any other template or script

---

## File change summary

| File | Change |
|------|--------|
| `config/cv.yaml.example` | Replace `skills` with `skill_categories`, add `certifications`, add `stack` to experience entries |
| `scripts/generate_pdf.py` | `build_cv_context`: `skills→skill_categories`, add `certifications`; `default_context`: read new keys |
| `templates/cv-fr/cv.html.j2` | Update Skills section, add Certifications section, add stack tags in experience loop |
| `templates/cv-en/cv.html.j2` | Same as FR |
| `templates/cv-fr/cv.css` | Add `.skill-category`, `.skill-category-label`, `.cert-line`, `.cert-meta`, `.cert-name`, `.stack-tags`, `.stack-tag` |
| `templates/cv-en/cv.css` | Same as FR |
| `tests/test_generate_pdf.py` | Update fixtures and add new test cases |
