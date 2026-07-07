# Per-user Hugging Face access token — Design Spec

Date: 2026-07-07
Status: approved

## Goal

Replace the single shared `HF_TOKEN` env var in `dashboard/llm.py` with a per-user token, entered once in `/settings`, encrypted at rest, and required before any AI-assisted candidature prep runs. Multi-tenancy (Supabase auth, `user_id` scoping, `user_settings` table) already exists — this closes the last shared-secret gap left from the single-user era.

Decisions (confirmed with Arnaud):
- **No shared fallback.** If a user hasn't set their own token, `/offers/{id}/prepare` is blocked with a clear message pointing to `/settings` — no silent use of a server-wide token.
- **Encrypted at rest**, via `cryptography.fernet.Fernet` (already an unused dependency in `requirements.txt`), keyed by a new `SECRET_KEY` env var.
- Gemini fallback (`GEMINI_API_KEY`, shared, used only when the user's own HF call fails) is unrelated to this feature and stays as-is.

## Architecture

**Migration** `alembic/versions/0004_hf_token.py`: add `user_settings.hf_token_encrypted BYTEA NULL`.

**`dashboard/user_data.py`** — three new functions, same lazy-init pattern as `_get_jwks_client` in `auth.py`:
- `get_hf_token(conn, user_id) -> str | None` — SELECT + decrypt; `None` if column is NULL or no row exists.
- `save_hf_token(conn, user_id, token: str) -> None` — encrypt + `INSERT ... ON CONFLICT (user_id) DO UPDATE` (same upsert shape as `save_settings`).
- `delete_hf_token(conn, user_id) -> None` — set column to NULL.
- A module-level `_fernet()` helper builds the `Fernet` instance from `os.environ["SECRET_KEY"]` once, raising immediately (`KeyError`/`ValueError`, uncaught — deployment misconfiguration, not a request-time condition) if the key is missing or malformed.

**`dashboard/llm.py`** — `hf_token: str` becomes a required parameter on `call_llm`, `analyze_offer`, `rewrite_cv_summary`, `write_cover_letter`, and `generate_prep_questions`, threaded down to `_call_hf`, which uses it instead of `os.environ["HF_TOKEN"]`. The env var is no longer read anywhere.

**`dashboard/app.py`** (`POST /offers/{offer_id}/prepare`): fetch `hf_token = user_data.get_hf_token(conn, user_id)` before the guard on description length. If `None`, return the existing `_error(...)` HTMX partial: "Ajoute ton token Hugging Face dans les paramètres avant de préparer une candidature." with a link to `/settings`. No LLM function is called in this branch.

**Settings UI** (`dashboard/templates/settings.html` + a new partial):
- New section "Clé API Hugging Face". Shows only a boolean state — "Configuré ✓" or "Non configuré" — the token itself is never redisplayed, not even masked, once saved.
- `POST /settings/hf-token` (form field `hf_token`, plain password-type input) — saves/replaces it, returns the updated partial.
- `DELETE /settings/hf-token` — clears it, returns the updated partial.

## Error handling

- Missing/invalid `SECRET_KEY` at encrypt/decrypt time: uncaught exception → 500. This is a startup/deployment boundary condition, not something to degrade gracefully around.
- Missing per-user HF token at prepare time: handled explicitly, user-facing message (see above) — this is an expected, recoverable state, not an error path.
- Empty string submitted to `POST /settings/hf-token`: treated as "no token" (same as `delete`), not saved as an empty encrypted blob.

## Testing

- `tests/test_llm.py`: existing tests updated to pass a `hf_token` argument through `call_llm` and the phase functions (no behavior change to assert, just signature).
- `tests/test_user_data.py`: round-trip test — `save_hf_token` then `get_hf_token` returns the same plaintext; `get_hf_token` returns `None` when nothing saved; `SECRET_KEY` set via `monkeypatch.setenv` in the test (mirrors the existing `SUPABASE_JWT_SECRET` pattern in `test_dashboard_app.py`).
- `tests/test_dashboard_app.py`:
  - Existing `/prepare` tests (`_patch_phases` helper) gain a `monkeypatch.setattr(user_data, "get_hf_token", lambda conn, user_id: "test-hf-token")` so they keep testing phase orchestration, not token plumbing.
  - New test: `/prepare` with no token configured returns the blocking message and writes nothing (no DB update, no LLM call attempted — assert via a phase-function monkeypatch that raises if called).

## Config / docs

- `.env.example`: remove `HF_TOKEN=hf_...` (no longer read), add `SECRET_KEY=` with a comment showing how to generate one (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
- `README.md`: document the new Settings section and the `SECRET_KEY` env var in the Configuration table.
- `CHANGELOG.md`: entries under `### Added` (settings UI, migration) and `### Changed` (llm.py signature, removal of shared `HF_TOKEN`).

## Out of scope (for this pass)

- Encryption key rotation / re-encrypting existing tokens on `SECRET_KEY` change.
- Validating the token against the HF API before saving (e.g. a test call) — bad tokens simply fail at prepare time with the existing `LLMError` surface.
- Rate limiting or per-user quota tracking on HF usage — each user now uses their own token/quota, so this is naturally out of scope.
