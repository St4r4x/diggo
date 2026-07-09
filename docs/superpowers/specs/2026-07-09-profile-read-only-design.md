# Diggo — Profile: read-only page (sub-phase A) — Design Spec

Date: 2026-07-09
Status: approved

## Goal

Migrate the read path of Diggo's Profile page (`/profile`) from FastAPI/Jinja2 to Next.js. This is the first of two sequential sub-phases (A: read-only, B: mutations — contact/résumé editing, CV meta/experience/skills/certifications/education CRUD), following the same progressive-rollout model Candidatures used, but shorter: Profile has no async state machine (no scan/prepare equivalent), so two sub-phases is enough, unlike Candidatures' four.

## Context

Today `GET /profile` (`dashboard/app.py`) renders `dashboard/templates/profile.html`: an accordion UI (Coordonnées / Résumé / CV, collapsible via inline JS) with an onboarding-progress banner at the top, and a CV section with FR/EN tabs showing summary, experience (each entry has its own bullet list), skills, certifications, and education. Backed by `profile_parser.load_profile()` (contact fields + free-text résumé — file-migration-aware, not `user_data.py`'s separately-existing `get_profile()`, which the current route does not call) and `user_data.get_cv(lang=...)` (DB-backed, also file-migration-aware on first load). Write actions (all 8 mutation routes: `/profile/contact`, `/profile/text`, `/profile/cv/meta`, `/profile/cv/experience` POST+DELETE, `/profile/cv/skills`, `/profile/cv/certifications`, `/profile/cv/education`) are out of scope for this sub-phase — they stay on the current Jinja2 implementation until sub-phase B replaces them.

Four templates in `dashboard/templates/partials/` — `profile_education.html`, `profile_experience.html`, `profile_projects.html`, `profile_skills.html` — are confirmed orphaned (grepped, zero references anywhere in `dashboard/`). Distinct from the `profile_cv_*.html` partials, which are live. `dashboard/profile_parser.py`'s `load_profile()` still returns empty `summary`/`experience`/`skills`/`education`/`certifications`/`projects` keys as a compat shim for these same orphaned partials, explicitly commented `# ponytail: compat shim — profile.html partials still use these; cleared in Task 7` (`dashboard/profile_parser.py:234-240`) — confirming they're known-dead, not an oversight. Deletion of the templates is deferred to sub-phase B's cutover task, same pattern as `offer_empty.html` during the Candidatures/Stats housekeeping; the shim keys in `load_profile()` itself are left alone (still needed by the live Jinja2 route until sub-phase B removes it) — this sub-phase's new API route simply doesn't forward them (see Backend section).

## Rollout model

Unlike Stats (single sub-phase, immediate cutover), Profile cuts over progressively like Candidatures: this sub-phase ends without touching `proxy/nginx.conf` — `/profile` keeps being served by `api` (Jinja2) until sub-phase B, which adds the mutation routes directly onto this now-built page and only then flips nginx and deletes the Jinja2 side. Users see no visible change between sub-phases; this sub-phase is purely additive (new `/api/profile` route + an unrouted Next.js page) until B cuts over.

## Backend

One new route in `dashboard/api.py`:

- `GET /api/profile` → `{"profile": {"contact": {name, title, email, phone, location, linkedin, github}, "profile_md": str}, "cv": {...FR CV...}, "cv_en": {...EN CV...}, "onboarding": {...}}`. `profile` comes from `profile_parser.load_profile(conn, user_id)` (same function the current Jinja2 route calls — not `user_data.get_profile()`, a separate, unrelated function operating on the same `user_profiles` table that the current route does not use; this migration preserves exact current behavior, not an opportunity to reconcile the two), with only the `contact`/`profile_md` keys forwarded into the response — the route does **not** pass through `load_profile()`'s empty `summary`/`experience`/`skills`/`education`/`certifications`/`projects` compat-shim keys (see Context), since those exist only for the orphaned Jinja2 partials this migration doesn't use. `cv`/`cv_en` come from `user_data.get_cv(conn, user_id, lang="fr")` / `lang="en"` unchanged. `onboarding` comes from `user_data.get_onboarding_state(conn, user_id)` unchanged.
- Gated by `get_current_user_api` (already exists, 401 only) — **not** `require_onboarding_complete_api`. Profile is where a user completes onboarding, so it cannot itself require onboarding to be complete; this matches the current Jinja2 route's `get_current_user` dependency exactly.

No routes are deleted in this sub-phase — `dashboard/app.py`'s `profile_page()` and all 8 mutation routes stay live, since `/profile` keeps routing to `api` until sub-phase B.

## Frontend

- **`frontend/app/profile/page.tsx`**: async Server Component, same SSR auth-check pattern as every other protected page (`getSessionUser()` from the existing shared `frontend/lib/session.ts` — reused as-is, no changes needed there since Profile's "must be logged in" check is identical to Stats'/Candidatures', only the onboarding-completeness requirement differs and that's enforced page-content-side, not at the SSR gate). Renders `DashboardNav` (`activePath="/profile"`) + `ProfileClient`.
- **`frontend/components/onboarding-banner.tsx`**: new shared component (not Profile-specific — `dashboard/templates/settings.html` also includes the equivalent Jinja2 partial today, and Settings' own future migration will reuse this component the same way `dashboard-nav.tsx` became shared infrastructure during Candidatures-A). Takes an `onboarding: {is_complete, profile_complete, search_complete, hf_token_complete}` prop, renders the progress line with links to `/settings#search`/`/settings#hf-token` when incomplete, renders nothing when `is_complete`.
- **`frontend/components/profile/profile-client.tsx`**: client component, `useQuery(['profile'], ...)` fetching `/api/profile`, 401 handling via the existing `redirectOnUnauthenticated()` helper (`frontend/lib/api-errors.ts`, extracted during the Stats phase — reused here, not reimplemented). No 403/onboarding-redirect handling needed (route has no onboarding gate).
  - Renders `OnboardingBanner` at the top.
  - **Contact card** and **résumé card**: two always-visible `Card`s using `bg-card`/`border-border`/`text-muted-foreground`/`text-foreground` design tokens — replacing the old accordion with the same always-visible card-stack layout Candidatures/Stats already established. Contact card shows name/title/email/phone/location/linkedin/github (each conditionally rendered when non-empty, matching the current template's `{% if %}` guards); résumé card shows the free-text `profile_md` content.
  - **CV card**: one `Card` with an FR/EN toggle — plain local `useState<"fr" | "en">`, two buttons (not a generic Tabs primitive; the language set is fixed at exactly two, so a dedicated shadcn `Tabs` component would be unused generality). Below the toggle, read-only sections for summary, experience (each entry: title/company/type/period + its bullet list), skills (grouped by category, matching `get_cv()`'s `{category, skill}` shape), certifications (name/issuer/year), and education (degree/school/year) — no add/edit/delete affordances in this sub-phase.
- No new npm dependencies.

## Out of scope (this sub-phase — covered by sub-phase B)

- All 8 mutation routes (contact, résumé, CV meta/experience/skills/certifications/education) and their corresponding edit/add/delete UI — sub-phase B.
- nginx cutover, Jinja2 route/template deletion, orphaned-partials cleanup — sub-phase B's final task.
- `/settings` — a separate future phase entirely, unrelated to Profile (though it will reuse `onboarding-banner.tsx` built here).
