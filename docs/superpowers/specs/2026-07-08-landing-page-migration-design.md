# Diggo — Landing page migration to Next.js — Design Spec

Date: 2026-07-08
Status: approved

## Goal

Migrate the public landing page (`/`) from FastAPI-rendered Jinja2 to the Next.js frontend, on top of the "Frontend Foundations" and "Auth pages migration" work already merged. This is the third of seven planned migration phases (Foundations → Auth → **Landing** → Candidatures → Stats → Profile → Settings).

## Context

Today `GET /` in `dashboard/app.py` has dual behavior: an anonymous visitor gets the marketing landing page (200, `dashboard/templates/landing.html`); an authenticated visitor gets a 302 redirect to `/candidatures` (`get_current_user_optional`, which returns `None` instead of raising when there's no valid session — unlike `get_current_user`/`get_current_user_api`). Every other protected page (`/candidatures`, `/stats`, `/profile`, `/settings`) is untouched by this migration and keeps being served by `api` via Jinja2, redirecting unauthenticated visitors to `/login` exactly as today (already reachable via `web` since the Auth migration).

## Architecture

- **Auth check via server-to-server SSR call.** The Next.js `/` page is a Server Component that calls `http://api:8000/api/me` directly over the Docker internal network (not through the public proxy), forwarding the incoming request's `Cookie` header. If the call returns 200, the page issues a server-side redirect to `/candidatures` (no client-side flash, matching today's instant 302). If it returns 401, the page renders the marketing content.
- **New env var**: `INTERNAL_API_URL=http://api:8000` on the `web` service in `docker-compose.yml`, set as a plain runtime `environment:` value (not a `NEXT_PUBLIC_*` build arg) — it's read server-side only inside the Next.js Node process, never sent to the browser.
- **nginx**: add `location = /` (exact match, evaluated before the existing prefix `location /` catch-all) routing to `web:3000`. Every other path — including every subpath like `/candidatures`, `/api/*` — is unaffected; nginx's exact-match location has priority over prefix matches, so this isolates only the bare root path.

## Backend cleanup

- `dashboard/app.py`'s `landing()` route and `dashboard/templates/landing.html` are deleted — once nginx stops routing `/` to `api`, they're unreachable, same as the Jinja2 auth pages deleted in the Auth migration.
- `get_current_user_optional` (`dashboard/auth.py`) is deleted too: it exists solely to support `landing()`'s "redirect if logged in, otherwise render" behavior. Confirmed via grep it has no other caller anywhere in the codebase. Its import in `dashboard/app.py` is removed along with it.

## Content

Same structure as today's page: nav (logo + theme toggle + Se connecter/Créer un compte), hero, 4 feature cards, "Comment ça marche" (3 steps), footer CTA — rebuilt with shadcn `Card`/`Button` and the established design tokens (dark-default, teal accent, Inter) instead of the current inline-styled violet/pink gradients.

Copy changes, to fit the broadened "cadres multi-secteurs" audience (sales, tech, comm, management) rather than reading as tech-only:
- Hero title and subtitle: kept essentially as-is — already audience-neutral (CV/lettre de motivation/fiche d'entretien, scan, scoring — no tech-specific language).
- "Scan automatique des offres" feature card: drop the explicit `Greenhouse, Lever, Ashby` ATS names (signals "built for tech/startup job seekers" to a reader from another sector) — generalize to "les principales plateformes de recrutement" while keeping the audience-neutral portal names (APEC, LinkedIn, Welcome to the Jungle).
- Remaining two feature cards ("Scoring des offres", "Suivi des statuts et relances"), the "Comment ça marche" steps, and the footer CTA: unchanged, already sector-neutral.
- The already-built `ThemeToggle` component (from Frontend Foundations) moves into the page's nav bar, next to "Se connecter"/"Créer un compte".

## Out of scope

- Any protected page (`/candidatures`, `/stats`, `/profile`, `/settings`) — not touched by *this* spec, still Jinja2, still redirects unauthenticated visitors to `/login` exactly as today. All four are on the roadmap and get migrated next, one page at a time, each with its own spec/plan/implementation pass — this section only scopes what this particular spec changes, not what the project will eventually cover.
- Any pricing/plans content — the product has no billing yet.
- SEO tooling beyond what SSR already provides (no sitemap.xml, robots.txt, or structured-data work in this pass).
