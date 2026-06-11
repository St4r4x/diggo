# Apply vs Interview Split — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Séparer le bouton "Préparer candidature" (CV ± LM) du bouton "Préparer entretien" (fiche prep uniquement), chacun n'apparaissant qu'au bon moment du funnel.

**Architecture:** Logique purement frontend — Jinja2 conditionnel sur `offer.status` dans `offer_detail.html`, deux fonctions JS (`copyPrepCmd` / `copyInterviewCmd`), deux modes CLI (`prepare-candidature.md` + nouveau `prepare-entretien.md`). Aucun changement à `app.py`, `db.py`, ni aux scripts Python.

**Tech Stack:** Jinja2, Vanilla JS (clipboard API), Claude CLI modes (Markdown)

---

## File Map

| Fichier | Action | Responsabilité |
|---------|--------|----------------|
| `templates/partials/offer_detail.html` | Modify | Bloc action buttons conditionnel + checkbox + JS |
| `modes/prepare-candidature.md` | Modify | Ajouter règle `--no-prep` |
| `modes/prepare-entretien.md` | Create | Mode fiche prep uniquement |
| `tests/test_dashboard_app.py` | Modify | Mettre à jour `TestPrepareCandidature`, ajouter tests interview |

---

## Task 1 : Ajouter règle `--no-prep` dans `prepare-candidature.md`

**Files:**
- Modify: `modes/prepare-candidature.md`

- [ ] **Step 1 : Ouvrir le fichier et repérer la section Instructions**

```
modes/prepare-candidature.md — Section ## Instructions, ligne ~30
```

- [ ] **Step 2 : Ajouter la règle `--no-prep` en tête de la section Instructions**

Insérer ce bloc juste AVANT la ligne `### Phase 1 — Load context` :

```markdown
### Flag `--no-prep`

If the user message contains `--no-prep`, skip Phase 5 entirely (do not generate the prep sheet).
Run Phase 6 as normal but only update `cv_path` and `cover_letter_path` in the DB.
```

- [ ] **Step 3 : Vérifier que le fichier est cohérent**

```bash
grep -n "no-prep\|Phase 5\|Phase 6" modes/prepare-candidature.md
```

Expected output : lignes avec `--no-prep`, `Phase 5`, `Phase 6` toutes présentes.

- [ ] **Step 4 : Commit**

```bash
git add modes/prepare-candidature.md
git commit -m "feat: add --no-prep flag to prepare-candidature mode"
```

---

## Task 2 : Créer `modes/prepare-entretien.md`

**Files:**
- Create: `modes/prepare-entretien.md`

- [ ] **Step 1 : Créer le fichier**

```markdown
# prepare-entretien

Generate the interview prep sheet PDF for a specific offer. Called after the CV has been selected.

## Input

Called with:
```bash
claude --system-prompt "$(cat modes/prepare-entretien.md)" "Prépare l'entretien pour l'offre ID <id>"
```

Extract the offer ID from the user message. Look for a number after "ID", "id", "offer-id", or "offre".

If no ID is found in the message, ask: "Quel est l'ID de l'offre ?"

## Instructions

### Phase 1 — Load context

1. Read `config/profile.md`
2. Query the DB:
   ```bash
   sqlite3 dashboard/data/applications.db \
     "SELECT id, company, role, offer_url, description FROM applications WHERE id = <offer_id>;"
   ```
3. Derive slug: `company.lower().replace(' ', '-')`
4. If `description` is empty or less than 500 characters, fetch the full job description:
   ```bash
   python -c "import httpx; r = httpx.get('<offer_url>', follow_redirects=True, timeout=15); print(r.text[:12000])"
   ```
   Extract the meaningful text mentally (strip HTML tags, navigation, footers).

### Phase 2 — Analyse the offer

From the description, extract:
- `top_skills`: 5–7 required skills mentioned explicitly (exact terms from the posting)
- `company_context`: mission, product, estimated size, tech stack mentioned

### Phase 3 — Generate prep sheet

1. Build `/tmp/prep-context-<slug>.json`:
   ```json
   {
     "company": "<company>",
     "role": "<role>",
     "date_str": "<YYYY-MM-DD>",
     "company_summary": "<2-3 sentences: mission, product, size, why interesting>",
     "tech_stack": ["<tech1>", "<tech2>"],
     "questions": [
       {"theme": "Technique ML", "question": "<question>"},
       {"theme": "MLOps", "question": "<question>"},
       {"theme": "Comportemental", "question": "<question>"}
     ]
   }
   ```
   Aim for 8–12 questions covering: technical depth (linked to top_skills), MLOps/deployment,
   behavioural (STAR format expected), and "why us / why this role".
2. Run:
   ```bash
   python scripts/generate_prep_sheet.py \
     --offer "<slug>" \
     --date "<YYYY-MM-DD>" \
     --context-file /tmp/prep-context-<slug>.json
   ```
   Note the output path printed.

### Phase 4 — Summarise

Print:
```
✅ Fiche entretien prête — <company> / <role>

Fiche révision: output/<slug>-<date>/prep-sheet-<slug>-<date>.pdf

Ouvre le PDF et révise avant l'entretien.
```

## Constraints

- Do NOT generate a CV or cover letter — this mode is for interview prep only.
- Do NOT update cv_path or cover_letter_path in the DB.
- Prep sheet: 8–12 questions minimum.
```

- [ ] **Step 2 : Vérifier que le fichier est lisible**

```bash
head -5 modes/prepare-entretien.md
```

Expected: `# prepare-entretien`

- [ ] **Step 3 : Commit**

```bash
git add modes/prepare-entretien.md
git commit -m "feat: add prepare-entretien mode (prep sheet only)"
```

---

## Task 3 : Mettre à jour les tests de `TestPrepareCandidature`

**Files:**
- Modify: `tests/test_dashboard_app.py`

- [ ] **Step 1 : Identifier les fixtures à ajouter**

La fixture `client_with_data` crée 2 offres avec statut `À envoyer` et `Envoyée`.
On a besoin d'une offre en statut `Entretien RH` pour tester le bouton entretien.

Ajouter une fixture `client_with_interview_offer` dans la classe ou au niveau module :

```python
@pytest.fixture
def client_with_interview_offer(client):
    import app as dashboard_app

    db = dashboard_app.app.state.db
    db.conn.execute(
        "INSERT INTO applications (company, role, offer_url, detection_date, "
        "score_grade, score_value, status) VALUES (?,?,?,?,?,?,?)",
        (
            "Hugging Face",
            "ML Engineer",
            "https://apply.workable.com/huggingface/1",
            "2026-06-01",
            "A",
            4.8,
            "Entretien RH",
        ),
    )
    db.conn.commit()
    return client
```

Ajouter cette fixture dans `tests/test_dashboard_app.py`, après la fixture `client_with_data` (vers ligne 72).

- [ ] **Step 2 : Mettre à jour `TestPrepareCandidature`**

Remplacer la classe entière `TestPrepareCandidature` par :

```python
class TestPrepareCandidature:
    def test_apply_status_shows_prep_button(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = next(r for r in db.get_all({}) if r["status"] == "À envoyer")
        r = client_with_data.get(f"/offers/{row['id']}")
        assert r.status_code == 200
        assert "copyPrepCmd" in r.text
        assert f"copyPrepCmd({row['id']})" in r.text

    def test_apply_status_shows_lm_checkbox(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = next(r for r in db.get_all({}) if r["status"] == "À envoyer")
        r = client_with_data.get(f"/offers/{row['id']}")
        assert "lettre" in r.text.lower() or "lm" in r.text.lower()

    def test_apply_status_cv_only_command_uses_generate_cv(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = next(r for r in db.get_all({}) if r["status"] == "À envoyer")
        r = client_with_data.get(f"/offers/{row['id']}")
        assert "generate-cv.md" in r.text

    def test_apply_status_with_lm_command_uses_prepare_candidature(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = next(r for r in db.get_all({}) if r["status"] == "À envoyer")
        r = client_with_data.get(f"/offers/{row['id']}")
        assert "prepare-candidature.md" in r.text
        assert "--no-prep" in r.text

    def test_interview_status_shows_interview_button(self, client_with_interview_offer):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = next(r for r in db.get_all({}) if r["status"] == "Entretien RH")
        r = client_with_interview_offer.get(f"/offers/{row['id']}")
        assert r.status_code == 200
        assert "copyInterviewCmd" in r.text
        assert f"copyInterviewCmd({row['id']})" in r.text
        assert "prepare-entretien.md" in r.text

    def test_interview_status_hides_prep_button(self, client_with_interview_offer):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = next(r for r in db.get_all({}) if r["status"] == "Entretien RH")
        r = client_with_interview_offer.get(f"/offers/{row['id']}")
        assert "copyPrepCmd" not in r.text

    def test_terminal_status_shows_no_action_buttons(self, client_with_data):
        import app as dashboard_app

        db = dashboard_app.app.state.db
        row = db.get_all({})[0]
        db.update(row["id"], {"status": "Refusée"})
        r = client_with_data.get(f"/offers/{row['id']}")
        assert "copyPrepCmd" not in r.text
        assert "copyInterviewCmd" not in r.text
```

- [ ] **Step 3 : Lancer les tests pour confirmer qu'ils échouent (TDD)**

```bash
cd /home/missia03/Projects/career-ops-fr && .venv/bin/pytest tests/test_dashboard_app.py::TestPrepareCandidature -v 2>&1 | tail -20
```

Expected: plusieurs FAILED (les nouveaux tests, car `offer_detail.html` n'est pas encore modifié).

- [ ] **Step 4 : Commit des tests**

```bash
git add tests/test_dashboard_app.py
git commit -m "test: update TestPrepareCandidature — apply/interview/terminal split"
```

---

## Task 4 : Modifier `offer_detail.html` — logique conditionnelle

**Files:**
- Modify: `templates/partials/offer_detail.html`

- [ ] **Step 1 : Remplacer le bloc `<!-- Action buttons -->` entier**

Localiser ce bloc dans le fichier (lignes 89–118) :

```html
      <!-- Action buttons -->
      <div class="flex flex-col gap-2">
        <button
          ...
          ✏️ Modifier
        </button>
        <button
          class="... bg-accent ..."
          onclick="copyPrepCmd({{ offer.id }})"
          id="prep-btn-{{ offer.id }}">
          ✦ Préparer candidature
        </button>
        <button
          ...
          🗑 Supprimer
        </button>
      </div>
```

Le remplacer par :

```html
      <!-- Action buttons -->
      {% set apply_statuses = ["À envoyer", "Envoyée", "Relance"] %}
      {% set interview_statuses = ["Entretien RH", "Entretien tech", "Offre"] %}
      <div class="flex flex-col gap-2">
        <button
          class="text-sm px-4 py-2 rounded-lg text-white font-medium transition-colors text-left"
          style="background:#1e1535;border:1px solid #2d1f5e;"
          onmouseover="this.style.borderColor='#6366f1'"
          onmouseout="this.style.borderColor='#2d1f5e'"
          hx-get="/offers/{{ offer.id }}/edit"
          hx-target="#offer-detail"
          hx-swap="innerHTML">
          ✏️ Modifier
        </button>

        {% if offer.status in apply_statuses %}
        <label class="flex items-center gap-2 text-sm cursor-pointer select-none"
               style="color:#a5b4fc;">
          <input type="checkbox" id="lm-toggle-{{ offer.id }}"
                 class="accent-indigo-500 cursor-pointer">
          Inclure lettre de motivation
        </label>
        <button
          class="text-sm px-4 py-2 rounded-lg text-white font-medium bg-accent transition-opacity hover:opacity-90 text-left"
          onclick="copyPrepCmd({{ offer.id }})"
          id="prep-btn-{{ offer.id }}">
          ✦ Préparer candidature
        </button>
        {% elif offer.status in interview_statuses %}
        <button
          class="text-sm px-4 py-2 rounded-lg text-white font-medium bg-accent transition-opacity hover:opacity-90 text-left"
          onclick="copyInterviewCmd({{ offer.id }})"
          id="interview-btn-{{ offer.id }}">
          ✦ Préparer entretien
        </button>
        {% endif %}

        <button
          class="text-sm px-4 py-2 rounded-lg text-white font-medium transition-colors text-left"
          style="background:rgba(185,28,28,0.25);border:1px solid rgba(185,28,28,0.4);"
          onmouseover="this.style.background='rgba(185,28,28,0.4)'"
          onmouseout="this.style.background='rgba(185,28,28,0.25)'"
          hx-delete="/offers/{{ offer.id }}"
          hx-target="#offer-detail"
          hx-swap="innerHTML"
          hx-confirm="Supprimer cette candidature ?">
          🗑 Supprimer
        </button>
      </div>
```

- [ ] **Step 2 : Remplacer le bloc `<script>` en bas du fichier**

Localiser le bloc `<script>` existant (lignes 148–156) :

```html
  <script>
  function copyPrepCmd(id) {
    const cmd = "claude --system-prompt \"$(cat modes/prepare-candidature.md)\" \"Prépare la candidature pour l'offre ID " + id + "\"";
    navigator.clipboard.writeText(cmd).then(function() {
      var btn = document.getElementById("prep-btn-" + id);
      btn.textContent = "✓ Commande copiée !";
      setTimeout(function() { btn.textContent = "✦ Préparer candidature"; }, 2000);
    });
  }
  </script>
```

Le remplacer par :

```html
  <script>
  function copyPrepCmd(id) {
    var withLm = document.getElementById("lm-toggle-" + id);
    var cmd;
    if (withLm && withLm.checked) {
      cmd = "claude --system-prompt \"$(cat modes/prepare-candidature.md)\" \"Prépare la candidature pour l'offre ID " + id + " --no-prep\"";
    } else {
      cmd = "claude --system-prompt \"$(cat modes/generate-cv.md)\" \"Génère le CV pour l'offre ID " + id + "\"";
    }
    navigator.clipboard.writeText(cmd).then(function() {
      var btn = document.getElementById("prep-btn-" + id);
      btn.textContent = "✓ Commande copiée !";
      setTimeout(function() { btn.textContent = "✦ Préparer candidature"; }, 2000);
    });
  }

  function copyInterviewCmd(id) {
    var cmd = "claude --system-prompt \"$(cat modes/prepare-entretien.md)\" \"Prépare l'entretien pour l'offre ID " + id + "\"";
    navigator.clipboard.writeText.call(navigator.clipboard, cmd).then(function() {
      var btn = document.getElementById("interview-btn-" + id);
      btn.textContent = "✓ Commande copiée !";
      setTimeout(function() { btn.textContent = "✦ Préparer entretien"; }, 2000);
    });
  }
  </script>
```

- [ ] **Step 3 : Lancer les tests**

```bash
cd /home/missia03/Projects/career-ops-fr && .venv/bin/pytest tests/test_dashboard_app.py::TestPrepareCandidature -v 2>&1 | tail -20
```

Expected: tous PASSED.

- [ ] **Step 4 : Lancer la suite complète**

```bash
cd /home/missia03/Projects/career-ops-fr && .venv/bin/pytest --tb=short 2>&1 | tail -20
```

Expected: aucun test en FAILED.

- [ ] **Step 5 : Mettre à jour le CHANGELOG**

Dans `CHANGELOG.md`, sous `## [Unreleased]` (ou `## 2026-06-11`), ajouter :

```markdown
### Changed
- `templates/partials/offer_detail.html` — action buttons now conditional on offer status:
  "Préparer candidature" (with optional LM checkbox) shown for apply statuses only;
  "Préparer entretien" shown for interview statuses only; no action button for terminal statuses
- `modes/prepare-candidature.md` — added `--no-prep` flag to skip prep sheet generation
### Added
- `modes/prepare-entretien.md` — new Claude CLI mode generating interview prep sheet only
```

- [ ] **Step 6 : Commit final**

```bash
git add templates/partials/offer_detail.html CHANGELOG.md
git commit -m "feat: split apply/interview action buttons in offer detail panel"
```
