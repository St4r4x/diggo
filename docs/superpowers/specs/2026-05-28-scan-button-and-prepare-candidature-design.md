# Design — Scan button & Préparer candidature

**Date:** 2026-05-28
**Scope:** Two dashboard features

---

## 1. Feature B — Bouton "Scanner maintenant"

### Goal

Allow the user to trigger the full import pipeline (`scan → dedup → pre_filter → import_offers`) from the dashboard UI, with live feedback.

### State model

Two new fields on `app.state`, initialized in the `lifespan` handler:

```python
app.state.scan_status = "idle"   # "idle" | "running" | "done" | "error"
app.state.scan_result = {"inserted": 0, "skipped": 0, "error": ""}
```

### New endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/scan/start` | Start a scan if idle; no-op if already running |
| `GET` | `/scan/status` | Return the scan status partial |

### Data flow

**`POST /scan/start`:**
1. If `scan_status == "running"` → return the "running" partial immediately (no second Task).
2. Otherwise: set `scan_status = "running"`, create an asyncio Task that:
   - Calls `load_settings()` then `_run_pipeline(settings)` then `import_offers(offers, DB_PATH)`
   - On success: set `scan_status = "done"`, store `{"inserted": n, "skipped": m}` in `scan_result`
   - On any exception: set `scan_status = "error"`, store `{"error": str(e)}` in `scan_result`
3. Return the "running" partial immediately (HTMX polling activates).

**`GET /scan/status`** — returns a different fragment per state:

| State | Fragment content |
|-------|-----------------|
| `idle` | Button "Scanner" (normal), no poll |
| `running` | Spinner + "Scan en cours…", `hx-trigger="every 2s"` polls this same endpoint |
| `done` | Green badge "X nouvelles offres", button re-enabled, `hx-swap-oob` refreshes `#offer-list` |
| `error` | Red badge with error message, button re-enabled |

Clicking the button when `done` or `error` resets to `idle` and starts a new scan.

### UI placement

In `dashboard/templates/index.html`, inside the filter bar div, after the grade select. The scan button and status badge share a single `<div id="scan-status">` that HTMX swaps in place.

### New files

- `dashboard/templates/partials/scan_status.html` — renders the scan button/badge based on `status` and `result` template variables

### Error handling

- Pipeline exceptions are caught inside the asyncio Task; they never crash the server.
- `scan_result["error"]` stores the first line of the exception message (no traceback exposed to UI).

---

## 2. Feature D — Commande "Préparer candidature"

### Goal

Show the `claude --mode` command to copy inside the offer detail panel, so the user can launch `prepare-candidature` from their terminal without memorizing the syntax.

### UI placement

In `dashboard/templates/partials/offer_detail.html`, at the bottom of the detail panel. Shown for all offers (not filtered by status).

### Component

```html
<div class="mt-4 bg-slate-900 rounded p-3 flex items-center gap-3">
  <code class="text-sm text-violet-300 flex-1">
    claude --mode modes/prepare-candidature.md --offer-id {{ offer.id }}
  </code>
  <button onclick="copyPrepCommand({{ offer.id }})" id="copy-btn-{{ offer.id }}"
          class="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1 rounded text-slate-200">
    Copier
  </button>
</div>
<script>
function copyPrepCommand(id) {
  navigator.clipboard.writeText(
    `claude --mode modes/prepare-candidature.md --offer-id ${id}`
  );
  const btn = document.getElementById(`copy-btn-${id}`);
  btn.textContent = 'Copié ✓';
  setTimeout(() => btn.textContent = 'Copier', 2000);
}
</script>
```

No server-side changes needed.

---

## 3. Testing

### Feature B — new tests in `tests/test_dashboard_app.py`

1. `POST /scan/start` when idle → 200, `app.state.scan_status` becomes `"running"`
2. `POST /scan/start` when already running → 200, no second Task created
3. `GET /scan/status` for each of the 4 states returns correct HTML fragment
4. Full scan flow with `_run_pipeline` and `import_offers` monkeypatched → status ends at `"done"` with correct counts

### Feature D — new test in `tests/test_dashboard_app.py`

1. `GET /offers/<id>` → response HTML contains `prepare-candidature.md --offer-id <id>`

---

## 4. Out of scope

- Scheduler / cron (not requested)
- Renaming the "Candidatures" nav link (already done in commit 2026-05-28)
- Real-time log streaming from the pipeline
- Any changes to `scripts/import_offers.py` internals
