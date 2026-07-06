# LLM migration — server-side candidature prep — Design Spec

Date: 2026-07-06
Status: approved

## Goal

Replace the Claude Code CLI-driven `modes/prepare-candidature.md` workflow with a server-side pipeline: a dashboard button that calls an LLM (Groq, with Gemini fallback) to analyze an offer, rewrite the CV summary, write a grounded cover letter, and generate an interview prep sheet — then renders all three PDFs in-process. This is Group 1 of `docs/todo-deployment.md`, the last blocker before career-ops-fr works for a user who doesn't have Claude Code.

## Architecture

New module `dashboard/llm.py`:

- `call_llm(system_prompt: str, user_prompt: str, *, json_schema: dict | None = None) -> str` — thin client using the `openai` SDK with `base_url="https://api.groq.com/openai/v1"`, model `llama-3.3-70b-versatile`. On Groq failure (timeout, 5xx, quota) falls back transparently to `google-generativeai` (Gemini Flash 2.0), logging which provider answered.
- Four phase functions, each: build a prompt from DB data, call `call_llm`, parse the JSON response into a typed dataclass.
  - `analyze_offer(offer: dict) -> OfferAnalysis`
  - `rewrite_cv_summary(profile: dict, cv: dict, analysis: OfferAnalysis) -> CvRewrite`
  - `write_cover_letter(profile: dict, cv: dict, offer: dict, analysis: OfferAnalysis) -> CoverLetterDraft`
  - `generate_prep_questions(offer: dict, analysis: OfferAnalysis) -> PrepSheetDraft`

Dataclasses (not raw dicts) give the route and the tests a stable contract.

## Global Constraints

- Python 3.11+, no new frameworks. New deps: `openai` (generic client, pointed at Groq), `google-generativeai` (Gemini fallback).
- Synchronous route — no async job/polling pattern for this feature (latency budget: a few seconds per phase, acceptable for a single-user request).
- All-or-nothing DB write: `cv_path`/`cover_letter_path`/`prep_sheet_path` are only updated after all 3 PDFs render successfully.
- Never invent data: any skill or experience the LLM references must exist in the user's own DB-backed CV/profile. Enforced by code, not just prompt wording.
- CV generated in French by default; English only if `OfferAnalysis.requires_english_cv` is true (offer explicitly asks for an English CV/resume, not merely English fluency).
- Cover letter language mirrors `OfferAnalysis.offer_language` ("fr"/"en" — the `applications` table has no lang column, so the LLM detects it during Phase 1).
- Cover letter style rules unchanged (see `feedback_cover_letter_style` memory): no em/en-dashes, no hollow phrases, mandatory career-pivot sentence, < 300 words, closing "Cordialement,"/"Best regards,".

---

## Phase 1 — `analyze_offer(offer)`

Input: `offer["description"]` (already populated by the scan pipeline — no HTTP re-fetch fallback in this feature; that's out of scope).

**Guard:** if `len(offer["description"]) < 300` (same threshold as the existing `legitimacy:thin_desc` signal in `pre_filter.py`), the route returns a clear error asking the user to flesh out the offer via `POST /offers/{id}/notes` or the edit route before preparing a candidature. No scraping fallback is implemented here.

Output (`OfferAnalysis`):
- `top_skills: list[str]` (5-7, exact terms from the posting)
- `keywords: list[str]`
- `company_context: str` (mission, product, size, stack)
- `gaps: list[str]` (skills in the offer not in the user's profile — never invented into the CV)
- `hook_angle: str` (one concrete "why this company" angle)
- `offer_language: Literal["fr", "en"]`
- `requires_english_cv: bool`

## Phase 2 — `rewrite_cv_summary(profile, cv, analysis)`

Output (`CvRewrite`): `highlighted_skills: list[str]`, `summary: str` (2 sentences, mirrors offer's role/domain, in French unless `requires_english_cv`).

**Validation:** any skill in `highlighted_skills` not present in `cv["skill_categories"]` is dropped silently (not an error — just excluded, matching "never invent" without failing the whole phase over a minor LLM slip).

## Phase 3 — `write_cover_letter(profile, cv, offer, analysis)`

The prompt includes the user's experience list **with `experience_id`** (from `user_experience` DB rows) and instructs the model to produce 3 paragraphs plus a citation list: `{claim: str, experience_id: int}` for every claim of professional accomplishment.

**Validation (grounding gate):** every cited `experience_id` must exist in the user's own `user_experience` rows. If any citation is invalid:
1. Retry once with an explicit error message appended to the prompt ("experience_id X does not exist, only cite from the provided list").
2. If still invalid, the phase raises and the route surfaces a clear error — no cover letter is generated. No further retries (cost/latency control).

Style constraints carried over unchanged from `modes/prepare-candidature.md`: hook paragraph never generic ("Je suis passionné par l'IA" forbidden), proof paragraph only from grounded claims, mandatory pivot sentence in the closing paragraph, < 300 words total, banned phrases enforced in the prompt (best-effort — not re-validated in code, matches existing manual-mode trust level for prose quality).

## Phase 4 — `generate_prep_questions(offer, analysis)`

Output (`PrepSheetDraft`): `company_summary: str`, `tech_stack: list[str]`, `questions: list[{theme, question}]` (8-12, covering technical/MLOps/behavioural/why-us). No grounding gate needed — these are questions, not claims about the candidate.

---

## Route: `POST /offers/{offer_id}/prepare`

Form field `skip_prep: bool` (replaces the old `--no-prep` CLI flag).

1. Load offer, profile, and CV (current language) for `current_user["sub"]` from DB.
2. Guard: description length (see Phase 1).
3. Run phases 1-3 (and 4, unless `skip_prep`), in sequence, synchronously.
4. On success: call `build_cv_context`/`generate_pdf` (CV), `build_cover_letter_context`/`generate_pdf` (cover letter, `generate_cover_letter.py`), and — unless `skip_prep` — `build_prep_sheet_context`/`generate_pdf` (`generate_prep_sheet.py`). These functions are already pure/in-process; the `/tmp/cl-context-*.json` and `/tmp/prep-context-*.json` IPC files used by the old Claude-Code-CLI flow are eliminated — the dataclasses feed the `build_*_context` functions directly as Python objects.
5. Update `cv_path`, `cover_letter_path`, `prep_sheet_path` (new column) on the offer row.
6. Return the offer-detail HTMX partial with download links.

**On any failure** (LLM/grounding/rendering) at any step: no DB write, no path referenced, HTMX partial shows a clear error message. Already-written PDF files on disk (if a later phase fails after an earlier `generate_pdf` call succeeded) are left orphaned in `output/` — acceptable, matches current behavior of the manual flow, cheap to regenerate.

## Migration

New Alembic migration: `applications.prep_sheet_path TEXT NOT NULL DEFAULT ''`.

## Config

- `requirements.txt`: add `openai`, `google-generativeai`.
- `.env.example`: `GROQ_API_KEY` already present; add `GEMINI_API_KEY`.
- Arnaud needs to create both API keys (Groq free tier, Google AI Studio) before real end-to-end testing — reminder at implementation time.

## Testing

- `call_llm` is mocked in every test — no real network calls.
- Each phase function tested independently: inject a canned JSON response, assert parsing and validation (dropped-skill case for Phase 2, invalid-citation retry/failure case for Phase 3).
- Route tested with all 4 phase functions monkeypatched (same pattern as `TestScan` in `tests/test_dashboard_app.py`), covering: happy path, `skip_prep`, thin-description guard, LLM failure, grounding failure after retry.

## Out of scope (for this pass)

- Async job/polling execution (Group 2.3 concern, not needed at this latency budget).
- HTTP re-fetch of thin offer descriptions.
- Re-validating cover letter prose against the banned-phrase list in code (prompt-only, as today).
- Self-hosted Ollama fallback (mentioned in the roadmap as a maybe; Groq + Gemini covers it for now).
