# UI Redesign — Gradient Sombre & Vivid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the dashboard UI to a deep-purple Gradient Sombre & Vivid style with Indigo+Rose accent colors, keeping the sidebar-fixed layout and all existing functionality intact.

**Architecture:** Pure visual/HTML/CSS changes — no Python, no routes, no logic. All templates live in `dashboard/templates/`. Shared styles go in `base.html`; page/partial-specific styles stay inline or in `<style>` blocks within each file.

**Tech Stack:** Tailwind CSS (CDN), HTMX, Jinja2. No new dependencies.

---

## Files to Modify

| File | What changes |
|------|-------------|
| `dashboard/templates/base.html` | Global bg, nav style, CSS variables / shared utility classes |
| `dashboard/templates/index.html` | Filter bar, panel bg colors, border colors |
| `dashboard/templates/partials/offer_list.html` | Card style, avatar initials, grade/status badges |
| `dashboard/templates/partials/offer_empty.html` | Empty state copy styling |
| `dashboard/templates/partials/offer_detail.html` | Header, metadata grid, action buttons, status buttons |
| `dashboard/templates/partials/offer_notes.html` | Textarea + label styling |
| `dashboard/templates/partials/offer_form.html` | Input/select/textarea + button styling |
| `dashboard/templates/partials/scan_status.html` | Scan button variants (idle/running/done/error) |
| `dashboard/templates/stats.html` | KPI cards, bar chart, status pills |
| `dashboard/templates/profile.html` | Accordion styles, profile header, pf-* classes |

---

## Color Reference

| Token | Value | Use |
|-------|-------|-----|
| bg-deep | `#0f0a1e` | Page background |
| bg-surface | `#1e1535` | Cards, panels, nav |
| bg-raised | `#1a1030` | Slightly lighter surface (nested cards) |
| border-subtle | `#2d1f5e` | Default borders |
| border-muted | `#221845` | Dimmer borders |
| accent-indigo | `#6366f1` | Primary accent, active borders |
| accent-violet | `#8b5cf6` | Secondary accent, links |
| accent-rose | `#ec4899` | Decorative gradients, grade-A badge end |
| text-bright | `#f1f5f9` | Primary text |
| text-muted | `#94a3b8` | Labels, secondary text |
| text-dim | `#64748b` | Placeholder, disabled |

---

## Task 1: Global base — `base.html`

**Files:**
- Modify: `dashboard/templates/base.html`

- [ ] **Step 1: Rewrite base.html**

Replace the entire file with:

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>career-ops-fr</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <style>
    body { background: #0f0a1e; color: #e2e8f0; }
    .scrollable { overflow-y: auto; }
    /* Gradient accent utility */
    .bg-accent { background: linear-gradient(135deg, #6366f1, #8b5cf6); }
    .bg-accent-rose { background: linear-gradient(135deg, #6366f1, #ec4899); }
    .text-accent { color: #a5b4fc; }
    /* Grade badge colors */
    .grade-a { background: linear-gradient(135deg, #6366f1, #ec4899); color: #fff; }
    .grade-b { background: linear-gradient(135deg, #1d4ed8, #6366f1); color: #fff; }
    .grade-c { background: linear-gradient(135deg, #d97706, #f59e0b); color: #fff; }
    .grade-d { background: linear-gradient(135deg, #b45309, #d97706); color: #fff; }
    .grade-f { background: #374151; color: #9ca3af; }
  </style>
</head>
<body class="h-screen flex flex-col" style="background: linear-gradient(135deg, #0f0a1e 0%, #1a0f30 100%);">
  <nav style="background:#1e1535;border-bottom:1px solid #2d1f5e;" class="px-5 py-3 flex items-center gap-6 shrink-0">
    <span class="font-bold text-lg" style="background:linear-gradient(135deg,#a5b4fc,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">career-ops-fr</span>
    <a href="/" class="{{ 'text-indigo-400 font-semibold border-b border-indigo-400 pb-0.5' if request.url.path == '/' else 'text-slate-400 hover:text-slate-200' }} text-sm transition-colors">Candidatures</a>
    <a href="/stats" class="{{ 'text-indigo-400 font-semibold border-b border-indigo-400 pb-0.5' if request.url.path == '/stats' else 'text-slate-400 hover:text-slate-200' }} text-sm transition-colors">Stats</a>
    <a href="/profile" class="{{ 'text-indigo-400 font-semibold border-b border-indigo-400 pb-0.5' if request.url.path == '/profile' else 'text-slate-400 hover:text-slate-200' }} text-sm transition-colors">Profil</a>
  </nav>
  <main class="flex-1 overflow-hidden">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Start the dev server and verify the nav renders**

```bash
cd /home/missia03/Projects/career-ops-fr
source .venv/bin/activate
uvicorn dashboard.app:app --reload --port 8000
```

Open http://localhost:8000 — nav should show deep-purple background, gradient logo text, indigo active link.

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/base.html
git commit -m "style: redesign nav — deep-purple bg, indigo+rose accent"
```

---

## Task 2: Index page panels — `index.html`

**Files:**
- Modify: `dashboard/templates/index.html`

- [ ] **Step 1: Rewrite index.html**

Replace the entire file with:

```html
{% extends "base.html" %}
{% block content %}
<div class="flex h-full gap-0">

  <!-- Left panel: filters + list -->
  <div class="w-96 shrink-0 flex flex-col" style="background:#1e1535;border-right:1px solid #2d1f5e;">
    <!-- Filter bar -->
    <div class="p-3 flex flex-col gap-2" style="border-bottom:1px solid #2d1f5e;">
      <input
        style="background:#0f0a1e;border:1px solid #2d1f5e;color:#e2e8f0;"
        class="w-full text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500 transition-colors placeholder-slate-500"
        type="text" name="q" placeholder="🔍  Rechercher entreprise ou rôle..."
        hx-get="/offers" hx-trigger="keyup changed delay:300ms"
        hx-target="#offer-list" hx-include="[name='status'],[name='grade']"
        id="search-input">
      <div class="flex gap-2">
        <select name="status" id="status-filter"
          style="background:#0f0a1e;border:1px solid #2d1f5e;color:#e2e8f0;"
          class="flex-1 text-sm rounded-lg px-2 py-2 focus:outline-none focus:border-indigo-500 transition-colors"
          hx-get="/offers" hx-trigger="change"
          hx-target="#offer-list" hx-include="[name='q'],[name='grade']">
          <option value="">Tous statuts</option>
          {% for s in statuses %}
          <option value="{{ s }}">{{ s }}</option>
          {% endfor %}
        </select>
        <select name="grade" id="grade-filter"
          style="background:#0f0a1e;border:1px solid #2d1f5e;color:#e2e8f0;"
          class="flex-1 text-sm rounded-lg px-2 py-2 focus:outline-none focus:border-indigo-500 transition-colors"
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
    <!-- Offer list -->
    <div id="offer-list" class="flex-1 scrollable">
      {% include "partials/offer_list.html" %}
    </div>
  </div>

  <!-- Right panel: detail -->
  <div id="offer-detail" class="flex-1 scrollable p-6">
    {% include "partials/offer_empty.html" %}
  </div>

</div>
{% endblock %}
```

- [ ] **Step 2: Verify in browser**

Reload http://localhost:8000 — left panel should have `#1e1535` bg, right panel transparent (showing through body gradient). Filter inputs dark.

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/index.html
git commit -m "style: redesign index panels — dark surface, indigo focus rings"
```

---

## Task 3: Offer list cards — `offer_list.html`

**Files:**
- Modify: `dashboard/templates/partials/offer_list.html`

Note: `STATUS_COLORS` and `GRADE_COLORS` dicts are injected from `dashboard/app.py`. We'll keep using them for status pills but replace grade badges with CSS classes defined in `base.html` (`grade-a`, `grade-b`, etc.).

- [ ] **Step 1: Rewrite offer_list.html**

```html
{% if not offers %}
<div class="p-5 text-slate-500 text-sm text-center mt-8">Aucune offre trouvée.</div>
{% endif %}
{% for offer in offers %}
{% set initials = (offer.company[:1] | upper) if offer.company else '?' %}
<div
  class="px-3 py-2.5 cursor-pointer transition-colors flex items-center gap-3"
  style="border-bottom:1px solid #221845;"
  onmouseover="this.style.background='#251b45'"
  onmouseout="this.style.background='transparent'"
  hx-get="/offers/{{ offer.id }}"
  hx-target="#offer-detail"
  hx-swap="innerHTML">

  <!-- Avatar initials -->
  <div class="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-white bg-accent">
    {{ initials }}
  </div>

  <!-- Company + role -->
  <div class="min-w-0 flex-1">
    <div class="text-sm font-semibold truncate" style="color:#f1f5f9;">{{ offer.company }}</div>
    <div class="text-xs truncate" style="color:#8b5cf6;">{{ offer.role }}</div>
  </div>

  <!-- Grade badge -->
  <div class="shrink-0 flex flex-col items-end gap-1">
    <span class="text-xs px-2 py-0.5 rounded font-bold
      {% if offer.score_grade == 'A' %}grade-a
      {% elif offer.score_grade == 'B' %}grade-b
      {% elif offer.score_grade == 'C' %}grade-c
      {% elif offer.score_grade == 'D' %}grade-d
      {% else %}grade-f{% endif %}">
      {{ offer.score_grade }}
    </span>
    <span class="text-xs px-1.5 py-0.5 rounded font-medium
      {{ STATUS_COLORS.get(offer.status, 'bg-gray-700 text-gray-200') }}">
      {{ offer.status }}
    </span>
  </div>
</div>
{% endfor %}
```

- [ ] **Step 2: Verify in browser**

Each offer row shows avatar circle, company in bright text, role in indigo, grade badge on right.

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/partials/offer_list.html
git commit -m "style: redesign offer list — avatar initials, gradient grade badges"
```

---

## Task 4: Offer empty state — `offer_empty.html`

**Files:**
- Modify: `dashboard/templates/partials/offer_empty.html`

- [ ] **Step 1: Rewrite offer_empty.html**

```html
<div class="flex flex-col items-center justify-center h-full gap-3 text-center">
  <div class="w-12 h-12 rounded-xl bg-accent-rose opacity-20 flex items-center justify-content:center"></div>
  <p style="color:#64748b;" class="text-sm">Sélectionne une offre pour voir le détail</p>
</div>
```

- [ ] **Step 2: Verify in browser**

Right panel shows centered muted text when no offer is selected.

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/partials/offer_empty.html
git commit -m "style: redesign empty state"
```

---

## Task 5: Offer detail — `offer_detail.html`

**Files:**
- Modify: `dashboard/templates/partials/offer_detail.html`

- [ ] **Step 1: Rewrite offer_detail.html**

```html
<div class="max-w-2xl">

  <!-- Header -->
  <div class="flex items-start justify-between mb-5">
    <div class="flex items-center gap-3">
      <div class="w-12 h-12 rounded-xl flex items-center justify-content:center items-center justify-center text-xl font-bold text-white bg-accent shrink-0">
        {{ (offer.company[:1] | upper) if offer.company else '?' }}
      </div>
      <div>
        <h2 class="text-xl font-bold" style="color:#f1f5f9;">{{ offer.company }}</h2>
        <p style="color:#a5b4fc;" class="text-sm">{{ offer.role }}</p>
      </div>
    </div>
    <div class="flex gap-2 items-center shrink-0">
      <span class="text-sm px-3 py-1 rounded-lg font-bold
        {% if offer.score_grade == 'A' %}grade-a
        {% elif offer.score_grade == 'B' %}grade-b
        {% elif offer.score_grade == 'C' %}grade-c
        {% elif offer.score_grade == 'D' %}grade-d
        {% else %}grade-f{% endif %}">
        {{ offer.score_grade }} {{ "%.1f"|format(offer.score_value) }}
      </span>
      <span class="text-sm px-3 py-1 rounded-lg font-medium
        {{ STATUS_COLORS.get(offer.status, 'bg-gray-700 text-gray-200') }}">
        {{ offer.status }}
      </span>
    </div>
  </div>

  <!-- Divider -->
  <div style="height:1px;background:linear-gradient(90deg,#6366f1,transparent);margin-bottom:1.25rem;"></div>

  <!-- Fields -->
  <dl class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm mb-6">
    <dt style="color:#8b5cf6;">Détecté le</dt>
    <dd style="color:#e2e8f0;">{{ offer.detection_date }}</dd>
    {% if offer.send_date %}
    <dt style="color:#8b5cf6;">Envoyé le</dt>
    <dd style="color:#e2e8f0;">{{ offer.send_date }}</dd>
    {% endif %}
    {% if offer.follow_up_date %}
    <dt style="color:#8b5cf6;">Relance</dt>
    <dd style="color:#e2e8f0;">{{ offer.follow_up_date }}</dd>
    {% endif %}
    {% if offer.offer_url and offer.offer_url.startswith(('http://', 'https://')) %}
    <dt style="color:#8b5cf6;">URL</dt>
    <dd><a href="{{ offer.offer_url }}" target="_blank" rel="noopener noreferrer"
          class="hover:text-indigo-300 underline break-all text-xs" style="color:#a5b4fc;">
      {{ offer.offer_url }}</a></dd>
    {% endif %}
    {% if offer.cv_path %}
    <dt style="color:#8b5cf6;">CV</dt>
    <dd style="color:#e2e8f0;" class="text-xs break-all">{{ offer.cv_path }}</dd>
    {% endif %}
    {% if offer.cover_letter_path %}
    <dt style="color:#8b5cf6;">LM</dt>
    <dd style="color:#e2e8f0;" class="text-xs break-all">{{ offer.cover_letter_path }}</dd>
    {% endif %}
    {% if offer.contacts %}
    <dt style="color:#8b5cf6;">Contacts</dt>
    <dd style="color:#e2e8f0;">{{ offer.contacts }}</dd>
    {% endif %}
  </dl>

  {% if offer.description %}
  <div class="mb-6">
    <p style="color:#8b5cf6;" class="text-sm mb-1">Description</p>
    <details>
      <summary class="text-sm cursor-pointer hover:text-white transition-colors" style="color:#cbd5e1;">
        {{ offer.description[:200] }}{% if offer.description|length > 200 %}…{% endif %}
      </summary>
      {% if offer.description|length > 200 %}
      <p class="text-sm mt-2 whitespace-pre-wrap rounded-lg p-3" style="color:#cbd5e1;background:#1e1535;border:1px solid #2d1f5e;">{{ offer.description }}</p>
      {% endif %}
    </details>
  </div>
  {% endif %}

  <div class="mb-6">
    {% include "partials/offer_notes.html" %}
  </div>

  <!-- Status quick-change -->
  <div class="mb-5">
    <p style="color:#8b5cf6;" class="text-sm mb-2">Changer le statut</p>
    <div class="flex flex-wrap gap-2">
      {% for s in statuses %}
      <button
        class="text-xs px-2.5 py-1 rounded-lg font-medium border transition-colors
          {% if s == offer.status %}border-indigo-500 {{ STATUS_COLORS.get(s, '') }}{% else %}border-[#2d1f5e] text-slate-400 hover:border-indigo-400 hover:text-slate-200{% endif %}"
        hx-post="/offers/{{ offer.id }}/status"
        hx-vals='{{ {"status": s} | tojson }}'
        hx-target="#offer-detail"
        hx-swap="innerHTML">
        {{ s }}
      </button>
      {% endfor %}
    </div>
  </div>

  <!-- Action buttons -->
  <div class="flex gap-3 flex-wrap">
    <button
      class="text-sm px-4 py-2 rounded-lg text-white font-medium transition-colors"
      style="background:#1e1535;border:1px solid #2d1f5e;"
      onmouseover="this.style.borderColor='#6366f1'"
      onmouseout="this.style.borderColor='#2d1f5e'"
      hx-get="/offers/{{ offer.id }}/edit"
      hx-target="#offer-detail"
      hx-swap="innerHTML">
      ✏️ Modifier
    </button>
    <button
      class="text-sm px-4 py-2 rounded-lg text-white font-medium transition-colors"
      style="background:rgba(185,28,28,0.25);border:1px solid rgba(185,28,28,0.4);"
      onmouseover="this.style.background='rgba(185,28,28,0.4)'"
      onmouseout="this.style.background='rgba(185,28,28,0.25)'"
      hx-delete="/offers/{{ offer.id }}"
      hx-target="#offer-detail"
      hx-swap="innerHTML"
      hx-confirm="Supprimer cette candidature ?">
      🗑 Supprimer
    </button>
    <button
      class="text-sm px-4 py-2 rounded-lg text-white font-medium bg-accent transition-opacity hover:opacity-90"
      onclick="copyPrepCmd({{ offer.id }})"
      id="prep-btn-{{ offer.id }}">
      ✦ Préparer candidature
    </button>
  </div>

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
</div>
```

- [ ] **Step 2: Click an offer in the browser and verify**

Detail panel shows: large avatar, gradient divider below header, indigo labels in metadata grid, gradient "Préparer candidature" button.

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/partials/offer_detail.html
git commit -m "style: redesign offer detail — avatar header, gradient divider, indigo labels"
```

---

## Task 6: Notes textarea — `offer_notes.html`

**Files:**
- Modify: `dashboard/templates/partials/offer_notes.html`

- [ ] **Step 1: Rewrite offer_notes.html**

```html
<div id="offer-notes-{{ offer.id }}">
  <div class="flex items-center justify-between mb-1.5">
    <p style="color:#8b5cf6;" class="text-sm font-medium">Notes</p>
    {% if saved %}
    <span class="text-xs" style="color:#4ade80;" id="notes-saved-{{ offer.id }}">✓ Sauvegardé</span>
    <script>
      setTimeout(function() {
        var el = document.getElementById("notes-saved-{{ offer.id }}");
        if (el) el.style.display = "none";
      }, 2000);
    </script>
    {% endif %}
  </div>
  <textarea
    name="notes"
    rows="6"
    placeholder="Questions à poser, points clés, impressions, contacts…"
    class="w-full text-sm rounded-lg p-3 resize-y focus:outline-none transition-colors placeholder-slate-500"
    style="background:#1e1535;border:1px solid #2d1f5e;color:#e2e8f0;"
    onfocus="this.style.borderColor='#6366f1'"
    onblur="this.style.borderColor='#2d1f5e'"
    hx-post="/offers/{{ offer.id }}/notes"
    hx-trigger="keyup changed delay:800ms"
    hx-target="#offer-notes-{{ offer.id }}"
    hx-swap="outerHTML"
    hx-include="this"
  >{{ offer.notes or "" }}</textarea>
</div>
```

- [ ] **Step 2: Verify in browser**

Notes textarea has dark surface bg, glows indigo on focus.

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/partials/offer_notes.html
git commit -m "style: redesign notes textarea — dark surface, indigo focus"
```

---

## Task 7: Edit form — `offer_form.html`

**Files:**
- Modify: `dashboard/templates/partials/offer_form.html`

- [ ] **Step 1: Rewrite offer_form.html**

```html
<!-- dashboard/templates/partials/offer_form.html -->
<form hx-post="/offers/{{ offer.id }}"
      hx-target="#offer-detail"
      hx-swap="innerHTML"
      class="max-w-2xl flex flex-col gap-3">

  <h2 class="text-lg font-bold mb-2" style="color:#f1f5f9;">Modifier — {{ offer.company }}</h2>

  {% set fields = [
    ("company", "Entreprise", offer.company, "text"),
    ("role", "Rôle", offer.role, "text"),
    ("offer_url", "URL offre", offer.offer_url, "text"),
    ("detection_date", "Date détection (YYYY-MM-DD)", offer.detection_date, "text"),
    ("score_grade", "Grade (A/B/C/D/F)", offer.score_grade, "text"),
    ("score_value", "Score (0.0–5.0)", offer.score_value, "text"),
    ("send_date", "Date envoi (YYYY-MM-DD)", offer.send_date or "", "text"),
    ("follow_up_date", "Date relance (YYYY-MM-DD)", offer.follow_up_date or "", "text"),
    ("contacts", "Contacts", offer.contacts, "text"),
    ("cv_path", "Chemin CV", offer.cv_path, "text"),
    ("cover_letter_path", "Chemin LM", offer.cover_letter_path, "text"),
  ] %}

  {% for name, label, value, type in fields %}
  <div>
    <label class="text-xs block mb-1" style="color:#8b5cf6;">{{ label }}</label>
    <input type="{{ type }}" name="{{ name }}" value="{{ value }}"
      class="w-full text-sm rounded-lg px-3 py-2 focus:outline-none transition-colors placeholder-slate-500"
      style="background:#1e1535;border:1px solid #2d1f5e;color:#e2e8f0;"
      onfocus="this.style.borderColor='#6366f1'"
      onblur="this.style.borderColor='#2d1f5e'">
  </div>
  {% endfor %}

  <div>
    <label class="text-xs block mb-1" style="color:#8b5cf6;">Statut</label>
    <select name="status"
      class="w-full text-sm rounded-lg px-3 py-2 focus:outline-none transition-colors"
      style="background:#1e1535;border:1px solid #2d1f5e;color:#e2e8f0;"
      onfocus="this.style.borderColor='#6366f1'"
      onblur="this.style.borderColor='#2d1f5e'">
      {% for s in statuses %}
      <option value="{{ s }}" {% if s == offer.status %}selected{% endif %}>{{ s }}</option>
      {% endfor %}
    </select>
  </div>

  <div>
    <label class="text-xs block mb-1" style="color:#8b5cf6;">Notes</label>
    <textarea name="notes" rows="4"
      class="w-full text-sm rounded-lg px-3 py-2 focus:outline-none transition-colors placeholder-slate-500"
      style="background:#1e1535;border:1px solid #2d1f5e;color:#e2e8f0;"
      onfocus="this.style.borderColor='#6366f1'"
      onblur="this.style.borderColor='#2d1f5e'">{{ offer.notes }}</textarea>
  </div>

  <div class="flex gap-3 mt-2">
    <button type="submit"
      class="text-sm px-4 py-2 rounded-lg text-white font-medium bg-accent hover:opacity-90 transition-opacity">
      Sauvegarder
    </button>
    <button type="button"
      class="text-sm px-4 py-2 rounded-lg text-white transition-colors"
      style="background:#1e1535;border:1px solid #2d1f5e;"
      onmouseover="this.style.borderColor='#6366f1'"
      onmouseout="this.style.borderColor='#2d1f5e'"
      hx-get="/offers/{{ offer.id }}"
      hx-target="#offer-detail"
      hx-swap="innerHTML">
      Annuler
    </button>
  </div>
</form>
```

- [ ] **Step 2: Click "Modifier" on an offer and verify**

Edit form shows dark inputs with indigo focus ring. "Sauvegarder" button uses gradient accent.

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/partials/offer_form.html
git commit -m "style: redesign edit form — dark inputs, indigo focus, gradient save button"
```

---

## Task 8: Scan status button — `scan_status.html`

**Files:**
- Modify: `dashboard/templates/partials/scan_status.html`

- [ ] **Step 1: Rewrite scan_status.html**

```html
{% if status == "running" %}
<div id="scan-status"
     hx-get="/scan/status"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
  <button disabled
          class="text-sm px-3 py-1.5 rounded-lg flex items-center gap-2 cursor-not-allowed transition-opacity opacity-60"
          style="background:#1e1535;border:1px solid #2d1f5e;color:#94a3b8;">
    <span class="inline-block w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin"></span>
    {% if result.found is defined and result.found > 0 %}
    Scan… {{ result.found }} trouvées{% if result.scored is defined and result.scored > 0 %}, {{ result.scored }} scorées{% endif %}
    {% else %}
    Scan en cours…
    {% endif %}
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
    class="text-sm px-3 py-1.5 rounded-lg font-medium text-white transition-opacity hover:opacity-90"
    style="background:linear-gradient(135deg,#065f46,#059669);border:1px solid rgba(5,150,105,0.3);">
    ✓ {{ result.inserted }} nouvelle{% if result.inserted != 1 %}s{% endif %}{% if result.get('abandoned', 0) > 0 %}, {{ result.abandoned }} expirée{% if result.abandoned != 1 %}s{% endif %}{% endif %} — Scanner
  </button>
</div>

{% elif status == "error" %}
<div id="scan-status">
  <button
    hx-post="/scan/start"
    hx-target="#scan-status"
    hx-swap="outerHTML"
    class="text-sm px-3 py-1.5 rounded-lg font-medium text-white transition-opacity hover:opacity-90"
    style="background:rgba(185,28,28,0.3);border:1px solid rgba(185,28,28,0.4);">
    ✗ Erreur — Réessayer
  </button>
</div>

{% else %}
<div id="scan-status">
  <button
    hx-post="/scan/start"
    hx-target="#scan-status"
    hx-swap="outerHTML"
    class="text-sm px-3 py-1.5 rounded-lg font-medium text-white bg-accent transition-opacity hover:opacity-90">
    ⟳ Scanner
  </button>
</div>
{% endif %}
```

- [ ] **Step 2: Verify in browser**

Idle Scanner button shows indigo gradient. Running state shows indigo spinner.

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/partials/scan_status.html
git commit -m "style: redesign scan button — indigo gradient, themed states"
```

---

## Task 9: Stats page — `stats.html`

**Files:**
- Modify: `dashboard/templates/stats.html`

- [ ] **Step 1: Rewrite stats.html**

```html
{% extends "base.html" %}
{% block content %}
<div class="p-8 max-w-2xl mx-auto overflow-y-auto h-full">
  <h1 class="text-2xl font-bold mb-8" style="color:#f1f5f9;">Statistiques</h1>

  <div class="grid grid-cols-2 gap-4 mb-8">

    <div class="rounded-xl p-5 relative overflow-hidden" style="background:#1e1535;border:1px solid #2d1f5e;">
      <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#6366f1,#8b5cf6);"></div>
      <p class="text-sm mb-1" style="color:#94a3b8;">Total candidatures</p>
      <p class="text-3xl font-bold" style="color:#f1f5f9;">{{ stats.total }}</p>
    </div>

    <div class="rounded-xl p-5 relative overflow-hidden" style="background:#1e1535;border:1px solid #2d1f5e;">
      <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#6366f1,#ec4899);"></div>
      <p class="text-sm mb-1" style="color:#94a3b8;">Taux de réponse</p>
      <p class="text-3xl font-bold" style="color:#f1f5f9;">{{ stats.response_rate }}%</p>
    </div>

    <div class="rounded-xl p-5 relative overflow-hidden" style="background:#1e1535;border:1px solid #2d1f5e;">
      <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#059669,#34d399);"></div>
      <p class="text-sm mb-1" style="color:#94a3b8;">Entretiens obtenus</p>
      <p class="text-3xl font-bold" style="color:#f1f5f9;">{{ stats.interview_count }}</p>
    </div>

    <div class="rounded-xl p-5 relative overflow-hidden {% if stats.stale_count > 0 %}border-amber-500/50{% endif %}"
         style="background:#1e1535;border:1px solid {% if stats.stale_count > 0 %}rgba(245,158,11,0.4){% else %}#2d1f5e{% endif %};">
      <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#d97706,#f59e0b);"></div>
      <p class="text-sm mb-1" style="color:#94a3b8;">Relances en retard (+7j)</p>
      <p class="text-3xl font-bold" style="color:{% if stats.stale_count > 0 %}#fbbf24{% else %}#f1f5f9{% endif %};">
        {{ stats.stale_count }}
      </p>
    </div>

  </div>

  <h2 class="text-lg font-semibold mb-4" style="color:#f1f5f9;">Par statut</h2>
  <div class="flex flex-col gap-3">
    {% for s in statuses %}
    {% set count = stats.by_status.get(s, 0) %}
    <div class="flex items-center gap-3">
      <span class="w-36 text-xs px-2 py-1 rounded-lg font-medium text-center
        {{ STATUS_COLORS.get(s, 'bg-gray-700 text-gray-200') }}">{{ s }}</span>
      <div class="flex-1 rounded-full h-2" style="background:#2d1f5e;">
        {% if stats.total > 0 %}
        <div class="h-2 rounded-full"
          style="width: {{ [count / stats.total * 100, 100] | min | int }}%;background:linear-gradient(90deg,#6366f1,#ec4899);"></div>
        {% endif %}
      </div>
      <span class="text-sm w-6 text-right" style="color:#cbd5e1;">{{ count }}</span>
    </div>
    {% endfor %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Open http://localhost:8000/stats and verify**

4 KPI cards with colored top borders, indigo→rose progress bars.

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/stats.html
git commit -m "style: redesign stats page — colored top borders, gradient bars"
```

---

## Task 10: Profile page — `profile.html`

**Files:**
- Modify: `dashboard/templates/profile.html`

- [ ] **Step 1: Replace the inline `<style>` block and profile header**

The profile page has a large `<style>` block for `.acc-btn`, `.pf-*` classes. Replace it with the new theme. Keep all HTML structure, `toggleAcc` script, and partial includes intact — only update colors.

Replace the `<style>` block (lines 86–117) with:

```html
<style>
  .acc-btn {
    width:100%; display:flex; justify-content:space-between; align-items:center;
    padding:0.55rem 1rem; background:#1e1535; border:1px solid #2d1f5e;
    border-radius:0.5rem; color:#e2e8f0; font-size:0.875rem; font-weight:600;
    cursor:pointer; text-align:left; margin-top:0.25rem; transition:background 0.15s;
  }
  .acc-btn:hover { background:#251b45; }
  .acc-btn.acc-open {
    border-bottom-left-radius:0; border-bottom-right-radius:0;
    border-bottom-color:transparent;
    background: linear-gradient(135deg, #1e1535, #2a1a50);
    color:#a5b4fc;
  }
  .acc-body {
    display:none; border:1px solid #2d1f5e; border-top:none;
    border-bottom-left-radius:0.5rem; border-bottom-right-radius:0.5rem;
    padding:1rem; background:#1e1535;
  }
  .acc-body.acc-open { display:block; }
  .chv { transition:transform 0.2s; }
  .acc-btn.acc-open .chv { transform:rotate(180deg); }

  .pf-input {
    width:100%; background:#0f0a1e; border:1px solid #2d1f5e; border-radius:0.5rem;
    color:#e2e8f0; padding:0.35rem 0.6rem; font-size:0.8rem; box-sizing:border-box;
    transition:border-color 0.15s;
  }
  .pf-input:focus { outline:none; border-color:#6366f1; }
  .pf-label { display:block; font-size:0.7rem; color:#8b5cf6; margin-bottom:0.2rem; }
  .pf-card {
    background:#0f0a1e; border:1px solid #2d1f5e; border-radius:0.5rem;
    padding:0.75rem; margin-bottom:0.5rem;
  }
  .pf-save-btn {
    background:linear-gradient(135deg,#6366f1,#8b5cf6); color:white; border:none;
    border-radius:0.5rem; padding:0.35rem 0.9rem; font-size:0.8rem; cursor:pointer;
    transition:opacity 0.15s;
  }
  .pf-save-btn:hover { opacity:0.9; }
  .pf-add-btn {
    background:transparent; border:1px dashed #2d1f5e; color:#8b5cf6;
    border-radius:0.5rem; padding:0.25rem 0.75rem; font-size:0.75rem; cursor:pointer;
    transition:border-color 0.15s, color 0.15s;
  }
  .pf-add-btn:hover { border-color:#6366f1; color:#a5b4fc; }
  .pf-del-btn {
    background:transparent; border:none; color:#f87171;
    font-size:0.75rem; cursor:pointer; padding:0;
  }
  .pf-flash { color:#4ade80; font-size:0.75rem; }
</style>
```

Also update the profile header section (lines 12–21) to use the new colors:

```html
  <div id="profile-header" class="flex justify-between items-start mb-6">
    <div>
      <h1 class="text-2xl font-bold" style="color:#f1f5f9;">{{ profile.contact.name or "Votre nom" }}</h1>
      <p class="text-sm" style="color:#a5b4fc;">{{ profile.contact.title }}</p>
    </div>
    <div class="text-right text-xs space-y-1" style="color:#8b5cf6;">
      {% if profile.contact.email %}<div>✉ {{ profile.contact.email }}</div>{% endif %}
      {% if profile.contact.github %}<div>⌥ {{ profile.contact.github }}</div>{% endif %}
    </div>
  </div>
```

Also update the warning banner (lines 6–9):

```html
  {% if not profile_exists %}
  <div class="rounded-lg p-3 mb-4 text-sm" style="background:rgba(120,53,15,0.3);border:1px solid rgba(245,158,11,0.4);color:#fbbf24;">
    Fichier profile.md introuvable — créez <code>config/profile.md</code> à partir de <code>config/profile.md.example</code>
  </div>
  {% endif %}
```

- [ ] **Step 2: Open http://localhost:8000/profile and verify**

Accordion buttons use `#1e1535` bg, active state has indigo gradient. Save buttons use indigo gradient. Input focus rings indigo.

- [ ] **Step 3: Commit**

```bash
git add dashboard/templates/profile.html
git commit -m "style: redesign profile page — indigo accordion, gradient save buttons"
```

---

## Task 11: Update CHANGELOG and README

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add CHANGELOG entry**

Add under `## [Unreleased]` at the top of `CHANGELOG.md`:

```markdown
## 2026-06-04

### Changed
- `dashboard/templates/` — full UI redesign: deep-purple gradient background (`#0f0a1e`→`#1a0f30`), Indigo+Rose accent palette, rounded-lg cards with surface/raised/border color system; no logic changes
- `dashboard/templates/base.html` — new nav style, shared `.grade-a/b/c/d/f` badge classes, `.bg-accent` / `.bg-accent-rose` utilities
- `dashboard/templates/partials/offer_list.html` — avatar initials per company, gradient grade badges
- `dashboard/templates/partials/offer_detail.html` — large avatar header, gradient divider, indigo metadata labels, styled action buttons
- `dashboard/templates/stats.html` — KPI cards with colored top borders, indigo→rose progress bars
- `dashboard/templates/profile.html` — accordion and form elements updated to match new theme
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for UI redesign [skip ci]"
```

---

## Final Verification

- [ ] Open http://localhost:8000 — sidebar dark purple, offer cards with avatars, grade badges gradient
- [ ] Open http://localhost:8000/stats — 4 KPI cards with colored top borders
- [ ] Open http://localhost:8000/profile — accordion buttons with new theme
- [ ] Click an offer → detail panel shows large avatar, gradient divider
- [ ] Click "Modifier" → form inputs have indigo focus ring
- [ ] Click "Scanner" → button shows indigo gradient
- [ ] Run `pytest` from repo root — all tests pass (no logic changed)
