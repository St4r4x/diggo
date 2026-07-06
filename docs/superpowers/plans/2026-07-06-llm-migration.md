# LLM Migration — Server-Side Candidature Prep — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Claude-Code-CLI-driven `modes/prepare-candidature.md` workflow with a server-side pipeline: a dashboard button that calls an LLM (Groq, Gemini fallback) to analyze an offer, rewrite the CV summary, write a grounded cover letter, and generate an interview prep sheet, then renders all three PDFs in-process via `POST /offers/{offer_id}/prepare`.

**Architecture:** New module `dashboard/llm.py` holds a thin `call_llm()` client (Groq via the `openai` SDK, transparent fallback to Gemini) plus four phase functions returning typed dataclasses. `dashboard/app.py` gets one new route that runs the four phases in sequence, feeds the results into the existing (already-pure) `build_*_context()`/`generate_pdf()` functions in `scripts/generate_pdf.py`, `scripts/generate_cover_letter.py`, `scripts/generate_prep_sheet.py`, and writes `cv_path`/`cover_letter_path`/`prep_sheet_path` to the `applications` row only after all three PDFs render.

**Tech Stack:** Python 3.11+, FastAPI/HTMX, psycopg2, `openai` SDK (pointed at Groq's OpenAI-compatible endpoint), `google-generativeai` (Gemini fallback), WeasyPrint/Jinja2 (unchanged).

## Global Constraints

- New deps only: `openai`, `google-generativeai`. No new frameworks.
- Synchronous route — no async job/polling pattern.
- All-or-nothing DB write: `cv_path`/`cover_letter_path`/`prep_sheet_path` only updated after all PDFs render successfully.
- Never invent data: any skill/experience the LLM references must exist in the user's own DB-backed CV. Enforced in code (Phase 2 drops unknown skills silently, Phase 3 raises `GroundingError` on unrecoverable invalid citations).
- CV generated in French by default; English only if `OfferAnalysis.requires_english_cv` is true.
- Cover letter language mirrors `OfferAnalysis.offer_language`.
- Cover letter style rules (see `feedback_cover_letter_style` memory and `/home/missia03/Projects/career-ops-fr/CLAUDE.md`): **no em-dashes or en-dashes**, no hollow phrases, mandatory career-pivot sentence, < 300 words, closing "Cordialement,"/"Best regards,". The mandatory pivot sentence from `modes/prepare-candidature.md` originally used em-dashes — every prompt constant in this plan uses the dash-free rewrite instead.
- `scripts/*` modules are imported from `dashboard/app.py` with **local imports inside the route function** (matches the existing convention at `dashboard/app.py:738` — `from scripts.import_offers import (...)` — not top-level imports).
- Python conventions: type hints on all signatures, `pathlib.Path` over `os.path`, f-strings, no bare `except:`, stdlib → third-party → local import order.

---

### Task 1: `prep_sheet_path` column — migration, db.py, test fixture

**Files:**
- Create: `alembic/versions/0003_prep_sheet_path.py`
- Modify: `dashboard/db.py` (`_COLS` tuple, `update()`'s `allowed` set)
- Modify: `tests/test_dashboard_app.py` (`_CREATE_TEMP` schema, `_insert_row` helper)
- Test: `tests/test_dashboard_app.py::TestOfferDetail::test_offer_detail_includes_prep_sheet_path` (new)

**Interfaces:**
- Produces: `applications.prep_sheet_path` column (TEXT, default `""`), readable/writable via `db.get_by_id()` / `db.update()` like `cv_path`/`cover_letter_path`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dashboard_app.py`, inside the existing `class TestOfferDetail:` (find it with `grep -n "class TestOfferDetail" tests/test_dashboard_app.py` — add the test as the last method in that class, matching its existing style of using `client_with_data`):

```python
    def test_offer_detail_includes_prep_sheet_path(
        self, client_with_data: TestClient
    ) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        db.update(1, {"prep_sheet_path": "output/acme-2026-07-06/prep-sheet.pdf"}, user_id=TEST_USER_ID)
        r = client_with_data.get("/offers/1")
        assert r.status_code == 200
        offer = db.get_by_id(1, user_id=TEST_USER_ID)
        assert offer["prep_sheet_path"] == "output/acme-2026-07-06/prep-sheet.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_app.py::TestOfferDetail::test_offer_detail_includes_prep_sheet_path -v`
Expected: FAIL — `psycopg2.errors.UndefinedColumn: column "prep_sheet_path" of relation "applications" does not exist` (the test temp table doesn't have the column yet, and `db.update()` doesn't whitelist it).

- [ ] **Step 3: Add the column to the test fixture schema**

In `tests/test_dashboard_app.py`, in `_CREATE_TEMP`, add the column right after `cover_letter_path`:

```python
    cv_path TEXT NOT NULL DEFAULT '',
    cover_letter_path TEXT NOT NULL DEFAULT '',
    prep_sheet_path TEXT NOT NULL DEFAULT '',
    follow_up_date TEXT,
```

- [ ] **Step 4: Wire the column into `dashboard/db.py`**

In `dashboard/db.py`, update `_COLS`:

```python
_COLS = (
    "id",
    "company",
    "role",
    "offer_url",
    "detection_date",
    "score_grade",
    "score_value",
    "status",
    "send_date",
    "contacts",
    "notes",
    "cv_path",
    "cover_letter_path",
    "prep_sheet_path",
    "follow_up_date",
    "description",
    "portal",
)
```

And in `DB.update()`, add `"prep_sheet_path"` to the `allowed` set (right after `"cover_letter_path"`):

```python
        allowed = {
            "company",
            "role",
            "offer_url",
            "detection_date",
            "score_grade",
            "score_value",
            "status",
            "send_date",
            "contacts",
            "notes",
            "cv_path",
            "cover_letter_path",
            "prep_sheet_path",
            "follow_up_date",
            "description",
            "portal",
        }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_dashboard_app.py::TestOfferDetail::test_offer_detail_includes_prep_sheet_path -v`
Expected: PASS

- [ ] **Step 6: Create the Alembic migration**

Create `alembic/versions/0003_prep_sheet_path.py`:

```python
"""Add prep_sheet_path to applications

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("prep_sheet_path", sa.Text, nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("applications", "prep_sheet_path")
```

- [ ] **Step 7: Apply the migration to the local dev database**

Run: `alembic upgrade head`
Expected: `Running upgrade 0002 -> 0003, Add prep_sheet_path to applications`

- [ ] **Step 8: Run the full test suite**

Run: `pytest`
Expected: all tests PASS (no regressions from the `_COLS`/`allowed` changes — every other test in `tests/test_dashboard_app.py` uses the same `_CREATE_TEMP` table, now with one extra column defaulted to `''`).

- [ ] **Step 9: Update CHANGELOG.md**

Add under `## 2026-07-06` → `### Added`:

```markdown
- `alembic/versions/0003_prep_sheet_path.py` — adds `applications.prep_sheet_path` column, needed for the upcoming server-side candidature-prep pipeline (Group 1 of the deployment roadmap)
```

- [ ] **Step 10: Commit**

```bash
git add alembic/versions/0003_prep_sheet_path.py dashboard/db.py tests/test_dashboard_app.py CHANGELOG.md
git commit -m "feat: add applications.prep_sheet_path column"
```

---

### Task 2: `dashboard/llm.py` — LLM client foundation (Groq + Gemini fallback)

**Files:**
- Create: `dashboard/llm.py`
- Test: `tests/test_llm.py` (new)

**Interfaces:**
- Produces: `call_llm(system_prompt: str, user_prompt: str, *, json_schema: dict | None = None) -> str`, `class LLMError(Exception)`, `class GroundingError(Exception)`. These are consumed by every phase function in Tasks 3-6 and by the route in Task 7.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

import llm


def test_call_llm_uses_groq_when_it_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "_call_groq", lambda *a, **k: "groq answer")

    def _fail_gemini(*a: object, **k: object) -> str:
        raise AssertionError("gemini should not be called when groq succeeds")

    monkeypatch.setattr(llm, "_call_gemini", _fail_gemini)

    result = llm.call_llm("system", "user")
    assert result == "groq answer"


def test_call_llm_falls_back_to_gemini_on_groq_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_groq(*a: object, **k: object) -> str:
        raise llm.OpenAIError("groq is down")

    monkeypatch.setattr(llm, "_call_groq", _fail_groq)
    monkeypatch.setattr(llm, "_call_gemini", lambda *a, **k: "gemini answer")

    result = llm.call_llm("system", "user")
    assert result == "gemini answer"


def test_call_llm_raises_llm_error_when_both_providers_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_groq(*a: object, **k: object) -> str:
        raise llm.OpenAIError("groq is down")

    def _fail_gemini(*a: object, **k: object) -> str:
        raise RuntimeError("gemini is down")

    monkeypatch.setattr(llm, "_call_groq", _fail_groq)
    monkeypatch.setattr(llm, "_call_gemini", _fail_gemini)

    with pytest.raises(llm.LLMError):
        llm.call_llm("system", "user")


def test_call_llm_appends_json_schema_hint_to_user_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_prompts = []

    def _capture(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
        seen_prompts.append(user_prompt)
        return "{}"

    monkeypatch.setattr(llm, "_call_groq", _capture)
    llm.call_llm("system", "user", json_schema={"foo": "bar"})
    assert '"foo": "bar"' in seen_prompts[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm'`

- [ ] **Step 3: Write the implementation**

Create `dashboard/llm.py`:

```python
"""LLM client and phase functions for server-side candidature prep.

Groq (llama-3.3-70b-versatile) is the primary provider. On any Groq failure
(timeout, 5xx, quota) this falls back transparently to Gemini Flash.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import google.generativeai as genai
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

_GROQ_MODEL = "llama-3.3-70b-versatile"
_GEMINI_MODEL = "gemini-2.0-flash"


class LLMError(Exception):
    """Raised when both Groq and Gemini fail to answer."""


class GroundingError(Exception):
    """Raised when a cover letter still cites an unknown experience_id after retry."""


def _call_groq(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    client = OpenAI(
        api_key=os.environ["GROQ_API_KEY"],
        base_url="https://api.groq.com/openai/v1",
    )
    kwargs: dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(
        model=_GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )
    return response.choices[0].message.content or ""


def _call_gemini(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    generation_config = {"response_mime_type": "application/json"} if json_mode else {}
    model = genai.GenerativeModel(
        _GEMINI_MODEL,
        system_instruction=system_prompt,
        generation_config=generation_config,
    )
    response = model.generate_content(user_prompt)
    return response.text or ""


def call_llm(
    system_prompt: str, user_prompt: str, *, json_schema: dict | None = None
) -> str:
    """Call Groq first; fall back to Gemini on any failure. Logs which provider answered."""
    json_mode = json_schema is not None
    if json_mode:
        user_prompt = (
            f"{user_prompt}\n\nRespond with a JSON object matching this shape: "
            f"{json.dumps(json_schema)}"
        )
    try:
        result = _call_groq(system_prompt, user_prompt, json_mode)
        logger.info("llm: answered by groq")
        return result
    except OpenAIError as exc:
        logger.warning("llm: groq failed (%s), falling back to gemini", exc)
    try:
        result = _call_gemini(system_prompt, user_prompt, json_mode)
        logger.info("llm: answered by gemini")
        return result
    except Exception as exc:
        # Any Gemini SDK failure here means both providers are down.
        raise LLMError(f"Both Groq and Gemini failed: {exc}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add dashboard/llm.py tests/test_llm.py
git commit -m "feat: add Groq/Gemini LLM client foundation"
```

---

### Task 3: Phase 1 — `analyze_offer`

**Files:**
- Modify: `dashboard/llm.py` (add `OfferAnalysis` dataclass and `analyze_offer`)
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `call_llm(system_prompt, user_prompt, *, json_schema=None) -> str` (Task 2).
- Produces: `@dataclass class OfferAnalysis: top_skills: list[str]; keywords: list[str]; company_context: str; gaps: list[str]; hook_angle: str; offer_language: str; requires_english_cv: bool` and `analyze_offer(offer: dict[str, Any]) -> OfferAnalysis`. Consumed by Tasks 4, 5, 6 and the route in Task 7.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_llm.py`:

```python
import json as _json

_CANNED_ANALYSIS = {
    "top_skills": ["PyTorch", "Kubernetes", "RAG"],
    "keywords": ["MLOps", "production ML"],
    "company_context": "AI startup building developer tools, ~40 people, Python stack.",
    "gaps": ["Kubernetes"],
    "hook_angle": "They open-sourced their inference engine, which I've used personally.",
    "offer_language": "en",
    "requires_english_cv": True,
}


def test_analyze_offer_parses_llm_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(_CANNED_ANALYSIS))
    offer = {"company": "Acme", "role": "ML Engineer", "description": "We need PyTorch..."}

    analysis = llm.analyze_offer(offer)

    assert analysis.top_skills == ["PyTorch", "Kubernetes", "RAG"]
    assert analysis.offer_language == "en"
    assert analysis.requires_english_cv is True
    assert analysis.gaps == ["Kubernetes"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm.py::test_analyze_offer_parses_llm_response -v`
Expected: FAIL with `AttributeError: module 'llm' has no attribute 'analyze_offer'`

- [ ] **Step 3: Write the implementation**

Append to `dashboard/llm.py`:

```python
@dataclass
class OfferAnalysis:
    top_skills: list[str]
    keywords: list[str]
    company_context: str
    gaps: list[str]
    hook_angle: str
    offer_language: str
    requires_english_cv: bool


_ANALYZE_OFFER_SCHEMA = {
    "top_skills": ["string"],
    "keywords": ["string"],
    "company_context": "string",
    "gaps": ["string"],
    "hook_angle": "string",
    "offer_language": "'fr' or 'en'",
    "requires_english_cv": "boolean",
}

_ANALYZE_OFFER_SYSTEM_PROMPT = (
    "You are a career coach analyzing a job posting for a candidate preparing an "
    "application. Extract only what is explicitly present in the posting text, "
    "never invent requirements."
)


def analyze_offer(offer: dict[str, Any]) -> OfferAnalysis:
    user_prompt = (
        f"Job posting for {offer.get('role', '')} at {offer.get('company', '')}:\n\n"
        f"{offer.get('description', '')}\n\n"
        "Extract 5-7 top_skills (exact terms from the posting), keywords, a "
        "company_context (mission, product, size, stack), gaps (skills a typical "
        "candidate profile might be missing based on the posting), a hook_angle "
        "(one concrete why-this-company reason, not generic), the offer_language "
        "('fr' or 'en'), and requires_english_cv (true only if the posting "
        "explicitly asks for an English-language CV/resume submission, not merely "
        "English fluency)."
    )
    raw = call_llm(
        _ANALYZE_OFFER_SYSTEM_PROMPT, user_prompt, json_schema=_ANALYZE_OFFER_SCHEMA
    )
    data = json.loads(raw)
    return OfferAnalysis(
        top_skills=list(data["top_skills"]),
        keywords=list(data["keywords"]),
        company_context=str(data["company_context"]),
        gaps=list(data["gaps"]),
        hook_angle=str(data["hook_angle"]),
        offer_language=str(data["offer_language"]),
        requires_english_cv=bool(data["requires_english_cv"]),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm.py::test_analyze_offer_parses_llm_response -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/llm.py tests/test_llm.py
git commit -m "feat: add analyze_offer LLM phase"
```

---

### Task 4: Phase 2 — `rewrite_cv_summary`

**Files:**
- Modify: `dashboard/llm.py` (add `CvRewrite` dataclass and `rewrite_cv_summary`)
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `call_llm` (Task 2), `OfferAnalysis` (Task 3). `cv: dict[str, Any]` shaped like `user_data.get_cv()`'s return value: `{"meta": {"summary": str}, "experience": [...], "skills": [{"id", "category", "skill", "sort_order"}], "certifications": [...], "education": [...]}`.
- Produces: `@dataclass class CvRewrite: highlighted_skills: list[str]; summary: str` and `rewrite_cv_summary(profile: dict[str, Any], cv: dict[str, Any], analysis: OfferAnalysis) -> CvRewrite`. Consumed by the route in Task 7.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_llm.py`:

```python
_SAMPLE_CV = {
    "meta": {"summary": "AI engineer with a background in sales."},
    "experience": [{"id": 1, "title": "AI Engineer", "company": "Missia", "bullets": ["Built RAG pipelines"]}],
    "skills": [
        {"id": 1, "category": "ML", "skill": "PyTorch", "sort_order": 0},
        {"id": 2, "category": "ML", "skill": "scikit-learn", "sort_order": 1},
    ],
    "certifications": [],
    "education": [],
}


def test_rewrite_cv_summary_keeps_known_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    canned = {"highlighted_skills": ["PyTorch"], "summary": "Tailored summary."}
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(canned))
    analysis = llm.OfferAnalysis(
        top_skills=["PyTorch"], keywords=[], company_context="", gaps=[],
        hook_angle="", offer_language="fr", requires_english_cv=False,
    )

    result = llm.rewrite_cv_summary({}, _SAMPLE_CV, analysis)

    assert result.highlighted_skills == ["PyTorch"]
    assert result.summary == "Tailored summary."


def test_rewrite_cv_summary_drops_unknown_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    canned = {"highlighted_skills": ["PyTorch", "Kubernetes"], "summary": "Tailored summary."}
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(canned))
    analysis = llm.OfferAnalysis(
        top_skills=["PyTorch", "Kubernetes"], keywords=[], company_context="",
        gaps=["Kubernetes"], hook_angle="", offer_language="fr", requires_english_cv=False,
    )

    result = llm.rewrite_cv_summary({}, _SAMPLE_CV, analysis)

    assert result.highlighted_skills == ["PyTorch"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm.py::test_rewrite_cv_summary_keeps_known_skills tests/test_llm.py::test_rewrite_cv_summary_drops_unknown_skill -v`
Expected: FAIL with `AttributeError: module 'llm' has no attribute 'rewrite_cv_summary'`

- [ ] **Step 3: Write the implementation**

Append to `dashboard/llm.py`:

```python
@dataclass
class CvRewrite:
    highlighted_skills: list[str]
    summary: str


_REWRITE_CV_SUMMARY_SCHEMA = {"highlighted_skills": ["string"], "summary": "string"}

_REWRITE_CV_SUMMARY_SYSTEM_PROMPT = (
    "You rewrite a candidate's CV summary to mirror a specific job posting. "
    "Never invent skills the candidate doesn't have."
)


def rewrite_cv_summary(
    profile: dict[str, Any], cv: dict[str, Any], analysis: OfferAnalysis
) -> CvRewrite:
    known_skills = [s["skill"] for s in cv.get("skills", [])]
    lang = "English" if analysis.requires_english_cv else "French"
    user_prompt = (
        f"Candidate's known skills: {known_skills}\n"
        f"Candidate's current CV summary: {cv.get('meta', {}).get('summary', '')}\n"
        f"Target offer top_skills: {analysis.top_skills}\n"
        f"Target offer keywords: {analysis.keywords}\n\n"
        "Pick highlighted_skills: a subset of the candidate's known skills above "
        "that match the offer's top_skills (never invent a skill not in the known "
        f"list). Write a 2-sentence summary in {lang} mirroring the offer's role "
        "and domain."
    )
    raw = call_llm(
        _REWRITE_CV_SUMMARY_SYSTEM_PROMPT,
        user_prompt,
        json_schema=_REWRITE_CV_SUMMARY_SCHEMA,
    )
    data = json.loads(raw)
    valid_skills = set(known_skills)
    highlighted = [s for s in data["highlighted_skills"] if s in valid_skills]
    return CvRewrite(highlighted_skills=highlighted, summary=str(data["summary"]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Commit**

```bash
git add dashboard/llm.py tests/test_llm.py
git commit -m "feat: add rewrite_cv_summary LLM phase"
```

---

### Task 5: Phase 3 — `write_cover_letter` with grounding gate

**Files:**
- Modify: `dashboard/llm.py` (add `CoverLetterDraft` dataclass and `write_cover_letter`)
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `call_llm`, `GroundingError` (Task 2), `OfferAnalysis` (Task 3). `cv["experience"]` entries have an `"id": int` key (from `user_data.get_cv()`).
- Produces: `@dataclass class CoverLetterDraft: paragraphs: list[str]; citations: list[dict[str, Any]]` and `write_cover_letter(profile: dict[str, Any], cv: dict[str, Any], offer: dict[str, Any], analysis: OfferAnalysis) -> CoverLetterDraft`. Consumed by the route in Task 7.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_llm.py`:

```python
_SAMPLE_OFFER = {"company": "Acme", "role": "ML Engineer", "description": "..."}


def _analysis(lang: str = "fr") -> "llm.OfferAnalysis":
    return llm.OfferAnalysis(
        top_skills=["PyTorch"], keywords=["MLOps"], company_context="AI startup.",
        gaps=[], hook_angle="Their open-source inference engine.",
        offer_language=lang, requires_english_cv=False,
    )


def test_write_cover_letter_accepts_valid_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned = {
        "paragraphs": ["Hook.", "Proof.", "Close."],
        "citations": [{"claim": "Built RAG pipelines", "experience_id": 1}],
    }
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(canned))

    result = llm.write_cover_letter({}, _SAMPLE_CV, _SAMPLE_OFFER, _analysis())

    assert result.paragraphs == ["Hook.", "Proof.", "Close."]
    assert result.citations[0]["experience_id"] == 1


def test_write_cover_letter_retries_once_on_invalid_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        _json.dumps(
            {
                "paragraphs": ["Hook.", "Proof.", "Close."],
                "citations": [{"claim": "Invented claim", "experience_id": 999}],
            }
        ),
        _json.dumps(
            {
                "paragraphs": ["Hook.", "Proof fixed.", "Close."],
                "citations": [{"claim": "Built RAG pipelines", "experience_id": 1}],
            }
        ),
    ]
    calls = []

    def _fake_call_llm(system_prompt: str, user_prompt: str, **kwargs: object) -> str:
        calls.append(user_prompt)
        return responses[len(calls) - 1]

    monkeypatch.setattr(llm, "call_llm", _fake_call_llm)

    result = llm.write_cover_letter({}, _SAMPLE_CV, _SAMPLE_OFFER, _analysis())

    assert len(calls) == 2
    assert "999" in calls[1]
    assert result.paragraphs == ["Hook.", "Proof fixed.", "Close."]


def test_write_cover_letter_raises_grounding_error_after_second_invalid_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned = {
        "paragraphs": ["Hook.", "Proof.", "Close."],
        "citations": [{"claim": "Invented claim", "experience_id": 999}],
    }
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(canned))

    with pytest.raises(llm.GroundingError):
        llm.write_cover_letter({}, _SAMPLE_CV, _SAMPLE_OFFER, _analysis())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm.py::test_write_cover_letter_accepts_valid_citations tests/test_llm.py::test_write_cover_letter_retries_once_on_invalid_citation tests/test_llm.py::test_write_cover_letter_raises_grounding_error_after_second_invalid_citation -v`
Expected: FAIL with `AttributeError: module 'llm' has no attribute 'write_cover_letter'`

- [ ] **Step 3: Write the implementation**

Append to `dashboard/llm.py`:

```python
@dataclass
class CoverLetterDraft:
    paragraphs: list[str]
    citations: list[dict[str, Any]]


_COVER_LETTER_SCHEMA = {
    "paragraphs": ["string", "string", "string"],
    "citations": [{"claim": "string", "experience_id": 0}],
}

_BANNED_PHRASES = [
    "Je suis très motivé",
    "passionné par",
    "je me permets de",
    "dans l'espoir de",
    "à fort impact",
    "de bout en bout",
    "production-first",
    "rigueur technique",
    "mettre mes compétences au service de",
    "je serais ravi d'échanger sur la façon dont",
    "dans l'attente de votre retour",
]

_PIVOT_SENTENCE = {
    "fr": (
        "Une reconversion délibérée : 8 ans à manager une équipe commerciale, "
        "puis formation en AI engineering, me permet d'allier profondeur "
        "technique et capacité à travailler avec des interlocuteurs non "
        "techniques."
    ),
    "en": (
        "A deliberate pivot: eight years leading a sales team, then "
        "retraining as an AI engineer, means I bring both technical depth "
        "and the communication skills to work directly with non-technical "
        "stakeholders."
    ),
}

_COVER_LETTER_SYSTEM_PROMPT = (
    "You write cover letters for a candidate who pivoted from 8 years in "
    "sales management to AI engineering. Every claim of professional "
    "accomplishment must cite an experience_id from the provided experience "
    "list, never invent one. Never use these phrases: "
    + "; ".join(_BANNED_PHRASES)
    + ". No em-dashes or en-dashes; use commas, periods, colons, or rephrase."
)


def write_cover_letter(
    profile: dict[str, Any],
    cv: dict[str, Any],
    offer: dict[str, Any],
    analysis: OfferAnalysis,
) -> CoverLetterDraft:
    experiences = [
        {
            "experience_id": e["id"],
            "title": e.get("title", ""),
            "company": e.get("company", ""),
            "bullets": e.get("bullets", []),
        }
        for e in cv.get("experience", [])
    ]
    valid_ids = {e["id"] for e in cv.get("experience", [])}
    lang = analysis.offer_language
    pivot = _PIVOT_SENTENCE.get(lang, _PIVOT_SENTENCE["fr"])
    base_user_prompt = (
        f"Company: {offer.get('company', '')}\nRole: {offer.get('role', '')}\n"
        f"Company context: {analysis.company_context}\n"
        f"Hook angle: {analysis.hook_angle}\n"
        f"Candidate's experience (cite only these experience_id values): "
        f"{experiences}\n\n"
        f"Write in {lang}. 3 paragraphs, under 300 words total:\n"
        "1. Hook: one concrete reason tied to the hook_angle, never generic.\n"
        "2. Proof: 2 specific experiences from the list above, each backed by "
        "a citation.\n"
        f'3. Close: include this sentence verbatim: "{pivot}" then mention '
        "availability.\n"
        "Return citations as a list of {claim, experience_id} for every "
        "accomplishment claim."
    )
    user_prompt = base_user_prompt
    invalid: list[dict[str, Any]] = []
    for attempt in range(2):
        raw = call_llm(
            _COVER_LETTER_SYSTEM_PROMPT, user_prompt, json_schema=_COVER_LETTER_SCHEMA
        )
        data = json.loads(raw)
        citations = list(data.get("citations", []))
        invalid = [c for c in citations if c.get("experience_id") not in valid_ids]
        if not invalid:
            return CoverLetterDraft(
                paragraphs=list(data["paragraphs"]), citations=citations
            )
        if attempt == 0:
            bad_ids = [c.get("experience_id") for c in invalid]
            user_prompt = (
                base_user_prompt
                + f"\n\nYour previous answer cited experience_id {bad_ids}, "
                f"which do not exist. Only cite from this list: "
                f"{sorted(valid_ids)}."
            )
    raise GroundingError(
        f"Cover letter still cites invalid experience_id after retry: {invalid}"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Commit**

```bash
git add dashboard/llm.py tests/test_llm.py
git commit -m "feat: add write_cover_letter LLM phase with grounding gate"
```

---

### Task 6: Phase 4 — `generate_prep_questions`

**Files:**
- Modify: `dashboard/llm.py` (add `PrepSheetDraft` dataclass and `generate_prep_questions`)
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `call_llm` (Task 2), `OfferAnalysis` (Task 3).
- Produces: `@dataclass class PrepSheetDraft: company_summary: str; tech_stack: list[str]; questions: list[dict[str, str]]` and `generate_prep_questions(offer: dict[str, Any], analysis: OfferAnalysis) -> PrepSheetDraft`. Consumed by the route in Task 7.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_llm.py`:

```python
def test_generate_prep_questions_parses_llm_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canned = {
        "company_summary": "AI startup building developer tools.",
        "tech_stack": ["Python", "Kubernetes"],
        "questions": [
            {"theme": "Technique ML", "question": "How would you deploy a RAG pipeline?"},
            {"theme": "MLOps", "question": "How do you monitor model drift?"},
        ],
    }
    monkeypatch.setattr(llm, "call_llm", lambda *a, **k: _json.dumps(canned))

    result = llm.generate_prep_questions(_SAMPLE_OFFER, _analysis())

    assert result.company_summary == "AI startup building developer tools."
    assert result.tech_stack == ["Python", "Kubernetes"]
    assert len(result.questions) == 2
    assert result.questions[0]["theme"] == "Technique ML"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm.py::test_generate_prep_questions_parses_llm_response -v`
Expected: FAIL with `AttributeError: module 'llm' has no attribute 'generate_prep_questions'`

- [ ] **Step 3: Write the implementation**

Append to `dashboard/llm.py`:

```python
@dataclass
class PrepSheetDraft:
    company_summary: str
    tech_stack: list[str]
    questions: list[dict[str, str]]


_PREP_SHEET_SCHEMA = {
    "company_summary": "string",
    "tech_stack": ["string"],
    "questions": [{"theme": "string", "question": "string"}],
}

_PREP_SHEET_SYSTEM_PROMPT = (
    "You write interview prep sheets: a company summary and 8-12 interview "
    "questions covering technical depth, MLOps/deployment, behavioural (STAR "
    "format), and why-this-role."
)


def generate_prep_questions(
    offer: dict[str, Any], analysis: OfferAnalysis
) -> PrepSheetDraft:
    user_prompt = (
        f"Company: {offer.get('company', '')}\nRole: {offer.get('role', '')}\n"
        f"Company context: {analysis.company_context}\n"
        f"Top skills required: {analysis.top_skills}\n\n"
        "Write a 2-3 sentence company_summary, a tech_stack list, and 8-12 "
        "questions covering technical depth (linked to top_skills), "
        "MLOps/deployment, behavioural, and why-us/why-this-role."
    )
    raw = call_llm(
        _PREP_SHEET_SYSTEM_PROMPT, user_prompt, json_schema=_PREP_SHEET_SCHEMA
    )
    data = json.loads(raw)
    return PrepSheetDraft(
        company_summary=str(data["company_summary"]),
        tech_stack=list(data["tech_stack"]),
        questions=list(data["questions"]),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add dashboard/llm.py tests/test_llm.py
git commit -m "feat: add generate_prep_questions LLM phase"
```

---

### Task 7: Route `POST /offers/{offer_id}/prepare`

**Files:**
- Modify: `dashboard/app.py` (import `llm`, add `_group_skills_by_category`, add the route)
- Modify: `dashboard/templates/partials/offer_detail.html` (replace the CLI-copy "Préparer candidature" button with an HTMX form; render `prep_error`)
- Modify: `tests/test_dashboard_app.py` (`_insert_row` gets an optional `description` param)
- Test: `tests/test_dashboard_app.py::TestOfferPrepare` (new class)

**Interfaces:**
- Consumes: `llm.analyze_offer`, `llm.rewrite_cv_summary`, `llm.write_cover_letter`, `llm.generate_prep_questions`, `llm.LLMError`, `llm.GroundingError` (Tasks 2-6); `user_data.get_profile`, `user_data.get_cv` (existing); `scripts.generate_pdf.build_cv_context`/`generate_pdf`, `scripts.generate_cover_letter.build_cover_letter_context`/`generate_pdf`, `scripts.generate_prep_sheet.build_prep_sheet_context`/`generate_pdf` (existing, unmodified).
- Produces: `POST /offers/{offer_id}/prepare` HTMX route returning `partials/offer_detail.html`.

- [ ] **Step 1: Write the failing tests**

First, extend `_insert_row` in `tests/test_dashboard_app.py` with an optional `description` param (append as the last keyword arg, default `""`, so existing calls are unaffected):

```python
def _insert_row(
    db,
    company: str = "Acme",
    role: str = "ML Engineer",
    offer_url: str = "https://example.com/1",
    detection_date: str = "2026-05-25",
    score_grade: str = "B",
    score_value: float = 4.0,
    status: str = "À envoyer",
    send_date: str | None = None,
    user_id: str = TEST_USER_ID,
    description: str = "",
) -> int:
    with db.conn.cursor() as cur:
        cur.execute(
            "INSERT INTO applications (user_id, company, role, offer_url, detection_date,"
            " score_grade, score_value, status, send_date, description) VALUES"
            " (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (
                user_id,
                company,
                role,
                offer_url,
                detection_date,
                score_grade,
                score_value,
                status,
                send_date,
                description,
            ),
        )
        row_id = cur.fetchone()[0]
    db.conn.commit()
    return row_id
```

Then add a new test class at the end of `tests/test_dashboard_app.py`:

```python
class TestOfferPrepare:
    _LONG_DESCRIPTION = "We need an ML engineer with PyTorch and RAG experience. " * 10

    _SAMPLE_CV = {
        "meta": {"summary": "AI engineer with a background in sales."},
        "experience": [
            {
                "id": 1,
                "title": "AI Engineer",
                "company": "Missia",
                "type": "CDI",
                "period": "2024-2026",
                "sort_order": 0,
                "bullets": ["Built RAG pipelines"],
            }
        ],
        "skills": [{"id": 1, "category": "ML", "skill": "PyTorch", "sort_order": 0}],
        "certifications": [],
        "education": [],
    }

    _SAMPLE_PROFILE = {
        "name": "Arnaud Thery",
        "title": "AI/ML Engineer",
        "email": "arnaud@example.com",
        "phone": "0600000000",
        "location": "Paris",
        "linkedin": "",
        "github": "",
        "profile_md": "",
    }

    def _patch_phases(self, monkeypatch: pytest.MonkeyPatch, dashboard_app) -> None:
        import llm

        monkeypatch.setattr(
            dashboard_app.user_data, "get_profile", lambda conn, uid: self._SAMPLE_PROFILE
        )
        monkeypatch.setattr(
            dashboard_app.user_data,
            "get_cv",
            lambda conn, uid, lang="fr": self._SAMPLE_CV,
        )
        monkeypatch.setattr(
            llm,
            "analyze_offer",
            lambda offer: llm.OfferAnalysis(
                top_skills=["PyTorch"], keywords=["MLOps"], company_context="AI startup.",
                gaps=[], hook_angle="Their open-source engine.", offer_language="fr",
                requires_english_cv=False,
            ),
        )
        monkeypatch.setattr(
            llm,
            "rewrite_cv_summary",
            lambda profile, cv, analysis: llm.CvRewrite(
                highlighted_skills=["PyTorch"], summary="Tailored summary."
            ),
        )
        monkeypatch.setattr(
            llm,
            "write_cover_letter",
            lambda profile, cv, offer, analysis: llm.CoverLetterDraft(
                paragraphs=["Hook.", "Proof.", "Close."],
                citations=[{"claim": "Built RAG pipelines", "experience_id": 1}],
            ),
        )
        monkeypatch.setattr(
            llm,
            "generate_prep_questions",
            lambda offer, analysis: llm.PrepSheetDraft(
                company_summary="AI startup.",
                tech_stack=["Python"],
                questions=[{"theme": "Technique ML", "question": "Explain RAG."}],
            ),
        )

    def test_prepare_happy_path_writes_all_three_paths(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description=self._LONG_DESCRIPTION)
        self._patch_phases(monkeypatch, dashboard_app)
        monkeypatch.setattr("scripts.generate_pdf.generate_pdf", lambda ctx, **kw: tmp_path / "cv.pdf")
        monkeypatch.setattr(
            "scripts.generate_cover_letter.generate_pdf", lambda ctx, **kw: tmp_path / "cl.pdf"
        )
        monkeypatch.setattr(
            "scripts.generate_prep_sheet.generate_pdf", lambda ctx, **kw: tmp_path / "prep.pdf"
        )

        r = client.post(f"/offers/{offer_id}/prepare")

        assert r.status_code == 200
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == str(tmp_path / "cv.pdf")
        assert offer["cover_letter_path"] == str(tmp_path / "cl.pdf")
        assert offer["prep_sheet_path"] == str(tmp_path / "prep.pdf")

    def test_prepare_skip_prep_leaves_prep_sheet_path_empty(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import app as dashboard_app
        import llm

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description=self._LONG_DESCRIPTION)
        self._patch_phases(monkeypatch, dashboard_app)

        def _fail_prep_questions(offer: dict, analysis: object) -> None:
            raise AssertionError("generate_prep_questions should not be called when skip_prep=True")

        monkeypatch.setattr(llm, "generate_prep_questions", _fail_prep_questions)
        monkeypatch.setattr("scripts.generate_pdf.generate_pdf", lambda ctx, **kw: tmp_path / "cv.pdf")
        monkeypatch.setattr(
            "scripts.generate_cover_letter.generate_pdf", lambda ctx, **kw: tmp_path / "cl.pdf"
        )

        r = client.post(f"/offers/{offer_id}/prepare", data={"skip_prep": "true"})

        assert r.status_code == 200
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == str(tmp_path / "cv.pdf")
        assert offer["prep_sheet_path"] == ""

    def test_prepare_rejects_thin_description(self, client: TestClient) -> None:
        import app as dashboard_app

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description="Too short.")

        r = client.post(f"/offers/{offer_id}/prepare")

        assert r.status_code == 200
        assert "trop courte" in r.text
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == ""

    def test_prepare_llm_failure_shows_error_and_writes_nothing(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app as dashboard_app
        import llm

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description=self._LONG_DESCRIPTION)

        def _fail_analyze(offer: dict) -> None:
            raise llm.LLMError("both providers down")

        monkeypatch.setattr(llm, "analyze_offer", _fail_analyze)

        r = client.post(f"/offers/{offer_id}/prepare")

        assert r.status_code == 200
        assert "Échec de la préparation IA" in r.text
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == ""

    def test_prepare_grounding_failure_shows_error_and_writes_nothing(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import app as dashboard_app
        import llm

        db = dashboard_app.app.state.db
        offer_id = _insert_row(db, description=self._LONG_DESCRIPTION)
        self._patch_phases(monkeypatch, dashboard_app)

        def _fail_cover_letter(profile: dict, cv: dict, offer: dict, analysis: object) -> None:
            raise llm.GroundingError("invalid citation")

        monkeypatch.setattr(llm, "write_cover_letter", _fail_cover_letter)

        r = client.post(f"/offers/{offer_id}/prepare")

        assert r.status_code == 200
        assert "Échec de la préparation IA" in r.text
        offer = db.get_by_id(offer_id, user_id=TEST_USER_ID)
        assert offer["cv_path"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dashboard_app.py::TestOfferPrepare -v`
Expected: FAIL — `404 Not Found` / `AttributeError` (the route and `llm` import don't exist in `app.py` yet).

- [ ] **Step 3: Write the implementation**

In `dashboard/app.py`, add the import near the other local module imports (after `import user_data`):

```python
import llm
```

Add near the top of the file, after the other module-level constants (after `_FUNNEL_STEPS`/`_EXIT_STEPS` or near `STATUS_COLORS` — any top-level spot works):

```python
_MIN_OFFER_DESCRIPTION_LENGTH = 300
```

Add this helper function near `_parse_description` (same section of the file):

```python
def _group_skills_by_category(skills: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for s in skills:
        grouped.setdefault(s["category"], []).append(s["skill"])
    return grouped
```

Add the route right after `offer_status` (after line 380, before the blank line that precedes `@app.get("/stats", ...)`):

```python
@app.post("/offers/{offer_id}/prepare", response_class=HTMLResponse)
async def offer_prepare(
    request: Request,
    offer_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    skip_prep: bool = Form(False),
) -> HTMLResponse:
    from datetime import date as _date

    from scripts.generate_cover_letter import build_cover_letter_context
    from scripts.generate_cover_letter import generate_pdf as generate_cl_pdf
    from scripts.generate_pdf import build_cv_context
    from scripts.generate_pdf import generate_pdf as generate_cv_pdf
    from scripts.generate_prep_sheet import build_prep_sheet_context
    from scripts.generate_prep_sheet import generate_pdf as generate_prep_pdf

    db = request.app.state.db
    conn = db.conn
    user_id = current_user["sub"]
    offer = db.get_by_id(offer_id, user_id=user_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")

    def _error(message: str) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "partials/offer_detail.html",
            {
                "offer": offer,
                "statuses": VALID_STATUSES,
                "parsed_desc": _parse_description(offer.get("description", "")),
                "prep_error": message,
            },
        )

    if len(offer.get("description", "")) < _MIN_OFFER_DESCRIPTION_LENGTH:
        return _error(
            "Description trop courte pour préparer la candidature. "
            "Complète-la via les notes ou l'édition de l'offre avant de réessayer."
        )

    try:
        analysis = llm.analyze_offer(offer)
        cv_lang = "en" if analysis.requires_english_cv else "fr"
        cv = user_data.get_cv(conn, user_id, lang=cv_lang)
        profile = user_data.get_profile(conn, user_id)
        cv_rewrite = llm.rewrite_cv_summary(profile, cv, analysis)
        cover_letter_draft = llm.write_cover_letter(profile, cv, offer, analysis)
        prep_draft = (
            None if skip_prep else llm.generate_prep_questions(offer, analysis)
        )
    except (llm.LLMError, llm.GroundingError) as exc:
        return _error(f"Échec de la préparation IA : {exc}")

    today = str(_date.today())

    cv_context = build_cv_context(
        name=profile["name"],
        title=profile["title"],
        email=profile["email"],
        phone=profile["phone"],
        location=profile["location"],
        summary=cv_rewrite.summary,
        experience=cv["experience"],
        skill_categories=_group_skills_by_category(cv["skills"]),
        highlighted_skills=cv_rewrite.highlighted_skills,
        education=cv["education"],
        languages=[],
        linkedin=profile["linkedin"],
        github=profile["github"],
        certifications=cv["certifications"],
    )
    cv_path = generate_cv_pdf(
        cv_context, offer=offer["company"], output_date=today, lang=cv_lang
    )

    recipient = (
        "Madame, Monsieur," if analysis.offer_language == "fr" else "Dear Hiring Team,"
    )
    cl_context = build_cover_letter_context(
        name=profile["name"],
        title=profile["title"],
        email=profile["email"],
        phone=profile["phone"],
        location=profile["location"],
        date_str=today,
        company=offer["company"],
        role=offer["role"],
        recipient=recipient,
        paragraphs=cover_letter_draft.paragraphs,
        lang=analysis.offer_language,
    )
    cl_path = generate_cl_pdf(cl_context, offer=offer["company"], output_date=today)

    prep_path = None
    if prep_draft is not None:
        prep_context = build_prep_sheet_context(
            company=offer["company"],
            role=offer["role"],
            date_str=today,
            company_summary=prep_draft.company_summary,
            tech_stack=prep_draft.tech_stack,
            questions=prep_draft.questions,
        )
        prep_path = generate_prep_pdf(
            prep_context, offer=offer["company"], output_date=today
        )

    offer = db.update(
        offer_id,
        {
            "cv_path": str(cv_path),
            "cover_letter_path": str(cl_path),
            "prep_sheet_path": str(prep_path) if prep_path else "",
        },
        user_id=user_id,
    )
    return templates.TemplateResponse(
        request,
        "partials/offer_detail.html",
        {
            "offer": offer,
            "statuses": VALID_STATUSES,
            "parsed_desc": _parse_description(offer.get("description", "")),
        },
    )
```

Now update `dashboard/templates/partials/offer_detail.html`. First, add a row for the new `prep_sheet_path` field right after the existing `cover_letter_path` block (after the `{% if offer.cover_letter_path %}...{% endif %}` block, lines 61-64):

```html
        {% if offer.prep_sheet_path %}
        <dt style="color:#8b5cf6;">Fiche prep</dt>
        <dd style="color:#e2e8f0;" class="text-xs break-all">{{ offer.prep_sheet_path }}</dd>
        {% endif %}
```

Then replace the `{% if offer.status in apply_statuses %}` block (lines 104-116) with an HTMX form instead of the CLI-copy button:

```html
        {% if offer.status in apply_statuses %}
        <form hx-post="/offers/{{ offer.id }}/prepare"
              hx-target="#offer-detail"
              hx-swap="innerHTML"
              class="flex flex-col gap-2">
          <label class="flex items-center gap-2 text-sm cursor-pointer select-none"
                 style="color:#a5b4fc;">
            <input type="checkbox" name="skip_prep" value="true"
                   class="accent-indigo-500 cursor-pointer">
            Sans fiche de préparation d'entretien
          </label>
          <button type="submit"
                  class="text-sm px-4 py-2 rounded-lg text-white font-medium bg-accent transition-opacity hover:opacity-90 text-left">
            ✦ Préparer candidature (IA)
          </button>
        </form>
```

(Leave the `{% elif offer.status in interview_statuses %}` branch and its `copyInterviewCmd` script untouched — that's the separate, not-yet-migrated "prepare-entretien" flow, out of scope for this feature.)

Also remove the now-unused `copyPrepCmd` script block: delete the entire `{% if offer.status in apply_statuses %}...{% endif %}` script block at the bottom of the file (lines 177-197 in the original), since the button that called it no longer exists. Keep the `{% elif offer.status in interview_statuses %}` script block as-is.

Finally, add an error banner just above the "Colonne gauche" div (right after the divider, before `<!-- Corps en 2 colonnes -->`):

```html
  {% if prep_error %}
  <div class="shrink-0 mb-4 text-sm rounded-lg p-3"
       style="background:rgba(185,28,28,0.15);border:1px solid rgba(185,28,28,0.4);color:#fca5a5;">
    {{ prep_error }}
  </div>
  {% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dashboard_app.py::TestOfferPrepare -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest`
Expected: all tests PASS — this confirms the `_insert_row` signature change and the template edit didn't break any existing test in `tests/test_dashboard_app.py` (e.g. tests asserting the old "Préparer candidature" button text should now assert the new "Préparer candidature (IA)" text; grep for `copyPrepCmd` or `"✦ Préparer candidature"` in the test file and fix any such assertion to match the new button label).

- [ ] **Step 6: Update CHANGELOG.md**

Add under `## 2026-07-06` → `### Added`:

```markdown
- `dashboard/llm.py` — Groq/Gemini-backed LLM pipeline (`analyze_offer`, `rewrite_cv_summary`, `write_cover_letter` with a grounding gate, `generate_prep_questions`)
- `POST /offers/{offer_id}/prepare` in `dashboard/app.py` — server-side candidature prep, replaces the Claude-Code-CLI `modes/prepare-candidature.md` workflow for CV/cover-letter/prep-sheet generation
```

And under `### Changed`:

```markdown
- `dashboard/templates/partials/offer_detail.html` — "Préparer candidature" button now posts to `/offers/{id}/prepare` (server-side LLM pipeline) instead of copying a Claude Code CLI command
```

- [ ] **Step 7: Commit**

```bash
git add dashboard/app.py dashboard/templates/partials/offer_detail.html tests/test_dashboard_app.py CHANGELOG.md
git commit -m "feat: wire LLM pipeline into POST /offers/{id}/prepare route"
```

---

### Task 8: Config, dependencies, final verification

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `CHANGELOG.md`
- Modify: `README.md` (if the Dashboard pages table or Configuration table exists — add the new route/env var per project convention)

**Interfaces:** None — this task only wires up config, it doesn't change any function signature.

- [ ] **Step 1: Install the new dependencies and capture their resolved versions**

```bash
source .venv/bin/activate
pip install openai google-generativeai
pip freeze | grep -iE "^(openai|google-generativeai)=="
```

- [ ] **Step 2: Add the pinned versions to `requirements.txt`**

Append the two lines printed by the previous step (exact versions will depend on what resolves at install time), e.g.:

```
openai==1.59.7
google-generativeai==0.8.3
```

- [ ] **Step 3: Add `GEMINI_API_KEY` to `.env.example`**

In `.env.example`, right after the `GROQ_API_KEY=gsk_...` line, add:

```
GEMINI_API_KEY=AI...
```

- [ ] **Step 4: Update README.md if it documents dashboard routes/config**

Run: `grep -n "GROQ_API_KEY\|Dashboard pages\|prepare-candidature" README.md`

If a "Configuration" table lists `GROQ_API_KEY`, add a row for `GEMINI_API_KEY` (Gemini fallback API key). If a "Dashboard pages" or routes table exists, add a row for `POST /offers/{id}/prepare` (server-side candidature prep: CV, cover letter, prep sheet). If neither section exists, skip this step — do not invent new README sections.

- [ ] **Step 5: Update CHANGELOG.md**

Add under `## 2026-07-06` → `### Changed`:

```markdown
- `requirements.txt` — add `openai` and `google-generativeai` for the server-side LLM pipeline
- `.env.example` — add `GEMINI_API_KEY` (Gemini fallback for the LLM pipeline)
```

- [ ] **Step 6: Run the full test suite one final time**

Run: `pytest`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .env.example CHANGELOG.md README.md
git commit -m "chore: add openai/google-generativeai deps and GEMINI_API_KEY config"
```

- [ ] **Step 8: Remind Arnaud about real API keys**

Before real end-to-end testing (not part of this plan's automated steps), Arnaud needs to create a real `GROQ_API_KEY` (Groq free tier) and `GEMINI_API_KEY` (Google AI Studio) and put them in his local `.env` — the current `.env` has no `GROQ_API_KEY` set. This is a manual step, not a code change.

---

## After this plan

Per `feedback_dev_workflow` memory: run `/simplify` on the full `feature/llm-migration` diff, then `docker compose build dashboard && docker compose up dashboard` for Arnaud to validate the feature end-to-end (CV/cover-letter/prep-sheet buttons, real Groq call) before merging to `master`. Do not merge without an explicit "oui, merge" from Arnaud.
