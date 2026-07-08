# Diggo — Candidatures: mutations (status, notes, delete, edit) — Design Spec

Date: 2026-07-09
Status: approved

## Goal

Migrate the write path of the Candidatures page — status changes, notes autosave, delete, and edit — from FastAPI/Jinja2/HTMX to Next.js. This is sub-phase B of four (A: list/detail read-only — done, B: mutations — this spec, C: scan flow, D: prepare flow), extending the page that went live at the end of sub-phase A rather than introducing a new route or nginx change.

## Context

Today, mutations on `/candidatures` are three separate Jinja2/HTMX routes in `dashboard/app.py`: `POST /offers/{id}/status`, `POST /offers/{id}/notes`, `POST /offers/{id}` (full edit save, backed by `GET /offers/{id}/edit` for the form), and `DELETE /offers/{id}`. All render Jinja2 partials (`offer_detail.html`, `offer_notes.html`, `offer_form.html`, `offer_empty.html`) that no longer have a live container since `index.html` was deleted in sub-phase A — none of these routes currently render anything a user can see; the read path already fully replaced them on the frontend. This sub-phase gives the frontend equivalent write actions and deletes the now-dead Jinja2 routes/templates.

## Backend

One flexible route in `dashboard/api.py`, replacing `offer_status`, `offer_notes`, and `offer_save`:

- `PATCH /api/offers/{offer_id}` — body is a partial JSON object of any subset of `db.update()`'s existing whitelist (`company`, `role`, `offer_url`, `send_date`, `follow_up_date`, `contacts`, `status`, `notes` — the fields this sub-phase's frontend actually sends; `db.update()` also whitelists `detection_date`/`score_grade`/`score_value`/`cv_path`/`cover_letter_path`/`prep_sheet_path`/`description`/`portal` for other callers, unaffected). If `status` is present, validate against `VALID_STATUSES` first (422 with `{"error": "invalid_status"}` if not, matching `offer_status`'s current behavior — checked before touching the DB, same as today). 404 if the offer doesn't exist or isn't owned by the current user (`db.get_by_id` check, same pattern as `get_offer`). Response: `{"offer": {...}, "description": {...}}` — identical shape to `GET /api/offers/{id}`, so the frontend reuses `OfferDetailResponse` and one `useMutation` invalidates the same query shape it fetches.
- `DELETE /api/offers/{offer_id}` — 404 if missing/not owned (`db.get_by_id` check first, since `db.delete()` is a no-op on a missing row and would otherwise silently 200), else `db.delete()` and return `{"ok": true}`.

Both use `require_onboarding_complete_api` (same dependency as the sub-phase A read routes) — a user who can view Candidatures can mutate it.

Chosen over three separate mirrored routes (status/notes/full-edit) because `db.update()` is already a flexible whitelist-based updater — one endpoint is less code and lets the frontend use a single `useMutation` hook for status buttons, notes autosave, and the edit form alike.

**Deleted this sub-phase** (once the frontend stops needing them): `dashboard/app.py`'s `offer_status`, `offer_notes`, `offer_save`, `offer_edit_form` routes, and `dashboard/templates/partials/offer_form.html`. `offer_delete` (the Jinja2 `DELETE /offers/{id}` route) is also deleted — superseded by the new JSON route, same URL path shape but returning JSON instead of an HTML partial (no path collision since the JSON route lives under `/api/offers/{id}` — different prefix). `dashboard/templates/partials/offer_detail.html` and `partials/offer_notes.html` are **not** deleted — `offer_prepare` (sub-phase D, not migrated) still renders `offer_detail.html`, which itself `{% include %}`s `offer_notes.html` (line 184), so both stay alive transitively even after the `offer_notes` POST route itself is deleted. Whoever migrates `offer_prepare` (sub-phase D) is the one who can finally retire both templates.

Test file `tests/test_dashboard_app.py`: delete `TestOfferEdit` (line 159), `TestOfferDelete` (254), `TestOfferStatus` (266), `TestOfferNotes` (292) — line numbers as of this spec, confirm at implementation time since earlier edits in this sub-phase may shift them. `TestOfferPrepare` (844) stays untouched (sub-phase D). New tests for `PATCH`/`DELETE /api/offers/{id}` go in `tests/test_api_routes.py`, alongside the sub-phase A `GET /api/offers`/`GET /api/offers/{id}` tests.

## Frontend

All extending `frontend/components/candidatures/candidatures-client.tsx` (sub-phase A) — no new page, no nginx change. One `useMutation` wraps `PATCH /api/offers/{id}`, invalidating `["offers", filters]` (all filter variants, so use a predicate/prefix match, not one exact key) and `["offer", id]` on success, so the list and detail panel both refresh from the single source of truth. A second `useMutation` wraps `DELETE`.

- **Status quick-change buttons**: the 9 `VALID_STATUSES` values as buttons in the detail panel (reusing `statusColor()` for each button's own color), each firing the shared mutation with `{status: <value>}`.
- **Notes field**: a `<textarea>` bound to `detail.offer.notes`, same 800ms-debounce pattern as the existing 300ms search-input debounce in this file (`useEffect` + `setTimeout`, no new library) — on the debounced value changing, fire the shared mutation with `{notes: <value>}`.
- **Delete button**: a confirm step (native `window.confirm` — no dialog library needed for a single Yes/No), then the delete mutation; on success, clear `selectedId` (deselects, panel returns to the "select an offer" empty state) and invalidate `["offers"]` so the list drops the deleted row.
- **Edit form** — 6 fields, not full parity with the old 14-field form (user's explicit choice): entreprise (`company`), rôle (`role`), URL (`offer_url`), date d'envoi (`send_date`), date de relance (`follow_up_date`), contacts (`contacts`). Dropped: `status`/`notes` (already editable elsewhere in the detail panel), `detection_date` (auto-set, rarely corrected), `score_grade`/`score_value` (computed by the scoring engine), `cv_path`/`cover_letter_path` (sub-phase D's prepare flow manages these, not manual text entry). New file `frontend/components/candidatures/offer-edit-form.tsx`, taking the current `Offer` and an `onSave`/`onCancel` pair — the detail panel toggles between its normal read view and this form via a `isEditing` boolean state (a "Modifier"/"Annuler" button pair), matching the original HTMX swap-in-place UX. Submitting fires the shared mutation with the 6 fields, then flips `isEditing` back to `false` on success.

The known sub-phase A minor issue — `/api/offers` 401 (expired session) not redirecting to `/login` (only 403 onboarding-incomplete does) — gets fixed here too, since this sub-phase already touches `fetchOffers`/error handling in this file: add `if (res.status === 401) window.location.href = "/login";` alongside the existing 403 branch, and apply the same 401 check to the new mutation calls (a session can expire between page load and a status-button click).

## Out of scope (this sub-phase specifically)

- Scan trigger + polling — sub-phase C.
- "Préparer candidature"/"Préparer entretien" — sub-phase D (includes the async-with-polling architecture change already agreed for this flow).
- `dashboard/templates/partials/scan_status.html`'s dangling `hx-get="/offers"` (targets a container that no longer exists, inert today) — noted for whoever migrates the scan flow, not this sub-phase's concern.
- `/stats`, `/profile`, `/settings` — separate future phases, unrelated to Candidatures.
