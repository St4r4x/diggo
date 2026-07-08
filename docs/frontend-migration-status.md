# Diggo — Next.js frontend migration — status & handoff

Date: 2026-07-09
Purpose: continuity doc for resuming this work in a fresh session/context. Read this first, then pick up at "Next step" below.

## Goal

Migrate the whole Diggo dashboard from FastAPI/Jinja2/HTMX to a Next.js frontend, one page at a time, keeping the FastAPI backend as a JSON API underneath. Full redesign (new design system) happens as part of the migration, not separately.

## Branch / environment state

- Branch: `claude/objective-gates-1d007a` (this worktree). **Not merged to `master`** past the Foundations phase — `master` is at `d43e383`. Everything below (Auth, Landing, Candidatures-A) exists only on this branch, by explicit user choice ("keep as-is" after Auth finished) — do not assume it's live anywhere else.
- To resume local dev: `supabase start` (local Postgres/Auth stack), repo-root `.env` already exists and is gitignored (has working `DATABASE_URL`/`SUPABASE_*`/`SECRET_KEY` values pulled from `supabase status` — don't recreate it, check it's still there first).
- To rebuild/preview: `docker compose build api web && docker compose up -d api web proxy` — preview on `http://localhost:8000`. `proxy` is nginx with a bind-mounted config; if you edit `proxy/nginx.conf` and the container doesn't pick it up, `docker compose restart proxy`.
- `frontend/.env.local` exists for local `npm run dev` (outside Docker) — has `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY`.

## Process being followed (repeat this for every remaining page/phase)

For each phase: **brainstorm → write spec to `docs/superpowers/specs/` → write plan to `docs/superpowers/plans/` (gitignored, not committed) → execute via `superpowers:subagent-driven-development`** (fresh implementer subagent per task, task-scoped reviewer after each, final whole-branch review at the end of the phase, fix rounds for Critical/Important findings). This has worked well seven times over (Foundations 7 tasks, Auth 5 tasks, Landing 2 tasks, Candidatures-A 3 tasks) — keep using it.

Key conventions established along the way (a fresh session should know these, they've caused real bugs when forgotten):
- **`CHANGELOG.md` must have exactly ONE `## [Unreleased]` header in the whole file, always.** New entries go into the existing `### Added`/`### Changed`/`### Removed` subsections under it. This has been violated and had to be fixed twice already — always `Read` the file first before editing it.
- Test files in this repo have **no shared `conftest.py`** — each test file defines its own DB fixtures (`_make_pg_db`, `_insert_row`, etc.). Never use `os.environ.setdefault("DATABASE_URL", ...)` at module level in a test file unless that file genuinely opens a DB connection — pytest collects every test file before running any of them, so a `setdefault` in a file that doesn't need it can silently poison `DATABASE_URL` for every file collected after it (this exact bug shipped once and was fixed in commit `4098330`).
- nginx (`proxy/nginx.conf`) routes page-by-page as each page migrates: exact-match `location = /` for the root, prefix `location /login` etc. for everything else migrated so far. Everything not yet migrated falls through to the default `location /` → `api` (FastAPI/Jinja2). `/_next/` must always route to `web` (Next.js's own static assets) — this was forgotten once and every migrated page rendered unstyled until fixed (commit `3a25405`).
- Dev servers (`npm run dev`) and Docker containers must always be started as **background** processes when a subagent verifies something — running them in the foreground blocks the whole subagent session (happened once, 10-minute stall).
- Design tokens (dark-default, teal accent `#2dd4bf`/`#0d9488`, Inter font) are established in `frontend/app/globals.css` — reuse `bg-background`/`text-foreground`/`bg-card`/`border-border`/`text-primary`/`bg-primary`/`text-muted-foreground`. Grade/status badges are the one deliberate exception (plain Tailwind palette classes, ported from the old Python `STATUS_COLORS`/`GRADE_COLORS` dicts) — multi-hue by nature, not part of the single-accent brand system.
- `frontend/components/dashboard-nav.tsx` + `frontend/components/logout-button.tsx` (added during Candidatures-A) are the shared nav for every authenticated page — reuse them, don't rebuild.
- TanStack Query (`@tanstack/react-query`) is the data-fetching library, wired via `frontend/app/providers.tsx` in the root layout — use `useQuery`/`useMutation`, invalidate the relevant query keys after mutations.
- SSR auth-check pattern (used by landing page and Candidatures): an async Server Component calls `http://api:8000/api/me` (via `INTERNAL_API_URL` env var, already set in `docker-compose.yml`) directly over the Docker network, forwarding the `Cookie` header from `next/headers`, `cache: "no-store"`.

## Phases done (all reviewed clean, "ready to merge")

1. **Frontend Foundations** — Next.js scaffold, design tokens, shadcn/ui (Button/Card/Input/Label), Docker 3-service split (`api`/`web`/`proxy`), nginx proxy. **Merged to master.** Spec: `docs/superpowers/specs/2026-07-08-nextjs-frontend-redesign-design.md`.
2. **Auth pages** — login/signup/confirm/reset-password migrated, `/auth/session` moved to `/api/auth/session`. Spec: `docs/superpowers/specs/2026-07-08-auth-pages-migration-design.md`.
3. **Landing page** (`/`) — SSR auth-check + redirect, marketing copy generalized for a broader "cadres multi-secteurs" audience (no more explicit Greenhouse/Lever/Ashby naming). Spec: `docs/superpowers/specs/2026-07-08-landing-page-migration-design.md`.
4. **Candidatures sub-phase A** (list + filters + detail, read-only) — `GET /api/offers`, `GET /api/offers/{id}`, TanStack Query, the shared dashboard nav (first protected page, nav didn't exist before). `/candidatures` now served by `web`. Spec: `docs/superpowers/specs/2026-07-08-candidatures-list-detail-design.md`.

**Known minor issues flagged by reviews, not yet fixed (low priority, noted for whoever touches these files next):**
- `frontend/components/candidatures/candidatures-client.tsx`: a 401 (expired session) on `/api/offers` has no client-side handling — only 403 (onboarding incomplete) redirects. Worth a one-line fix (`if (res.status === 401) window.location.href = "/login"`) when sub-phase B touches this file anyway.
- `dashboard/templates/partials/scan_status.html`: has a dangling `hx-get="/offers"` targeting a `#offer-list` element that no longer exists (both lived only in the now-deleted `index.html`). Inert today (no UI can currently trigger a scan), but whoever migrates the scan flow (sub-phase C) needs to know this partial can't be trusted as-is.
- `dashboard/templates/partials/offer_form.html`: the "Annuler" button HTMX-GETs the now-deleted `/offers/{id}` route. Also inert (its only container, `#offer-detail` in `index.html`, is gone) — whoever migrates the edit form (sub-phase B, see below) should just not reuse this template.

## Candidatures is split into 4 sub-phases (A done, B/C/D not started)

Decision: `/candidatures` cuts over to `web` progressively (already happened, end of sub-phase A) rather than all-at-once at the end — each sub-phase adds functionality to the now-live page, no more nginx changes needed for B/C/D.

### Next step: Candidatures sub-phase B (mutations) — design approved, NOT yet written to a spec file or plan

This is what to do first when resuming. The design below was approved in conversation but never written to `docs/superpowers/specs/` — **do that first** (spec self-review, commit, then `writing-plans`, then `subagent-driven-development`), don't skip straight to planning.

**Backend** — one flexible route in `dashboard/api.py`, replacing the Jinja2 `offer_status`/`offer_notes`/`offer_save` routes:
- `PATCH /api/offers/{offer_id}` — accepts any subset of the fields `db.update()` already whitelists (`company`, `role`, `offer_url`, `send_date`, `follow_up_date`, `contacts`, `status`, `notes`, plus whatever else `db.update()`'s existing `allowed` set includes — check `dashboard/db.py`). Validates `status` against `VALID_STATUSES` (422 if invalid, matching the old `offer_status` route's behavior). 404 if the offer doesn't exist/isn't owned by the user. Response: `{"offer": {...}, "description": {...}}` — same shape as `GET /api/offers/{id}`, so the frontend can reuse one type.
- `DELETE /api/offers/{offer_id}` — 404 if missing, else deletes, returns `{"ok": true}`.

Chosen over 3 separate mirrored routes (status/notes/full-edit) because `db.update()` is already a flexible whitelist-based updater — one endpoint is less code and lets the frontend use one `useMutation` hook for status buttons, notes autosave, and the edit form alike.

**Frontend** — all extending the existing `frontend/components/candidatures/candidatures-client.tsx` from sub-phase A (no new page, no nginx change):
- Status quick-change buttons in the detail panel (9 statuses, matching `VALID_STATUSES`) → `PATCH {status}` → invalidate the `offers` and `offer` query keys so both list and detail refresh.
- Notes field with 800ms autosave debounce (same debounce pattern already used for the search input — a `useEffect`+`setTimeout` pair, not a new library) → `PATCH {notes}`.
- Delete button with a confirm step → `DELETE`, then deselect the offer (clear `selectedId` state) and let the list refetch.
- Edit form — **simplified to 6 fields** (user's explicit choice, not full parity): entreprise (`company`), rôle (`role`), URL (`offer_url`), date d'envoi (`send_date`), date de relance (`follow_up_date`), contacts (`contacts`). Dropped vs. the original 14-field form: `status`/`notes` (redundant — already editable elsewhere in the detail panel), `detection_date` (auto-set, rarely manually corrected), `score_grade`/`score_value` (computed by the scoring engine, not manually overridden in this pass), `cv_path`/`cover_letter_path` (managed by the prepare flow in sub-phase D, not manual text entry). The edit form replaces the detail panel view temporarily (toggle via a "Modifier"/"Annuler" affordance), matching the original UX pattern.

**Suggested task decomposition** (not yet written as a formal plan):
1. Backend — `PATCH`/`DELETE` routes + tests (mirror the TDD-per-route pattern from sub-phase A's Task 1; note `dashboard/templates/partials/offer_detail.html` is STILL used by `offer_prepare` — don't delete it yet, sub-phase D still needs it. The Jinja2 `offer_status`/`offer_notes`/`offer_save`/`offer_edit_form` routes and `offer_form.html` template become deletable once this phase's frontend work lands and cuts them off — but only after the frontend actually replaces their UI, same "delete what you replace, not more" discipline as every prior phase).
2. Frontend — status buttons + notes autosave + delete (extends the existing detail panel, no new files needed beyond edits to `candidatures-client.tsx`).
3. Frontend — edit form (6 fields, likely its own small component file, e.g. `frontend/components/candidatures/offer-edit-form.tsx`).
4. Backend cleanup — delete the now-fully-replaced Jinja2 mutation routes + `offer_form.html` (NOT `offer_detail.html` — still needed by `offer_prepare`, sub-phase D). Update/delete corresponding tests in `tests/test_dashboard_app.py` (`TestOfferEdit`, `TestOfferStatus`, `TestOfferNotes`, `TestOfferDelete` — check current file for exact class names/line numbers, they may have shifted since Candidatures-A's deletions).

### After B: sub-phases C and D (not designed yet)

- **Sub-phase C — scan flow.** Trigger + 2s polling (`app.state.scan_status`/`app.state.scan_result`, currently a **global singleton, not per-user** — worth flagging as a pre-existing bug/design smell when this gets designed, not something to silently carry forward without at least noting it). Needs its own brainstorm.
- **Sub-phase D — "Préparer candidature"/"Préparer entretien".** **User already decided this becomes async-with-polling** (like the scan flow), not the current 30-60s blocking synchronous POST — this is a real backend architecture change (new per-offer task-state tracking, since the existing scan pattern is a single global slot and prepare is per-offer, potentially concurrent across offers). Needs its own brainstorm before writing a spec — this is the most architecturally involved remaining sub-phase.

## After Candidatures (all 4 sub-phases): remaining top-level phases

Stats (`/stats`) → Profile (`/profile`) → Settings (`/settings`) — none brainstormed yet. Each gets the same brainstorm → spec → plan → subagent-driven-development treatment. Check `dashboard/app.py`/`dashboard/templates/` for their current Jinja2 implementations when starting each.

## Other loose threads (not blocking, mentioned earlier in this session)

- `docs/todo-product-ideas.md` — backend language/framework options, CV/LinkedIn import for onboarding, multi-LLM support, plus a handful of unprompted ideas (CI/CD is currently completely absent from this repo — no `.github/workflows/` — probably the highest-leverage non-migration investment). Written earlier this session per explicit user request, not acted on.
- `docs/todo-deployment.md` (pre-dates this session, 2026-07-03) — partially stale (auth/multi-tenancy Groups 0/5 are now done), but Group 6 (security headers, rate limiting, RGPD/export/delete-account) and Group 3 (scraping hardening) are still fully open and worth revisiting once the frontend migration is further along.
