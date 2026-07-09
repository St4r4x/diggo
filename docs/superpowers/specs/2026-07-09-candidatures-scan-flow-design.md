# Diggo — Candidatures: scan flow — Design Spec

Date: 2026-07-09
Status: approved

## Goal

Migrate the scan trigger + live-progress UI from FastAPI/Jinja2/HTMX to Next.js, and fix a pre-existing bug along the way: scan state is currently a single global dict shared across every user of the process, not scoped per user. This is sub-phase C of four Candidatures sub-phases (A: list/detail read-only — done, B: mutations — done, C: scan flow — this spec, D: prepare flow), extending the page already live from sub-phases A/B.

## Context

Today, `POST /scan/start` kicks off a background `asyncio.create_task` running the scrape → dedup → score → import pipeline (`scripts/import_offers.py`), and `GET /scan/status` is polled by HTMX every 2s while running. Both routes read/write `app.state.scan_status`/`app.state.scan_result` — one dict on the FastAPI app instance, shared by every request regardless of which user made it. The imported offers themselves are correctly scoped by `user_id` in the DB; only the *polling state* is unscoped. Neither route is currently reachable from any live UI — the button lived only in `dashboard/templates/index.html`, deleted in sub-phase A — so this bug is latent, not yet observed in practice, but would surface the moment two users scan concurrently.

`dashboard/templates/partials/scan_status.html`'s `"done"` state HTMX-swaps in `hx-get="/offers" hx-trigger="load" hx-target="#offer-list"` to refresh the list after a scan — `#offer-list` no longer exists (it lived in the deleted `index.html`), so this is also dead and needs a new equivalent on the JSON/TanStack Query side.

## Backend

Two new JSON routes in `dashboard/api.py`, replacing `POST /scan/start` and `GET /scan/status`:

- `POST /api/scan/start` — starts a background scan for the current user. Returns `{"status": "running"}`. If the user already has a scan running, this is a no-op that returns the same `{"status": "running"}` response (matches today's `scan_start` exactly — both branches return the identical response today, no separate "already running" signal; the frontend just resumes polling either way).
- `GET /api/scan/status` — returns `{"status": "idle" | "running" | "done" | "error", "result": {"inserted": int, "skipped": int, "found": int, "scored": int, "abandoned": int, "error": str}}` for the current user only.

**Per-user state.** A new module-level `dict[str, dict]` (keyed by `user_id`) replaces `app.state.scan_status`/`app.state.scan_result`. `_run_scan_task`/`_start_scan` (currently free functions in `dashboard/app.py` operating on `app_state`) move to operate on this per-user dict instead — same function shapes, different storage target. Same lifetime/durability characteristics as today (in-memory, lost on process restart, fine for this app's single-container deployment — no multi-replica sync problem to solve). Exact file placement (inline in `api.py` vs. a new small `dashboard/scan_state.py`) decided at plan-writing time based on how large the resulting `api.py` addition looks.

Both routes gated by `require_onboarding_complete_api`, same as every other Candidatures route.

**Deleted this sub-phase** (once the frontend stops needing them): `dashboard/app.py`'s `scan_start`, `scan_status` routes and the `_run_scan_task`/`_start_scan`/`_scan_lock` helpers (moved, not just deleted — see above). `dashboard/templates/partials/scan_status.html` deleted — it's the one template whose only container (`index.html`) is already gone, unlike `offer_detail.html`/`offer_notes.html` which sub-phase B correctly left alone for `offer_prepare`.

## Frontend

New `frontend/components/candidatures/scan-button.tsx`, rendered in `candidatures-client.tsx` at the same spot the old `{% include "partials/scan_status.html" %}` sat (end of the filter panel, above the offer list).

- `useQuery(['scan-status'], fetchScanStatus, { refetchInterval: (query) => query.state.data?.status === "running" ? 2000 : false })` — TanStack Query's built-in polling, matching every other data fetch in this codebase; polling stops automatically once status leaves `"running"`, no manual `setInterval`.
- Four visual states, reproducing the old partial's copy and behavior on the design system: idle (`⟳ Scanner` button), running (disabled button, spinner, live `"Scan… {found} trouvées, {scored} scorées"` count when available), done (`✓ {inserted} nouvelle(s), {abandoned} expirée(s) — Scanner`, clickable to scan again), error (`✗ Erreur — Réessayer`).
- A `useMutation` wraps `POST /api/scan/start`; on success, invalidates `['scan-status']` so polling picks up the new `"running"` state immediately instead of waiting up to 2s.
- When a `['scan-status']` poll returns `"done"` (transitioning from `"running"`), also invalidate `['offers']` — this replaces the old dead `hx-get="/offers" hx-trigger="load"` swap with the TanStack Query equivalent: the list refreshes once new offers have actually landed.

## Testing

**Backend**: tests move to `tests/test_api_routes.py`, mirroring the existing `TestScan` class's pattern in `tests/test_dashboard_app.py` (monkeypatch `asyncio.create_task` so no real scan pipeline runs, then assert on state/response) — adapted from asserting on rendered HTML to asserting on JSON. Plus the regression test this sub-phase exists to add: two different `user_id`s get independent scan state (start as user A, confirm `GET /api/scan/status` for user B still reports `"idle"`).

**Frontend**: no test framework in this repo (confirmed project-wide, not new to this phase) — verified via `tsc --noEmit`, `eslint`, and manual interactive browser testing using the `DEV_AUTO_LOGIN` pattern established in sub-phase B (seed a throwaway test identity, click through start → poll → done, confirm the list actually refreshes, clean up afterward).

## Out of scope (this sub-phase specifically)

- "Préparer candidature"/"Préparer entretien" — sub-phase D (includes the async-with-polling architecture change already agreed for that flow — this sub-phase's per-user state pattern is the template D will extend to per-offer, potentially-concurrent state).
- `dashboard/templates/partials/offer_detail.html`/`offer_notes.html` and their dangling `hx-*` targets (flagged during sub-phase B's final review) — still rendered by `offer_prepare`, untouched until sub-phase D retires that route.
- `/stats`, `/profile`, `/settings` — separate future phases, unrelated to Candidatures.
