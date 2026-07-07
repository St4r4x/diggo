# Onboarding Gate — Design

**Date:** 2026-07-07

## Goal

Before public launch, a new user who signs up and confirms their email lands on an empty `/candidatures` dashboard with no guidance. Nothing tells them they need to fill in their profile, set search keywords, and add a Hugging Face token before the app does anything useful — the HF token requirement in particular is only discovered later, as an error message when they try to prepare a candidature (`app.py:442-447`).

This design gates access to the core app behind a completeness check, and redirects incomplete accounts to the existing `/profile` and `/settings` pages — with a progress banner telling them exactly what's missing.

## Context

Existing pieces already in place, reused as-is:
- `dashboard/auth.py` — `get_current_user` dependency, cookie-based Supabase JWT auth
- `dashboard/user_data.py` — `get_profile`, `get_cv`, `get_settings`, `get_hf_token`
- `dashboard/templates/profile.html`, `settings.html` — existing forms for profile, search keywords, HF token
- `dashboard/templates/partials/settings_hf_token.html` — HF token form, currently a single instructional paragraph

No new database columns or migrations. Completeness is computed from existing data on every request — an account that becomes "incomplete" again later (e.g. user deletes their only experience) is caught automatically, with no state to go stale.

---

## Onboarding completeness

New function in `user_data.py`:

```python
def get_onboarding_state(conn: psycopg2.extensions.connection, user_id: str) -> dict[str, Any]:
    """Return completeness flags for profile, search settings, and HF token."""
```

Returns:

```python
{
    "profile_complete": bool,   # contact.name/email set, summary non-empty, >=1 experience, >=1 skill
    "search_complete": bool,    # settings["keywords"] non-empty
    "hf_token_complete": bool,  # get_hf_token(conn, user_id) is not None
    "is_complete": bool,        # all three above
}
```

`profile_complete` checks (all required, in the "fr" CV — English stays optional):
- `get_profile(conn, user_id)`: `name` and `email` non-empty
- `get_cv(conn, user_id, lang="fr")`: `summary` non-empty, `len(experience) >= 1`, `len(skills) >= 1`

This reuses `get_profile`/`get_cv` as-is — no new queries beyond what `/profile` already loads.

---

## Route gate

New dependency in `dashboard/auth.py`:

```python
def require_onboarding_complete(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Redirect to the first incomplete onboarding step. Raises 302 if incomplete."""
```

Checks `get_onboarding_state` and raises `HTTPException(302, headers={"Location": "/profile" or "/settings"})`:
- `profile_complete` false → `/profile`
- else `search_complete` false → `/settings`
- else `hf_token_complete` false → `/settings`

Applied to: `index()` (`/candidatures`), `offer_list()`, `offer_detail()`, `offer_edit_form()`, `stats_page()`, `scan_start()`, `offer_prepare` (the prepare-candidature route). Replaces their existing `Depends(get_current_user)`.

`/profile` and `/settings` (and their sub-routes: `profile_save_*`, `settings_save_search`, `settings_save_hf_token`, `settings_ats_*`) keep plain `Depends(get_current_user)` — never gated, since they're where the user resolves the gate.

This mirrors the existing 302-on-401 pattern already used for unauthenticated requests, so `htmx` requests hitting a gated endpoint redirect the browser the same way an expired session does today.

---

## Progress banner

New partial `dashboard/templates/partials/onboarding_banner.html`, included at the top of `profile.html` and `settings.html`:

```
🚀 Pour démarrer : ✓ Profil · ✗ Mots-clés de recherche · ✗ Token Hugging Face
```

- Rendered only when `not onboarding.is_complete`
- Each incomplete item links to its page (`/settings#search`, `/settings#hf-token`) with an anchor scroll
- `profile_page()` and `settings_page()` pass `onboarding=get_onboarding_state(conn, user_id)` into their template context
- Once complete, the banner simply stops rendering — no dismissal state to persist

---

## Post-confirmation redirect

`auth_confirm_page` and the login success path (`login.html`'s JS redirect after `/auth/session`) currently send the user to `/` (which redirects to `/candidatures`). Change the login redirect target to `/profile` — `require_onboarding_complete` would bounce them there anyway on their first gated request, but landing there directly skips a redundant redirect and puts them exactly where they need to be.

No change needed to `auth_confirm_page` itself (it's just the "check your email" static page); the redirect-after-login change is a one-line edit in `login.html`.

---

## Hugging Face token creation walkthrough

Two independent improvements to `partials/settings_hf_token.html`, both scoped to that file plus one new function in `llm.py`.

### Numbered steps

Replace the current single paragraph with:

```
1. Ouvre huggingface.co/settings/tokens (lien, nouvel onglet)
2. Clique sur "New token"
3. Active la permission "Inference Providers" (obligatoire — sans elle le token sera refusé)
4. Copie le token (commence par hf_) et colle-le ci-dessous
```

### Server-side token validation on save

New function in `llm.py`:

```python
def validate_hf_token(hf_token: str) -> None:
    """Raise LLMError with a specific, actionable message if the token doesn't work."""
```

Makes a minimal call through the same `OpenAI` client already used by `_call_hf` (1-token max completion, cheapest possible check — no new HTTP client or dependency). Maps failures to specific messages:
- 401 → "Token invalide — vérifie que le copier-coller est complet."
- 403 → "Token valide mais sans la permission Inference Providers — active-la dans les paramètres du token sur Hugging Face."
- other `OpenAIError` → "Impossible de vérifier le token pour le moment, réessaie."

`settings_save_hf_token` calls `validate_hf_token` before `user_data.save_hf_token`. On failure, the token is **not** saved, and `settings_hf_token.html` re-renders with the specific error message inline (same pattern as the existing auth error display in `login.html`). On success, saves as today.

Cost: one extra Hugging Face call per save attempt — negligible (single-token completion).

---

## What is NOT in scope

- No new database columns/migrations — onboarding state is always computed live
- No dismissable/skippable banner — it disappears only when actually complete
- No English CV requirement for onboarding completeness (optional, same as today)
- No wizard/dedicated `/onboarding` route — reuses `/profile` and `/settings` as-is
- No retroactive onboarding for existing accounts — the gate only blocks incomplete accounts going forward; any account with a filled profile, keywords, and token (all existing accounts today) is never redirected
