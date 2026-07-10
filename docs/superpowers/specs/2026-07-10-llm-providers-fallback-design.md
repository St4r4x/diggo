# Diggo — Multi-provider LLM with automatic fallback — Design Spec

Date: 2026-07-10
Status: approved

## Goal

Today `dashboard/llm.py` hard-codes Hugging Face Inference Providers as the sole LLM backend (`_HF_MODEL = "openai/gpt-oss-120b:fastest"`, an `openai.OpenAI` client pointed at `router.huggingface.co`), with each user bringing their own HF token (stored encrypted in `user_settings.hf_token_encrypted`, entered via `/settings`). If Hugging Face is down or the user's token stops working, the entire candidature-prep pipeline (offer analysis, CV rewrite, cover letter, interview prep) is blocked with no alternative.

This adds four more providers — Ollama Cloud, OpenAI, Anthropic, Groq — and automatic fallback: the pipeline tries each of the user's configured providers in a user-defined order until one succeeds, so a single provider outage no longer blocks candidature prep. Stays on the existing "bring your own key" model — no centralized billing on Diggo's account.

## Context

`call_llm()` (`dashboard/llm.py:74-93`) is already the single choke point every LLM-calling function (`analyze_offer`, `rewrite_cv_summary`, `write_cover_letter`, `generate_prep_questions`) goes through, and `_call_hf()` already wraps an OpenAI-SDK-compatible call — Hugging Face's Inference Providers router, Ollama Cloud, OpenAI, and Groq are all OpenAI-compatible (differ only in `base_url` and model name), so three of the four new providers reuse the existing client shape. Anthropic has no OpenAI-compatible endpoint and needs the `anthropic` SDK.

`user_data.get_hf_token()`/`save_hf_token()`/`delete_hf_token()` (`dashboard/user_data.py:187-219`) and the single `hf_token_encrypted bytea` column on `user_settings` (added in migration `0004`) are replaced by a dedicated table so a 6th provider can be added later without another schema change to `user_settings` itself.

`get_onboarding_state()` (`dashboard/user_data.py:222-246`) currently gates completion on `hf_token_complete`; this becomes "at least one provider configured," consistent with the fallback model — the point is having *a* working LLM entry point, not a specific one.

## Data model

New table, migration `0007` (`down_revision = "0006"`):

```
user_llm_providers
  id                 serial primary key
  user_id            text not null
  provider           text not null   -- 'huggingface' | 'ollama_cloud' | 'openai' | 'anthropic' | 'groq'
  api_key_encrypted  bytea not null
  sort_order         integer not null default 0
  created_at         timestamptz not null default now()
  unique (user_id, provider)
```

`upgrade()` also backfills: for every row in `user_settings` where `hf_token_encrypted IS NOT NULL`, insert `(user_id, 'huggingface', hf_token_encrypted, 0)` into `user_llm_providers` — the Fernet ciphertext is copied as-is (same `SECRET_KEY`, no decrypt/re-encrypt needed) — then drop the `hf_token_encrypted` column from `user_settings`. `downgrade()` re-adds the column, copies the Hugging Face row's ciphertext back if present, and drops the table.

## Backend: `user_data.py`

Replace `get_hf_token`/`save_hf_token`/`delete_hf_token` with:

- `get_llm_providers(conn, user_id) -> list[dict]` — `[{"provider": str, "sort_order": int}]` ordered by `sort_order`. Never returns key material — callers that need a specific key call `get_llm_provider_key`.
- `get_llm_provider_key(conn, user_id, provider) -> str | None` — decrypts and returns one provider's key, or `None` if not configured or decryption fails (same `InvalidToken -> None` pattern as today's `get_hf_token`).
- `save_llm_provider(conn, user_id, provider, api_key) -> None` — encrypts, upserts (`ON CONFLICT (user_id, provider) DO UPDATE`); if this is the user's first provider, `sort_order` defaults to `0`, otherwise appends at `max(sort_order) + 1`.
- `delete_llm_provider(conn, user_id, provider) -> None`.
- `reorder_llm_providers(conn, user_id, order: list[str]) -> None` — sets `sort_order` to each provider's index in `order`; providers not in `order` are left unchanged.

`get_onboarding_state()`: `hf_token_complete` renamed `llm_provider_complete`, computed as `len(get_llm_providers(conn, user_id)) >= 1`; `is_complete` uses the renamed field.

## Backend: `dashboard/llm.py`

```python
_PROVIDER_DEFAULTS: dict[str, tuple[str, str]] = {  # provider -> (base_url, default_model)
    "huggingface":  ("https://router.huggingface.co/v1", "openai/gpt-oss-120b:fastest"),
    "ollama_cloud": ("https://ollama.com/v1",             "llama3.3"),
    "openai":       ("https://api.openai.com/v1",         "gpt-4.1-mini"),
    "groq":         ("https://api.groq.com/openai/v1",    "llama-3.3-70b-versatile"),
}
_ANTHROPIC_MODEL = "claude-sonnet-4-5"
```

- `_call_openai_compatible(provider, api_key, system_prompt, user_prompt, json_mode) -> str` — today's `_call_hf` generalized to take `provider`, looks up `base_url`/model from `_PROVIDER_DEFAULTS`.
- `_call_anthropic(api_key, system_prompt, user_prompt, json_mode) -> str` — new, uses the `anthropic` SDK's `Anthropic(api_key=...).messages.create(...)`; for `json_mode`, appends the same "respond with a JSON object matching this shape" instruction used today rather than a structured-output feature (keeps behavior identical across providers).
- `call_llm(providers: list[tuple[str, str]], system_prompt, user_prompt, *, json_schema=None) -> str` — `providers` is `[(provider_name, api_key), ...]` in try-order (already resolved/decrypted by the caller, so `llm.py` stays free of DB access). For each provider: dispatch to `_call_anthropic` if `provider == "anthropic"` else `_call_openai_compatible`; on success, `logger.info("llm: answered by %s", provider)` and return. On `AuthenticationError`/`PermissionDeniedError` (equivalent Anthropic exceptions included), log a warning and continue to the next provider — an invalid key for one provider must not block the others. On any other `OpenAIError`/network error/Anthropic API error, also continue to the next provider (this is the fallback path proper). If every provider in the list is exhausted without success, raise `LLMError` wrapping the last exception. If `providers` is empty, raise `LLMError("Aucun fournisseur LLM configuré.")` immediately.
- `validate_provider_key(provider: str, api_key: str) -> None` — replaces `validate_hf_token`; same one-token-of-output smoke-test call as today, dispatched to the right client per provider, raising `LLMError` with the same three-message shape (invalid token / valid-but-missing-permission where the provider distinguishes it / transient-failure) on failure.

Every LLM-calling function (`analyze_offer`, `rewrite_cv_summary`, `write_cover_letter`, `generate_prep_questions`) changes its first parameter from `hf_token: str` to `providers: list[tuple[str, str]]`, threading straight through to `call_llm`.

## Backend: `dashboard/prepare_state.py`

`_run_prepare()`: replace `user_data.get_hf_token(conn, user_id)` (and its "no token" early-exit) with:

```python
provider_names = [p["provider"] for p in user_data.get_llm_providers(conn, user_id)]
providers = [
    (name, key)
    for name in provider_names
    if (key := user_data.get_llm_provider_key(conn, user_id, name)) is not None
]
if not providers:
    _status[offer_id] = "error"
    _error[offer_id] = (
        "Ajoute au moins un fournisseur LLM dans les paramètres avant de "
        "préparer une candidature."
    )
    return
```

Every call site (`llm.analyze_offer(hf_token, ...)` etc.) becomes `llm.analyze_offer(providers, ...)`.

## Backend: `dashboard/api.py`

- `GET /api/settings` response: `hf_token_set: bool` replaced by `llm_providers: list[{"provider": str, "sort_order": int}]`.
- `PUT /api/settings/llm-providers/{provider}` (body `{"api_key": str}`) — 404 if `provider` isn't one of the five known names; empty/whitespace-only key deletes the provider (mirrors today's empty-token-clears behavior) and returns `{"llm_providers": [...]}`; otherwise `await asyncio.to_thread(llm.validate_provider_key, provider, api_key)` (kept off the event loop, matching the existing HF-token route's fix), 422 with `{"detail": {"error": "invalid_provider_key", "message": str(exc)}}` on `LLMError`, else `save_llm_provider` + `{"llm_providers": [...]}` (refreshed full list, matching the ATS-targets route's established shape).
- `DELETE /api/settings/llm-providers/{provider}` → `delete_llm_provider`, returns `{"llm_providers": [...]}`.
- `PUT /api/settings/llm-providers/reorder` (body `{"order": list[str]}`) → `reorder_llm_providers`, returns `{"llm_providers": [...]}`.
- Remove `POST`/`DELETE /api/settings/hf-token`.

## Frontend

- `frontend/lib/types.ts`: `SettingsResponse.hf_token_set: boolean` → `llm_providers: {provider: string, sort_order: number}[]`. New `LLM_PROVIDER_LABELS: Record<string, string>` constant (display names: "Hugging Face", "Ollama Cloud", "OpenAI", "Anthropic (Claude)", "Groq") in `frontend/lib/types.ts` or a small shared const file, following `status-colors.ts`'s existing pattern of colocated display-mapping constants.
- `frontend/components/settings/hf-token-section.tsx` → `llm-providers-section.tsx`: renders the 5 known providers, configured ones first (ordered by `sort_order`, with ↑/↓ buttons per row calling `PUT /api/settings/llm-providers/reorder` with the new order — no drag-and-drop library, plain buttons is enough for 5 items), each with a "Configuré ✓" badge, a masked key input + Enregistrer/Supprimer buttons (mirroring today's HF-token form exactly, just parameterized by provider); unconfigured providers appear below, dimmed, with just a key input + Enregistrer. Error message from a failed `PUT` shown inline per-row (matching the current single-token error display, now scoped to the row that failed).
- `frontend/components/settings/settings-client.tsx`: swap the `HfTokenSection` import/usage for `LlmProvidersSection`.
- `frontend/components/onboarding-banner.tsx`: no change needed — it already links to `/settings#hf-token`; that anchor id moves to wrap the new section's root element instead of the old one, keeping the existing link live. (If the section is renamed to something like `id="llm-providers"`, `onboarding-banner.tsx` needs a matching one-line update — pick the anchor id during implementation and update both together.)

No new npm dependencies.

## Testing

- `tests/test_llm.py` (new or extended): `call_llm` fallback — first provider raises a network/5xx-equivalent error, second succeeds → result comes from the second, first's failure logged; first provider raises an auth error → skipped without retry, second tried; all providers exhausted → `LLMError` raised wrapping the last exception; empty `providers` list → immediate `LLMError`. `_call_anthropic` and `_call_openai_compatible` each covered with a mocked client.
- `tests/test_user_data.py`: CRUD for `get_llm_providers`/`get_llm_provider_key`/`save_llm_provider`/`delete_llm_provider`/`reorder_llm_providers`; `get_onboarding_state`'s `llm_provider_complete` with zero/one/many providers configured.
- `tests/test_prepare_state.py`: `_run_prepare` builds the `providers` list correctly from DB rows (skipping any provider whose key fails to decrypt), and the "no providers configured" early-exit path.
- `tests/test_api_routes.py`: the three new `/api/settings/llm-providers*` routes (save/validate/422, delete, reorder), and `GET /api/settings`'s new `llm_providers` shape.
- Migration `0007`: a dedicated test (following the existing migration-test pattern if one exists, otherwise a direct `alembic upgrade`/`downgrade` round-trip against a scratch schema) verifying the Hugging Face backfill copies ciphertext correctly and the column drop/re-add round-trips.
- The user's existing Hugging Face key (already re-saved after the earlier `SECRET_KEY` mismatch) is picked up automatically by the `0007` backfill — no re-entry needed after this migration runs.

## Dependencies

Add `anthropic` to `requirements.txt`. The other four providers reuse the already-present `openai` SDK.
