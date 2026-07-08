# Diggo — Candidatures: list + filters + detail (read-only) — Design Spec

Date: 2026-07-08
Status: approved

## Goal

Migrate the read path of Diggo's core page — the offers list with filters and the detail panel — from FastAPI/Jinja2/HTMX to Next.js. This is the first of four sequential sub-phases covering the full Candidatures page (A: list/detail read-only, B: mutations, C: scan flow, D: prepare flow), each building on a page that's already live in production between sub-phases (see Rollout below).

## Context

Today `GET /candidatures` renders `dashboard/templates/index.html`: a two-column layout (filterable list on the left, detail panel on the right), backed by `GET /offers` (filtered list partial, re-fetched via HTMX on every filter change) and `GET /offers/{id}` (detail partial, fetched on list-item click). Write actions (status change, notes autosave, edit, delete, prepare, scan) are out of scope for this sub-phase — they stay on the current Jinja2 implementation until sub-phases B/C/D replace them one at a time.

## Rollout model (applies to all four Candidatures sub-phases)

Unlike Auth/Landing (each cut over in one shot once fully built), Candidatures cuts over **progressively**: this sub-phase ends by pointing nginx's `/candidatures` at `web`, even though status changes/notes/scan/prepare aren't built yet. Sub-phases B/C/D then add functionality directly to this now-live page — no further nginx changes needed after this sub-phase. Users see a temporarily read-only Candidatures page between sub-phases; this tradeoff is accepted in exchange for continuous, fully-integrated verification at every step instead of one large late cutover.

## Backend

Two new JSON routes in `dashboard/api.py`, reusing `db.py`'s existing `get_all`/`get_by_id`/`get_followups` and `app.py`'s existing `_parse_description` helper unchanged:

- `GET /api/offers?status=&grade=&q=&sal_min=` → `{"offers": [...], "followup_ids": [1, 5, 9], "statuses": [...]}`. Filters map 1:1 to `db.get_all()`'s existing `filters` dict (empty/absent params are simply omitted, matching today's `offer_list` route). `statuses` is `VALID_STATUSES` from `db.py`, included so the frontend doesn't hardcode the list.
- `GET /api/offers/{offer_id}` → `{"offer": {...}, "description": {"mission": "", "profil": "", "stack": "", "avantages": "", "contrat": "", "salaire": ""}}` (the parsed-description shape `_parse_description` already produces). 404 (FastAPI's default JSON error body) if the offer doesn't exist or belongs to another user (`get_by_id` already scopes by `user_id`).

**Onboarding gate, JSON-friendly.** Both routes need the same "must be authenticated AND have completed onboarding" gate `require_onboarding_complete` already enforces for the Jinja2 routes — but that dependency raises `HTTPException(302, redirect to /profile or /settings)`, which is wrong for a `fetch()` caller (following a 302 would return HTML, not JSON, and silently break `response.json()`). A new `require_onboarding_complete_api` dependency in `dashboard/auth.py` mirrors the existing `get_current_user_api`/`get_current_user` pairing: same logic as `require_onboarding_complete`, but raises `HTTPException(403, detail={"error": "onboarding_incomplete", "redirect": "/profile"})` (or `"/settings"`) instead of a 302. FastAPI serializes arbitrary JSON-serializable `detail` automatically — no custom exception handler needed.

**Page-level auth/onboarding check.** `frontend/app/candidatures/page.tsx` is an async Server Component (same SSR pattern as the landing page) that calls `/api/me` (via `INTERNAL_API_URL`, already wired) before rendering: no session → redirect to `/login`; session present → render the client-side interactive list+detail component, which itself calls `/api/offers` and handles the 403 onboarding-incomplete case client-side (redirect to whatever `redirect` field the response carries) — the SSR check only handles the "not logged in at all" case for speed/no-flash, the same way Landing's SSR check works, while the finer-grained onboarding-state check happens where the data is actually fetched.

Jinja2 routes deleted at the end of this sub-phase (once nginx stops routing `/candidatures` to `api`): `GET /candidatures` (`index()`), `GET /offers` (`offer_list()`), `GET /offers/{offer_id}` (`offer_detail()`) in `dashboard/app.py`, plus `dashboard/templates/index.html` and `dashboard/templates/partials/offer_list.html`. `dashboard/templates/partials/offer_detail.html` is **not** deleted — `offer_save`, `offer_status`, and `offer_prepare` (none migrated yet) still render it; it's deleted whichever later sub-phase migrates the last of those three. `GET /offers/{offer_id}/edit` is likewise **not** deleted yet — migrated in sub-phase B.

`_parse_description()` (currently a module-private helper in `dashboard/app.py`, used by both the route this sub-phase deletes and four routes that stay) moves to `dashboard/db.py` as a public `parse_description()` function, so both `dashboard/app.py` (still-live routes) and `dashboard/api.py` (new route) can import it without a circular import between `app.py` and `api.py`.

## Frontend

- **New dependency**: `@tanstack/react-query`, with a `QueryClientProvider` added to the root layout (`frontend/app/layout.tsx`) — shared infrastructure every later Candidatures sub-phase (and any future page with server state) builds on.
- **`frontend/app/candidatures/page.tsx`**: the SSR auth-check Server Component described above, rendering a client component for the actual UI.
- **List + filters**: two-column layout matching the current one (list column, detail column). Search input (300ms debounce, matching today's `keyup changed delay:300ms`), status/grade/salary `<select>`s — all four params feed a single `useQuery(['offers', filters], ...)` call, so any filter change refetches automatically via TanStack Query's key-based caching (no manual debounce-and-refetch wiring beyond the search input's own debounce).
- **Follow-up banner**: amber bar showing `followup_ids.length` when non-zero, "Voir" click sets the status filter to "Envoyée".
- **Detail panel**: read-only rendering of the selected offer (metadata, parsed description sections) fetched via `useQuery(['offer', id], ...)`, no write actions yet (no status buttons, no notes field, no edit/delete/prepare buttons — those are sub-phases B/D).
- **Grade/status badges**: plain Tailwind palette utility classes (`bg-green-600`, `bg-amber-600`, etc.), ported directly from the existing Python `STATUS_COLORS`/`GRADE_COLORS` dicts into a shared TS constant. This is a deliberate exception to the "design tokens only" rule for single-accent brand elements — grade/status differentiation is inherently multi-hue and was never part of the teal-accent brand system to begin with, in the current app or the redesign.

## Out of scope (this sub-phase specifically — all covered by B/C/D)

- Status changes, notes autosave, edit form, delete — sub-phase B.
- Scan trigger + polling — sub-phase C.
- "Préparer candidature"/"Préparer entretien" — sub-phase D (includes the async-with-polling architecture change agreed for this flow).
- `/stats`, `/profile`, `/settings` — separate future phases entirely, unrelated to Candidatures.
