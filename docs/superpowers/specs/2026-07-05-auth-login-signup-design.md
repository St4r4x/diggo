# Auth — Login / Signup / Reset Password Design

**Date:** 2026-07-05

## Goal

Allow any user to create an account and sign in to career-ops-fr. Each user sees only their own data. Supports email+password signup with email verification, login, and password reset.

## Context

The backend already validates Supabase JWTs and scopes all DB queries to `user_id`. What's missing is the front-door: pages for signup/login/reset, token storage in a cookie, and wiring the cookie into `auth.py`.

---

## Architecture

### Stack additions

- **Supabase CLI local** — replaces the standalone `postgres:16` service. Provides PostgreSQL (port 54322), Auth API (54321), Studio (54323), and Inbucket email catcher (54324).
- **`supabase-js` v2** via CDN — loaded only on auth pages (`/login`, `/signup`, `/auth/reset-password`). Handles `signInWithPassword`, `signUp`, `resetPasswordForEmail`, and silent token refresh.
- **Two httpOnly cookies** — `session` (access_token, 1h) and `refresh` (refresh_token, 7d).

### Auth flow

```
Browser                    FastAPI                 Supabase Auth (local :54321)
  |                           |                         |
  |-- GET /login ------------>|                         |
  |<-- HTML login page -------|                         |
  |                           |                         |
  |-- supabase.auth.signIn() ----------------------->  |
  |<-- { access_token, refresh_token } --------------|  |
  |                           |                         |
  |-- POST /auth/session ---->|                         |
  |   { access_token,         |-- verify JWT (PyJWT) -> |
  |     refresh_token }       |<-- valid ---------------|
  |                           |                         |
  |<-- Set-Cookie: session,   |                         |
  |    Set-Cookie: refresh    |                         |
  |                           |                         |
  |-- GET / (cookie auto) --->|                         |
  |   reads cookie,           |                         |
  |   extracts user_id        |                         |
  |<-- HTML dashboard --------|                         |
```

**Token refresh:** `supabase-js` refreshes automatically when the access_token expires. On refresh it calls `POST /auth/session` again to update the `session` cookie.

**Redirect on 401:** `auth.py` raises `HTTPException(302, Location="/login")` instead of returning JSON 401.

---

## Routes

### Public (no auth required)

| Route | Method | Description |
|-------|--------|-------------|
| `/login` | GET | Login page — email + password form, link to /signup, link to reset |
| `/signup` | GET | Signup page — email + password + confirm password |
| `/auth/confirm` | GET | Static "check your email" page shown after signup |
| `/auth/reset-password` | GET | New password form — opened via Supabase email link |
| `/auth/session` | POST | Receives `{access_token, refresh_token}`, verifies JWT, sets cookies |
| `/auth/session` | DELETE | Clears both cookies → logout |

### Protected (unchanged)

All existing routes (`/`, `/stats`, `/profile`, `/offers/*`, `/scan/*`) remain protected via `Depends(get_current_user)`.

---

## Cookie spec

```
session=<access_token>;  HttpOnly; SameSite=Lax; Path=/; Max-Age=3600
refresh=<refresh_token>; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800
```

- `HttpOnly` — not accessible via JS (XSS-safe)
- `SameSite=Lax` — sent on top-level navigations, not on cross-site subrequests
- No `Secure` flag in local dev; added in prod (Railway sets HTTPS)

---

## `dashboard/auth.py` changes

```python
def get_current_user(request: Request) -> CurrentUser:
    if os.getenv("DEV_AUTO_LOGIN") == "true":
        return _DEV_USER
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    # PyJWT decode (unchanged)
    secret = os.getenv("SUPABASE_JWT_SECRET", "")
    if not secret:
        raise HTTPException(status_code=500, detail="SUPABASE_JWT_SECRET is not configured")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return {"sub": payload["sub"], "email": payload.get("email", "")}
```

---

## Templates

Four new Jinja2 templates, same Tailwind dark theme as existing pages:

- `dashboard/templates/auth/login.html` — email + password form, error display, links to /signup and reset
- `dashboard/templates/auth/signup.html` — email + password + confirm, error display, link to /login
- `dashboard/templates/auth/confirm.html` — static "check your email" message
- `dashboard/templates/auth/reset-password.html` — new password form (opened via Supabase email link containing a token in the URL fragment)

`supabase-js` v2 loaded via CDN only on these pages. ~50 lines of vanilla JS per page calling `supabase.auth.*`.

---

## `base.html` changes

- Add user email display in nav (top right)
- Add "Déconnexion" button → calls `DELETE /auth/session` + `supabase.auth.signOut()` then redirects to `/login`

---

## Supabase CLI — local setup

Replace `postgres:16` standalone with Supabase CLI:

```bash
supabase init        # creates supabase/ config dir
supabase start       # starts all services
```

Services started:
- PostgreSQL: `postgresql://postgres:postgres@localhost:54322/postgres`
- Auth API: `http://localhost:54321`
- Studio: `http://localhost:54323`
- Inbucket (email catcher): `http://localhost:54324`

`docker-compose.yml` change:
- Remove `postgres:` service and `postgres_data` volume
- Remove `depends_on: postgres` from dashboard and pipeline
- `DATABASE_URL` in `.env` → `postgresql://postgres:postgres@localhost:54322/postgres`
- `SUPABASE_URL` → `http://localhost:54321`
- `SUPABASE_JWT_SECRET` → value from `supabase status` output

Alembic runs unchanged against the new DATABASE_URL.

---

## Email verification flow

1. User submits signup form
2. `supabase.auth.signUp()` called in browser
3. Supabase sends confirmation email → Inbucket catches it locally (`http://localhost:54324`)
4. User clicks link → Supabase confirms account
5. User redirected to `/login`

In prod (Supabase hosted): real SMTP, real email delivery. No code change needed.

---

## Password reset flow

1. User clicks "Mot de passe oublié" on `/login`
2. Email input shown → `supabase.auth.resetPasswordForEmail(email, { redirectTo: '/auth/reset-password' })`
3. Supabase sends reset email → Inbucket locally
4. User clicks link → redirected to `/auth/reset-password` with token in URL fragment
5. JS extracts token, calls `supabase.auth.updateUser({ password: newPassword })`
6. Redirected to `/login`

---

## Environment variables

New/changed in `.env` and `.env.example`:

```bash
# Was: postgresql://career:career@localhost:5432/career
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres

# Was: http://localhost:54321 (placeholder)
SUPABASE_URL=http://localhost:54321

# Was: local-anon-key (placeholder) — real value from `supabase status`
SUPABASE_ANON_KEY=eyJ...

# Was: super-secret-jwt-token-for-local-dev-only — real value from `supabase status`
SUPABASE_JWT_SECRET=super-secret-jwt-token-with-at-least-32-characters
```

---

## What is NOT in scope

- OAuth (Google/GitHub) — add later once Supabase hosted is configured
- Email templates customization — Supabase defaults are fine for now
- Rate limiting on auth endpoints — Supabase handles this internally
- Admin user management UI
