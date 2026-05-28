# Scan Button & Préparer Candidature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Scanner maintenant" button to the dashboard that triggers the full import pipeline in the background with live HTMX feedback, and add a test for the already-implemented "Préparer candidature" copy button.

**Architecture:** Two new FastAPI endpoints (`POST /scan/start`, `GET /scan/status`) manage an asyncio Task and expose state via `app.state`. HTMX polls `/scan/status` every 2s while running, then swaps `#offer-list` out-of-band on completion. Feature D (copy button) is already implemented in `offer_detail.html` — only the test is missing.

**Tech Stack:** FastAPI, asyncio, HTMX 1.9, Jinja2, pytest + TestClient

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `dashboard/app.py` | Modify | Add `POST /scan/start`, `GET /scan/status`, init scan state in lifespan |
| `dashboard/templates/partials/scan_status.html` | Create | Renders scan button/badge based on `status` and `result` |
| `dashboard/templates/index.html` | Modify | Add `<div id="scan-status">` in filter bar |
| `tests/test_dashboard_app.py` | Modify | Add `TestScan` class (4 tests) + test for prepare-candidature button |

---

## Task 1: Add scan state to app lifespan

**Files:**
- Modify: `dashboard/app.py:39-43`

- [ ] **Step 1: Update the lifespan handler**

Open `dashboard/app.py`. The current lifespan is:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = open_db(DB_PATH)
    yield
    app.state.db.conn.close()
```

Replace it with:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = open_db(DB_PATH)
    app.state.scan_status = "idle"
    app.state.scan_result: dict = {"inserted": 0, "skipped": 0, "error": ""}
    yield
    app.state.db.conn.close()
```

- [ ] **Step 2: Verify the app still starts**

```bash
cd /home/missia03/Projects/career-ops-fr
source .venv/bin/activate
python -c "import sys; sys.path.insert(0, 'dashboard'); import app; print('ok')"
```

Expected output: `ok`

---

## Task 2: Create the scan_status partial template

**Files:**
- Create: `dashboard/templates/partials/scan_status.html`

- [ ] **Step 1: Create the partial**

Create `dashboard/templates/partials/scan_status.html` with this content:

```html
{% if status == "running" %}
<div id="scan-status"
     hx-get="/scan/status"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
  <button disabled
          class="text-sm px-3 py-1 rounded bg-slate-600 text-slate-400 cursor-not-allowed flex items-center gap-2">
    <span class="inline-block w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></span>
    Scan en cours…
  </button>
</div>

{% elif status == "done" %}
<div id="scan-status"
     hx-get="/offers"
     hx-trigger="load"
     hx-target="#offer-list"
     hx-swap="innerHTML">
  <button
    hx-post="/scan/start"
    hx-target="#scan-status"
    hx-swap="outerHTML"
    class="text-sm px-3 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-white">
    ✓ {{ result.inserted }} nouvelle{% if result.inserted != 1 %}s{% endif %} — Scanner
  </button>
</div>

{% elif status == "error" %}
<div id="scan-status">
  <button
    hx-post="/scan/start"
    hx-target="#scan-status"
    hx-swap="outerHTML"
    class="text-sm px-3 py-1 rounded bg-red-700 hover:bg-red-600 text-white"
    title="{{ result.error }}">
    ✗ Erreur — Réessayer
  </button>
</div>

{% else %}
<div id="scan-status">
  <button
    hx-post="/scan/start"
    hx-target="#scan-status"
    hx-swap="outerHTML"
    class="text-sm px-3 py-1 rounded bg-violet-700 hover:bg-violet-600 text-white">
    Scanner
  </button>
</div>
{% endif %}
```

- [ ] **Step 2: Verify the file exists**

```bash
ls /home/missia03/Projects/career-ops-fr/dashboard/templates/partials/scan_status.html
```

Expected: path printed with no error.

---

## Task 3: Add scan endpoints to app.py

**Files:**
- Modify: `dashboard/app.py`

- [ ] **Step 1: Add imports at top of app.py**

At the top of `dashboard/app.py`, the existing imports include `from contextlib import asynccontextmanager`. Add `asyncio` to the stdlib imports block:

```python
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
```

- [ ] **Step 2: Add the two scan endpoints**

At the bottom of `dashboard/app.py` (after the last `@app.post` route), add:

```python
async def _run_scan_task(app_state) -> None:
    from scripts.import_offers import _run_pipeline, import_offers
    from scripts.pre_filter import load_settings

    try:
        settings = load_settings()
        offers = await _run_pipeline(settings)
        inserted, skipped = import_offers(offers, DB_PATH)
        app_state.scan_result = {"inserted": inserted, "skipped": skipped, "error": ""}
        app_state.scan_status = "done"
    except Exception as exc:
        app_state.scan_result = {"inserted": 0, "skipped": 0, "error": str(exc).splitlines()[0]}
        app_state.scan_status = "error"


@app.post("/scan/start", response_class=HTMLResponse)
async def scan_start(request: Request):
    if request.app.state.scan_status == "running":
        return templates.TemplateResponse(
            request,
            "partials/scan_status.html",
            {"status": "running", "result": request.app.state.scan_result},
        )
    request.app.state.scan_status = "running"
    request.app.state.scan_result = {"inserted": 0, "skipped": 0, "error": ""}
    asyncio.create_task(_run_scan_task(request.app.state))
    return templates.TemplateResponse(
        request,
        "partials/scan_status.html",
        {"status": "running", "result": request.app.state.scan_result},
    )


@app.get("/scan/status", response_class=HTMLResponse)
async def scan_status(request: Request):
    return templates.TemplateResponse(
        request,
        "partials/scan_status.html",
        {
            "status": request.app.state.scan_status,
            "result": request.app.state.scan_result,
        },
    )
```

- [ ] **Step 3: Verify syntax**

```bash
cd /home/missia03/Projects/career-ops-fr
source .venv/bin/activate
python -c "import sys; sys.path.insert(0, 'dashboard'); import app; print('ok')"
```

Expected output: `ok`

---

## Task 4: Add scan button to index.html

**Files:**
- Modify: `dashboard/templates/index.html`

- [ ] **Step 1: Add the scan-status div in the filter bar**

In `dashboard/templates/index.html`, the filter bar div currently ends with the two selects and closes at a `</div>`. Add the scan status div after the flex row with selects:

Current (lines 8-35 of index.html):
```html
    <div class="p-3 border-b border-slate-700 flex flex-col gap-2">
      <input
        ...
        id="search-input">
      <div class="flex gap-2">
        <select name="status" ...>
          ...
        </select>
        <select name="grade" ...>
          ...
        </select>
      </div>
    </div>
```

Replace the closing `</div>` of the filter bar with:

```html
      <div class="flex gap-2">
        <select name="status" id="status-filter"
          class="flex-1 bg-slate-800 text-slate-200 text-sm rounded px-2 py-2 border border-slate-600 focus:outline-none focus:border-violet-500"
          hx-get="/offers" hx-trigger="change"
          hx-target="#offer-list" hx-include="[name='q'],[name='grade']">
          <option value="">Tous statuts</option>
          {% for s in statuses %}
          <option value="{{ s }}">{{ s }}</option>
          {% endfor %}
        </select>
        <select name="grade" id="grade-filter"
          class="flex-1 bg-slate-800 text-slate-200 text-sm rounded px-2 py-2 border border-slate-600 focus:outline-none focus:border-violet-500"
          hx-get="/offers" hx-trigger="change"
          hx-target="#offer-list" hx-include="[name='q'],[name='status']">
          <option value="">Tous grades</option>
          {% for g in ["A","B","C","D","F"] %}
          <option value="{{ g }}">{{ g }}</option>
          {% endfor %}
        </select>
      </div>
      {% include "partials/scan_status.html" %}
    </div>
```

But the initial render needs `status` and `result` variables. Update `dashboard/app.py` route `GET /` to pass them:

```python
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db = request.app.state.db
    offers = db.get_all({})
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "offers": offers,
            "statuses": VALID_STATUSES,
            "status": request.app.state.scan_status,
            "result": request.app.state.scan_result,
        },
    )
```

- [ ] **Step 2: Verify the page renders**

```bash
cd /home/missia03/Projects/career-ops-fr
source .venv/bin/activate
python -c "
import sys
sys.path.insert(0, 'dashboard')
from fastapi.testclient import TestClient
import app as dashboard_app
client = TestClient(dashboard_app.app)
r = client.get('/')
assert r.status_code == 200
assert 'Scanner' in r.text
print('ok')
"
```

Expected output: `ok`

---

## Task 5: Write and run the scan tests

**Files:**
- Modify: `tests/test_dashboard_app.py`

- [ ] **Step 1: Write the failing tests**

At the bottom of `tests/test_dashboard_app.py`, add:

```python
class TestScan:
    def test_scan_start_when_idle_returns_running(self, client):
        import app as dashboard_app

        dashboard_app.app.state.scan_status = "idle"
        r = client.post("/scan/start")
        assert r.status_code == 200
        assert "Scan en cours" in r.text

    def test_scan_start_when_running_does_not_create_second_task(self, client, monkeypatch):
        import app as dashboard_app

        dashboard_app.app.state.scan_status = "running"
        created = []

        original_create_task = __import__("asyncio").create_task

        def mock_create_task(coro):
            created.append(coro)
            coro.close()
            return None

        monkeypatch.setattr("asyncio.create_task", mock_create_task)
        r = client.post("/scan/start")
        assert r.status_code == 200
        assert len(created) == 0

    def test_scan_status_idle(self, client):
        import app as dashboard_app

        dashboard_app.app.state.scan_status = "idle"
        dashboard_app.app.state.scan_result = {"inserted": 0, "skipped": 0, "error": ""}
        r = client.get("/scan/status")
        assert r.status_code == 200
        assert "Scanner" in r.text
        assert "Scan en cours" not in r.text

    def test_scan_status_done_shows_inserted_count(self, client):
        import app as dashboard_app

        dashboard_app.app.state.scan_status = "done"
        dashboard_app.app.state.scan_result = {"inserted": 3, "skipped": 5, "error": ""}
        r = client.get("/scan/status")
        assert r.status_code == 200
        assert "3" in r.text

    def test_scan_status_error_shows_message(self, client):
        import app as dashboard_app

        dashboard_app.app.state.scan_status = "error"
        dashboard_app.app.state.scan_result = {"inserted": 0, "skipped": 0, "error": "Connection timeout"}
        r = client.get("/scan/status")
        assert r.status_code == 200
        assert "Erreur" in r.text

    def test_scan_full_flow(self, client, monkeypatch):
        import asyncio
        import app as dashboard_app
        from app import _run_scan_task

        dashboard_app.app.state.scan_status = "idle"
        dashboard_app.app.state.scan_result = {"inserted": 0, "skipped": 0, "error": ""}

        async def fake_run_pipeline(_settings):
            return []

        def fake_import_offers(_offers, _path):
            return (7, 2)

        def fake_load_settings():
            return {}

        monkeypatch.setattr("scripts.import_offers._run_pipeline", fake_run_pipeline)
        monkeypatch.setattr("scripts.import_offers.import_offers", fake_import_offers)
        monkeypatch.setattr("scripts.pre_filter.load_settings", fake_load_settings)

        # Run the task coroutine directly (avoids asyncio.create_task in sync test context)
        asyncio.get_event_loop().run_until_complete(
            _run_scan_task(dashboard_app.app.state)
        )

        assert dashboard_app.app.state.scan_status == "done"
        assert dashboard_app.app.state.scan_result["inserted"] == 7


class TestPrepareCandidature:
    def test_offer_detail_contains_prepare_command(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({})[0]
        r = client_with_data.get(f"/offers/{row['id']}")
        assert r.status_code == 200
        assert f"prepare-candidature.md --offer-id {row['id']}" in r.text
```

- [ ] **Step 2: Run the tests to verify they fail correctly (before implementation is wired up)**

```bash
cd /home/missia03/Projects/career-ops-fr
source .venv/bin/activate
pytest tests/test_dashboard_app.py::TestScan tests/test_dashboard_app.py::TestPrepareCandidature -v 2>&1 | tail -20
```

Expected: some tests fail because `/scan/start` and `/scan/status` don't exist yet (404) — confirms tests are real.

- [ ] **Step 3: Run the full test suite**

```bash
cd /home/missia03/Projects/career-ops-fr
source .venv/bin/activate
pytest tests/test_dashboard_app.py -v 2>&1 | tail -30
```

Expected: all existing tests pass, new scan+prepare tests pass too.

- [ ] **Step 4: Run the complete pytest suite**

```bash
cd /home/missia03/Projects/career-ops-fr
source .venv/bin/activate
pytest --tb=short 2>&1 | tail -20
```

Expected: all tests pass (or same baseline failures as before this work).

---

## Task 6: Update CHANGELOG and commit

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add CHANGELOG entry**

In `CHANGELOG.md`, under `## [Unreleased]` add:

```markdown
## [Unreleased]

## 2026-05-28

### Added
- `dashboard/templates/partials/scan_status.html` — HTMX partial for scan button/badge (idle, running, done, error states)
- `dashboard/app.py` — `POST /scan/start` and `GET /scan/status` endpoints: trigger full import pipeline as asyncio Task with live HTMX polling feedback
- `tests/test_dashboard_app.py` — `TestScan` (6 tests) and `TestPrepareCandidature` (1 test)

### Changed
- `dashboard/app.py` — `GET /` passes `status` and `result` to template for initial scan button render
- `dashboard/templates/index.html` — scan button added to filter bar via `scan_status.html` include
```

- [ ] **Step 2: Commit**

```bash
cd /home/missia03/Projects/career-ops-fr
git add dashboard/app.py \
        dashboard/templates/partials/scan_status.html \
        dashboard/templates/index.html \
        tests/test_dashboard_app.py \
        CHANGELOG.md \
        docs/superpowers/specs/2026-05-28-scan-button-and-prepare-candidature-design.md \
        docs/superpowers/plans/2026-05-28-scan-button-and-prepare-candidature.md
git commit -m "feat: add scan button with HTMX live feedback and prepare-candidature tests"
```
