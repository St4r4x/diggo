# Diggo — public landing page & rebrand — Design Spec

Date: 2026-07-07
Status: approved

## Goal

Rename career-ops-fr to **Diggo** (chosen after checking for naming collisions — no active competitor in the French job-search space uses this name) and add a public landing page at `/`, so a visitor who isn't logged in understands what the product does before signing up. Today `/` is the protected offers list; an anonymous visitor is redirected straight to `/login` with zero context.

## Naming

**Diggo** — invented word from "digger" (digging up the right opportunity). Checked against active competitors in the French job-search/candidature space (Tremplin, Rebond, Postulo, Boussole, JobRadar/Déclic all collide or are close competitors; Diggo's only web results are an unrelated Indonesian POS app, a children's reading app, and a browser extension — no conflict in this product category).

## Rename scope

**In scope for this pass:**
- Every display occurrence of "career-ops-fr" → "Diggo": `dashboard/templates/base.html` (page `<title>`, nav logo), `dashboard/templates/auth/{login,signup,confirm,reset-password}.html` (titles + header text), `README.md` (title line, description), the new landing page.
- GitHub repo rename: `St4r4x/career-ops-fr` → `St4r4x/diggo` via `gh repo rename`. GitHub auto-redirects the old URL for git/web, so this is low-risk and reversible.
- `git remote set-url origin` updated to the new URL (single update in the shared `.git/config`, applies to the main checkout and this worktree alike since remotes aren't per-worktree).
- `docker-compose.yml`: add a top-level `name: diggo` key. Docker Compose derives container names (`career-ops-fr-dashboard-1` today) from the project directory name by default; `name:` overrides that without requiring the directory itself to be renamed.

**Explicitly out of scope for this pass (technical constraint):**
- Renaming the local folder `career-ops-fr` → `diggo`. This session is running *inside* a git worktree nested under that folder (`career-ops-fr/.claude/worktrees/charming-dhawan-215c52`). A worktree's link back to the main repo's `.git` directory is stored as an absolute path on both sides; renaming an ancestor directory of either side while the worktree is in active use breaks that link and would corrupt the current session's own working directory mid-flight. The plan documents the exact commands for Arnaud to run this himself later, from a shell with no active Claude session/worktree pointing into this tree.

## Routing change

`/` becomes a smart entry point instead of an always-protected route:
- Not authenticated → renders the new public landing page, HTTP 200.
- Authenticated → HTTP 302 redirect to `/candidatures` (the offers list, moved from `/` to this new path).

The existing `index()` handler (offers list, currently `@app.get("/")`) is renamed to serve `/candidatures` instead, unchanged otherwise. `base.html`'s nav "Candidatures" link and its active-state check move from `/` to `/candidatures`. `login.html`'s post-login redirect (`window.location.href = '/'`) is left as-is — it lands on the smart `/` route, which immediately forwards an authenticated user to `/candidatures`.

**Auth check without forcing a redirect:** the existing `get_current_user` dependency raises `HTTPException(302, location=/login)` when there's no valid session — exactly the *opposite* of what `/` needs (it must render 200 for anonymous visitors, not redirect). A new `get_current_user_optional(request) -> CurrentUser | None` in `dashboard/auth.py` wraps the same token-decode path and returns `None` instead of raising. It's called directly inside the `/` handler (not via `Depends`), so it doesn't interact with the `Depends(get_current_user)` override machinery the existing test suite relies on for other routes — the new landing-page tests set up real cookies/no-cookies directly, matching the existing pattern already used in `TestAuthRoutes` and `TestRoot::test_requires_auth`.

## Landing page content

Reuses the existing dark theme (`#0f0a1e` background, indigo→pink gradient accents) already established on the login/signup pages — no new design system.

1. **Hero**: headline leading with AI-prepared candidatures ("CV, lettre de motivation et fiche d'entretien générés sur mesure pour chaque offre"), one-line subheadline, primary CTA "Créer un compte" (→ `/signup`) and secondary link "Se connecter" (→ `/login`).
2. **Feature cards** (4): (1) génération IA du dossier de candidature — lead feature, (2) scan automatique des portails (APEC, LinkedIn, WTTJ, ATS Greenhouse/Lever/Ashby), (3) scoring des offres, (4) suivi des statuts + relances.
3. **"Comment ça marche"**: 3 steps — connecte ton profil → scan automatique → prépare ta candidature en un clic.
4. **Footer CTA**: repeat of the primary sign-up button.

New template `dashboard/templates/landing.html`, extending `base.html`'s general HTML shell but NOT its authenticated nav (the nav currently always renders the Paramètres/Profil/Stats links and a logout button regardless of auth state — wrong for an anonymous landing page). The landing page gets its own minimal header (logo + "Se connecter"/"Créer un compte" links), matching the pattern already used standalone in `login.html`/`signup.html` (which also don't extend `base.html`'s nav).

## Testing

- `TestRoot`'s three existing tests (`test_returns_200`, `test_contains_app_title`, `test_requires_auth`) currently assert on the *offers list* being served at `/` — their intent moves to `/candidatures` (renamed accordingly, assertions unchanged otherwise since `/candidatures` behaves exactly like `/` did before).
- New tests for the smart `/` route: anonymous → 200, landing page content present; authenticated (real cookie, not the `client` fixture's blanket override, matching `test_requires_auth`'s existing style) → 302 to `/candidatures`.
- `base.html` nav link and active-state tests (if any reference `href="/"` for Candidatures) updated to `/candidatures`.
- `README.md`/branding text changes are documentation-only, no test coverage needed.

## Out of scope

- Local folder rename (see above — documented as a manual follow-up, not automated).
- A dedicated marketing domain/DNS setup — out of scope, this is about the app's own `/` route.
- Any pricing/plans content — the product has no billing yet, the landing page doesn't imply one.
