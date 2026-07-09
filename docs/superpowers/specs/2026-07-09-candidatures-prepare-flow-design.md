# Diggo — Candidatures: prepare flow — Design Spec

Date: 2026-07-09
Status: approved

## Goal

Migrate the "Préparer candidature" (AI-generated CV + cover letter + optional interview prep sheet) and "Préparer entretien" (local CLI command copy) actions from FastAPI/Jinja2/HTMX to Next.js. This is sub-phase D, the last of four Candidatures sub-phases (A: list/detail read-only, B: mutations, C: scan flow — all done, D: prepare flow — this spec), and the one that finally retires `dashboard/templates/partials/offer_detail.html`/`offer_notes.html`.

## Context

Today, `POST /offers/{offer_id}/prepare` (`dashboard/app.py`) runs synchronously and blocks the request for ~30-60s: it validates the offer's description length (≥300 chars) and that the user has a saved Hugging Face token, then makes up to 4 sequential LLM calls (`llm.analyze_offer` → `llm.rewrite_cv_summary` → `llm.write_cover_letter` → optionally `llm.generate_prep_questions`, unless the `skip_prep` checkbox is set), then renders 2-3 PDFs via WeasyPrint (`scripts/generate_pdf.py`, `scripts/generate_cover_letter.py`, `scripts/generate_prep_sheet.py`), then writes the resulting file paths to the offer's `cv_path`/`cover_letter_path`/`prep_sheet_path` columns. Any `llm.LLMError`/`llm.GroundingError` or PDF-rendering exception is caught and re-rendered as a specific inline error message via the same `partials/offer_detail.html` template. This route is gated on `offer.status` being one of `apply_statuses` (`"À envoyer"`, `"Envoyée"`, `"Relance"`) in the template — the button only appears for offers in those statuses.

**"Préparer entretien" is a different, unrelated feature** despite the shared UI section: for offers in `interview_statuses` (`"Entretien RH"`, `"Entretien tech"`, `"Offre"`), the template instead shows a button that copies a `claude --system-prompt "$(cat modes/prepare-entretien.md)" "Prépare l'entretien pour l'offre ID {id}"` shell command to the clipboard via `navigator.clipboard.writeText`, for the user to run in their own terminal against Claude Code. No backend call, no LLM, no async work needed — this sub-phase ports it as a straightforward clipboard-copy button alongside the real migration work, since it lives in the same UI section.

**Pre-existing gap this sub-phase also fixes**: generated PDF file paths are currently only ever displayed as raw server-filesystem text (`{{ offer.cv_path }}` etc.) — there is no HTTP route that serves these files. The feature has never actually been downloadable through the app itself. This sub-phase adds real download routes as part of making the migrated feature usable, not as a scope-creep addition.

## Backend

New `dashboard/prepare_state.py`, mirroring `dashboard/scan_state.py`'s per-user in-memory pattern (sub-phase C) but keyed by `offer_id` instead of `user_id` — an offer's ownership is already checked via `db.get_by_id(offer_id, user_id=...)` in the route before starting prep, so a per-`offer_id` dict is sufficient (no need for a `(user_id, offer_id)` compound key), and it naturally allows multiple offers to prep concurrently for the same user without interfering, which a per-user key would not.

- `start_prepare(offer_id: int, user_id: str, skip_prep: bool) -> None` — no-op if already running for that `offer_id` (same no-`await`-between-check-and-set reasoning as `scan_state.start_scan`, no lock needed). Runs the same LLM+PDF pipeline as today's `offer_prepare`, updating a `stage` field after each step so the frontend can show live progress: `"Analyse de l'offre…"` → `"Rédaction du CV…"` → `"Rédaction de la lettre…"` → (only if not `skip_prep`) `"Génération de la fiche d'entretien…"` → `"Génération des PDF…"`. On success: writes `cv_path`/`cover_letter_path`/`prep_sheet_path` to the DB exactly as today's route does, sets state to `{"status": "done", "stage": "", "error": ""}`. On `llm.LLMError`/`llm.GroundingError`: sets `{"status": "error", "stage": "", "error": "Échec de la préparation IA : {exc}"}` (same message format as today's `_error()` helper). On a PDF-rendering exception (broad `except Exception`, matching today's route's own comment explaining why — WeasyPrint/Jinja2 failures can't be enumerated up front): `{"status": "error", "stage": "", "error": "Échec de la génération des PDF : {exc}"}`.
- `get_prepare_state(offer_id: int) -> dict` — `{"status": "idle"|"running"|"done"|"error", "stage": str, "error": str}`.

Two new routes in `dashboard/api.py`:
- `POST /api/offers/{offer_id}/prepare` — validates ownership (404 if not found/not owned), then validates the two synchronous preconditions today's route checks before anything async starts: description length ≥300 chars (422 with the exact French message if not) and a saved HF token present (422 if not) — these fail fast, matching today's UX of an immediate inline error rather than a pointless "running" state that immediately errors. If both pass, calls `prepare_state.start_prepare(...)` and returns `{"status": "running"}`.
- `GET /api/offers/{offer_id}/prepare/status` — validates ownership, returns `get_prepare_state(offer_id)`.

Three new download routes:
- `GET /api/offers/{offer_id}/cv`, `GET /api/offers/{offer_id}/cover-letter`, `GET /api/offers/{offer_id}/prep-sheet` — each validates ownership (404 if not found/not owned), 404s if that offer's corresponding path column is empty, otherwise returns a `FileResponse` with `Content-Disposition: attachment` so the browser downloads rather than navigates.

All five routes gated by `require_onboarding_complete_api`, same as every other Candidatures route.

**Deleted this sub-phase** (once the frontend stops needing them): `dashboard/app.py`'s `offer_prepare` route. `dashboard/templates/partials/offer_detail.html` and `partials/offer_notes.html` — flagged with `TODO(sub-phase D)` comments since sub-phase B — are **finally deleted**, since `offer_prepare` was their only remaining live renderer.

## Frontend

New `frontend/components/candidatures/prepare-panel.tsx` (separate component, same reasoning as `ScanButton` in sub-phase C — keeps `candidatures-client.tsx` from growing further), rendered as its own row in the detail panel, below the existing status quick-change buttons row:

- When `offer.status` is `"À envoyer"`/`"Envoyée"`/`"Relance"`: a "Sans fiche de préparation d'entretien" checkbox plus "✦ Préparer candidature (IA)" button. Clicking triggers `POST /api/offers/{id}/prepare` (a 422 response renders its message inline immediately, matching today's fast-fail UX for the two precondition checks); on success, polls `GET /api/offers/{id}/prepare/status` via TanStack Query's `refetchInterval` (same pattern as `ScanButton`: 2s while `"running"`, stops otherwise), showing the live `stage` text while running, the specific error message plus a "Réessayer" retry on `"error"`. On `"done"`, invalidates the `["offer", id]` query so the newly-populated `cv_path`/`cover_letter_path`/`prep_sheet_path` (and their new download links) appear without a manual refresh.
- When `offer.status` is `"Entretien RH"`/`"Entretien tech"`/`"Offre"`: the "✦ Préparer entretien" button, `navigator.clipboard.writeText(...)` with the same command template as today (parameterized by `offer.id`), no backend call.
- New CV/LM/Fiche prep rows added to the metadata `<dl>` in `candidatures-client.tsx` (sub-phases A/B never carried these fields over from the old template, since nothing populated them before this sub-phase) — each a real download link (`<a href="/api/offers/{id}/cv" download>` etc.), shown only when the corresponding path is non-empty.

## Testing

**Backend**: mirrors `tests/test_scan_state.py`'s pattern — unit tests for `prepare_state.py` (mocking `llm.analyze_offer`/`rewrite_cv_summary`/`write_cover_letter`/`generate_prep_questions` and the three PDF generators, the same way this repo's *existing* tests for `offer_prepare` already do — check `tests/test_dashboard_app.py`'s current `TestOfferPrepare` class for the established mocking pattern before writing new tests, reuse it rather than inventing a new one), plus the regression test this sub-phase exists to add: two different `offer_id`s get independent state (per-offer isolation, analogous to sub-phase C's per-user isolation test). Route tests for the two prepare routes (ownership, the two 422 preconditions) and the three download routes (ownership, 404 when the path column is empty, correct headers when present).

**Frontend**: same no-test-framework constraint as every prior phase — `tsc`/`eslint` plus manual interactive verification. Since a real prepare run means real Hugging Face API calls (not just an external scrape like sub-phase C's scan), the same safety approach applies: confirm the real `POST` fires and flips to `"running"` with one real click, then stop it immediately (don't let a real multi-step LLM+PDF pipeline run to completion during a UI verification pass), then verify the stage-progression/done/error states safely via a `window.fetch` mock in the browser. For the download links specifically, seed a fake `cv_path` directly in the DB (pointing at a dummy file) to confirm the link renders and the download route actually serves it, without needing a real completed prep run.

## Out of scope (this sub-phase specifically)

- `/stats`, `/profile`, `/settings` — separate future phases, unrelated to Candidatures.
- Any change to `modes/prepare-entretien.md`'s content or the Claude Code CLI mode it drives — out of scope, this sub-phase only ports the clipboard-copy button that references it.
