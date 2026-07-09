# Diggo — Stats page migration — Design Spec

Date: 2026-07-09
Status: approved

## Goal

Migrate `/stats` from FastAPI/Jinja2 to Next.js — the first page after the Candidatures migration (all 4 sub-phases done, see `docs/frontend-migration-status.md`). Single sub-phase: the page is entirely read-only (no filters, no mutations, no polling), so there's no A/B/C/D split like Candidatures needed.

## Context

Today `GET /stats` (`dashboard/app.py`) renders `dashboard/templates/stats.html`: 4 summary cards (total candidatures, response rate, interview count, stale follow-ups), a funnel chart (`_FUNNEL_STEPS` with conversion rates between steps, plus an "exits" section for Refusée/Abandonnée), a per-status breakdown (all `VALID_STATUSES`, bar + count), and the latest daily report (`reports/daily-*.md`, converted to HTML via `mistune`). All of it comes from `db.get_stats(user_id)` plus the `_build_funnel()` helper, both already backend logic — this migration is a straight port, no new computation.

## Backend

One new route in `dashboard/api.py`:

- `GET /api/stats` → `{"stats": {...}, "funnel": [...], "exits": [...], "max_count": int, "latest_report_html": str | null, "latest_report_date": str | null}`. `stats` is `db.get_stats()`'s return value unchanged (`total`, `response_rate`, `interview_count`, `stale_count`, `by_status`). `funnel`/`exits`/`max_count` come from `_build_funnel(stats["by_status"])`. `latest_report_html`/`latest_report_date` reuse the existing "find newest `reports/daily-*.md`, render with `mistune`" logic from the current route, unchanged.
- Gated by `require_onboarding_complete_api` (already exists, added in Candidatures-A — 403 with JSON `{"error": "onboarding_incomplete", "redirect": "..."}` instead of a redirect, so a `fetch()` caller can act on it).
- `_build_funnel()` moves from `dashboard/app.py` to `dashboard/db.py` (alongside `get_stats`, `VALID_STATUSES`, `_FUNNEL_STEPS`/`_EXIT_STEPS` — all stats-domain logic in one place) so `api.py` can import it without a circular dependency, mirroring how `parse_description()` moved to `db.py` during Candidatures-A.

Jinja2 cutover: delete `stats_page()` from `dashboard/app.py` and `dashboard/templates/stats.html` once nginx routes `/stats` to `web`. `STATUS_COLORS`/`GRADE_COLORS` module-level dicts and their `templates.env.globals` registration in `app.py` are only referenced by `stats.html` (confirmed by grep — Candidatures' Jinja2 templates are already gone) — delete them in the same commit as dead code.

## Frontend

- **`frontend/app/stats/page.tsx`**: async Server Component, same SSR auth-check pattern as `candidatures/page.tsx` (`fetch` to `/api/me` via `INTERNAL_API_URL`, forwarding the `Cookie` header, redirect to `/login` if no session). Renders `DashboardNav` (`activePath="/stats"`) + `StatsClient`.
- **`frontend/components/stats/stats-client.tsx`**: client component, `useQuery(['stats'], ...)` fetching `/api/stats`, handling the 401 case the same way the Candidatures fetch helpers do today (redirect to `/login`) and the 403 onboarding-incomplete case (redirect to the `redirect` field), and a loading/error state (skeleton or simple "Chargement…" text — no existing skeleton component to reuse, keep it minimal).
- **Summary cards**: 4 cards using `bg-card`/`border-border`/`text-muted-foreground`/`text-foreground` design tokens (replacing the old inline hex styles), same top gradient-accent-bar treatment is dropped in favor of the established teal accent (`text-primary`/`border-primary` on hover or a static thin top border in `bg-primary`) — keep it simple, a static `border-t-2 border-primary` per card, no per-card gradient variety (that was a Jinja2-era decoration, not part of the design-token system).
- **Funnel + per-status bars**: plain divs with inline `width: {pct}%` (same technique as today — no chart library, nothing here needs `recharts` or similar), using `bg-muted` for the track and `bg-primary` for the fill. Funnel step labels and exit labels use `getStatusColor()` from `frontend/lib/status-colors.ts` (already exists, ported during Candidatures-A) — reused as-is, no changes needed there.
- **Daily report**: `latest_report_html` rendered via `dangerouslySetInnerHTML` (server already sanitizes via `mistune` server-side, same trust boundary as today's Jinja2 `| safe` — the HTML is generated from the user's own local `reports/` files, not user-supplied input at request time). Empty state ("Aucun rapport disponible…") when `latest_report_html` is null. A `prose`-like wrapper class scoped to this block only (matching today's `.prose-report` CSS, ported to Tailwind's `prose` plugin if already available, otherwise a small scoped CSS block — check `frontend/app/globals.css` at implementation time for what's already there before adding new CSS).

No new dependencies (`@tanstack/react-query` already installed; no chart or markdown library needed since rendering stays server-side).

## Out of scope

- `/profile`, `/settings` — separate future phases, same treatment each time (per `docs/frontend-migration-status.md`).
- Any new stats/metrics not already computed by `db.get_stats()`/`_build_funnel()` — this is a straight port, not a feature addition.
