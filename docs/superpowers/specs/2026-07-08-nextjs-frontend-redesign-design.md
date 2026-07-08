# Diggo — Next.js frontend migration & UX/UI redesign — Design Spec

Date: 2026-07-08
Status: approved

## Goal

Diggo is repositioning from a personal tool into a public service for qualified job seekers across sectors (sales, tech, comms, management — "cadres"), not just AI/ML profiles. The current UI — Tailwind loaded via CDN, dark purple/pink gradient theme, inline styles scattered across Jinja2 templates — reads as generic and dated, and isn't built for a broad public audience. This redesign gives Diggo a distinctive, professional, genuinely dynamic UI, and moves the frontend off server-rendered HTML onto a proper JS frontend to support that.

## Context

Current stack: FastAPI + Jinja2 templates + HTMX for interactivity, Tailwind via `cdn.tailwindcss.com` (explicitly discouraged in production by Tailwind itself — no purge, runtime compile, console warning). All business logic (scraping, scoring, PDF generation, DB access via `db.py`/`user_data.py`) lives in the FastAPI app and is unaffected by this redesign — only the presentation layer changes.

## Audience & tone

Public-facing service for qualified job seekers across sectors, not a niche dev tool. Visual tone: modern startup / SaaS product (Notion, Linear), not corporate-cold and not dev-tool-niche. Dark theme by default (matches the target tone and keeps continuity with Diggo's current identity), light theme available via a persisted toggle — not tied to `prefers-color-scheme`, since the default must be consistent for every first-time visitor.

## Architecture

- **FastAPI becomes a JSON API.** Routes in `dashboard/app.py` that currently render HTML (including HTMX partials) return JSON instead. Business logic (scoring, scraping, DB access, PDF generation) is untouched — only the response format at the route layer changes.
- **New Next.js service** owns the entire frontend: landing, auth (login/signup/confirm/reset-password), candidatures (list + detail panel), stats, profile (CV editor), settings. Consumes the FastAPI JSON API via `fetch`.
- **Single public origin via a new reverse proxy**: today `docker-compose.yml` exposes the `dashboard` service directly on `127.0.0.1:8000`, no proxy in front of it. This migration adds one (nginx or equivalent) so `/api/*` routes to FastAPI and everything else to Next.js under one origin. This avoids CORS entirely and keeps the existing Supabase auth mechanism (httpOnly JWT cookies, JWKS/ES256 validation) working unchanged — same-origin cookies, no cross-site auth plumbing needed.
- **Docker Compose** gets three services instead of one: `api` (the existing FastAPI app, minus Jinja2/HTMX-specific code), `web` (new Next.js app), and the new reverse proxy in front of both.
- PDF generation (WeasyPrint + Jinja2, for CV/cover-letter/prep-sheet documents) stays entirely inside FastAPI, untouched by this migration — those are print documents, not web UI.

## Design system

- **Palette**: dark by default — near-black backgrounds (`#0c0e14` page, `#151820` surfaces), near-white text (`#f7f8f9`), subtle borders (`#262a35`). Light theme uses inverted neutrals with the same accent, adjusted for contrast.
- **Accent**: single accent color, teal (`#2dd4bf` dark / `#0d9488` light on white for contrast). Replaces the current indigo/pink gradient system.
- **Grade badges (A–F)**: derived from a teal → amber → gray scale instead of the current purple/pink gradient.
- **Typography**: Inter, loaded via `next/font` (self-hosted automatically by Next.js — no external font request, no layout shift), falling back to `ui-sans-serif, system-ui`.
- **Components**: shadcn/ui as the base component layer (Button, Card, Dialog, Dropdown, Tabs, Input, Toast, etc. — built on Radix primitives). Every component is copied into the repo and customized with Diggo's tokens (color, radius, shadow) rather than left as shadcn defaults — the goal is a distinctive "bento" look (well-delimited cards, generous rounded corners), in the vein of Notion/Linear, not an out-of-the-box component library look.
- **Micro-interactions**: hover/transition states on offer cards, the detail panel, and status changes are a deliberate part of the redesign — this is the concrete payoff of moving off static server-rendered HTML onto React (local state, animated transitions).

## Scope

**In scope** — every page of the current dashboard, rebuilt as Next.js pages/components against the new JSON API:
- Landing (public marketing page)
- Auth: login, signup, confirm, reset-password
- Candidatures: offer list + filters + detail panel (status, notes, prepare-candidature/prepare-entretien actions)
- Stats: pipeline funnel, response rate, daily report widget
- Profile: contact info, profile text, CV editor (FR/EN tabs)
- Settings: search keywords/salary/target companies, ATS targets CRUD, Hugging Face token

**Out of scope**:
- PDF templates (`templates/cv-fr`, `templates/cv-en`, `templates/cover-letter-fr`, `templates/prep-sheet-fr`) — stay as WeasyPrint-rendered Jinja2/CSS documents in FastAPI, unrelated to the web UI redesign.
- Any pricing/billing UI — the product has no billing yet.
- Backend business logic changes (scoring algorithm, scraping strategies, DB schema) — this spec is presentation-layer only, aside from the HTML→JSON response format change needed to serve a JS frontend.

## Non-functional requirements

- **Responsive**: genuinely mobile-first, not "usable but desktop-only" — Tailwind breakpoints and shadcn/ui's responsive-ready primitives make this the default rather than an afterthought.
- **Accessibility**: WCAG AA baseline — color contrast, full keyboard navigation, visible focus states. Largely covered by Radix primitives underlying shadcn/ui (dialogs/dropdowns/menus already handle focus trapping and ARIA roles correctly).
- **SEO**: the landing page is server-rendered (Next.js SSR/SSG) so it's indexable — it's the public-facing entry point for a service that now needs to be discoverable, unlike the previously auth-gated app.
- **Auth**: the existing Supabase JWT/httpOnly-cookie mechanism is unchanged in principle; only the consumer moves from Jinja2-rendered pages to Next.js pages making authenticated `fetch` calls against `/api/*`.

## Out of scope (explicit exclusions)

- Renaming or restructuring the repo beyond what's needed for the two-service Docker layout.
- A dedicated marketing/SEO content strategy beyond making the landing page server-rendered and indexable.
- Migrating the scraping/scoring pipeline scripts (`scripts/*.py`) — unrelated to the frontend.
