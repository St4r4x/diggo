# Intégrations sans LLM — Design Spec

**Date:** 2026-05-29
**Scope:** 3 groupes indépendants inspirés de `santifer/career-ops`, sans LLM

---

## Groupe 1 — Nouveaux signaux dans `pre_filter.py`

### 1a. Salaire normalisé (remplace le signal salary existant)

**Problème actuel :** le signal salary (+0.3) ne fait que détecter un chiffre dans la cible. Il ignore le 13e mois, les RTT, l'intéressement et le titre-restaurant — courants en France.

**Nouveau comportement :** reconstruire le package annuel total avant de scorer.

**Regex ajoutées :**

```python
_MONTHS_13_RE = re.compile(r"13[eè]me?\s*mois|treizi[eè]me\s*mois", re.IGNORECASE)
_RTT_RE = re.compile(r"(\d+)\s*RTT", re.IGNORECASE)
_TR_RE = re.compile(r"titre[\s-]restaurant|ticket[\s-]restaurant", re.IGNORECASE)
_INTERESSEMENT_RE = re.compile(r"int[eé]ressement|participation", re.IGNORECASE)
```

**Reconstruction du package :**
1. Extraire salaire de base via `_SALARY_RE` existant
2. Si valeur < 1000 → mensuel, multiplier × 13 si `_MONTHS_13_RE` sinon × 12
3. Si `_RTT_RE(n)` trouvé → `+ n × base_annuelle / 218`; si RTT mentionné sans chiffre → `+ 10 × base / 218`
4. Si `_TR_RE` → `+ 218 × 9` (défaut 9€/jour, 218 jours/an)
5. Si `_INTERESSEMENT_RE` → `+ base_annuelle × 0.05`
6. `total_package = base + rtt_val + tr_val + interessement_val`

**Score :**
- `total_package` dans `[target_salary_min, target_salary_max]` → **+0.5** (hausse vs +0.3 actuel)
- `total_package` hors cible → **-0.3** (pénalité explicite)
- Aucune info salariale → **0.0** (neutre, pas de pénalité)

**Tag :** `salary:<total_package>` (ex: `salary:48900`)

---

### 1b. Signal légitimité (pénalités uniquement, cap -0.5)

**Problème actuel :** une offre générique sans stack technique ni salaire est importée et scorée identiquement à une offre détaillée. Aucune distinction de qualité.

**Nouveau comportement :** pénalités basées sur des règles Python déterministes.

| Condition | Pénalité | Tag |
|-----------|----------|-----|
| `len(description) < 300` | -0.5 | `legitimacy:thin_desc` |
| 0 skill tech dans description | -0.3 | `legitimacy:no_tech` |
| Aucun salaire détectable | -0.2 | `legitimacy:no_salary` |

- Pénalités cumulées, cappées à **-0.5**
- `legitimacy:suspicious` ajouté si pénalité totale ≥ 0.3

**Note :** ancienneté > 90 jours non implémentée — `detection_date` en DB est la date d'import, pas la date de publication originale. Serait un faux positif.

---

## Groupe 2 — ATS Unicode normalisation dans `generate_pdf.py`

**Problème :** WeasyPrint génère un PDF avec des guillemets courbes, em-dashes et zero-width chars qui peuvent casser les parseurs ATS (Applicant Tracking Systems).

**Solution :** fonction `_normalize_for_ats(text: str) -> str` appliquée sur le contenu texte rendu par Jinja2, avant passage à WeasyPrint.

**Substitutions :**

```python
_ATS_REPLACEMENTS: list[tuple[str, str]] = [
    ("—", "--"),   # em-dash → double hyphen
    ("–", "-"),    # en-dash → hyphen
    ("‘", "'"),    # left single quote → apostrophe
    ("’", "'"),    # right single quote → apostrophe
    ("“", '"'),    # left double quote
    ("”", '"'),    # right double quote
    (" ", " "),    # non-breaking space → regular space
    ("​", ""),     # zero-width space → removed
    ("‌", ""),     # zero-width non-joiner → removed
    ("﻿", ""),     # BOM → removed
]
```

**Stratégie :** masquer `<style>` et `<script>` avant normalisation, restaurer après — évite de corrompre les règles CSS.

**Application :** dans `generate_pdf()`, entre `render_html()` et `HTML(string=...).write_pdf()`.

Même normalisation appliquée dans `generate_cover_letter.py` et `generate_prep_sheet.py`.

---

## Groupe 3 — Liveness check (`scripts/liveness.py`)

**Problème :** `import_offers.py` importe des offres sans vérifier si elles sont encore actives. Des postings fermés entrent en DB, consomment des ressources de scoring et polluent le tracker.

**Solution :** nouveau module `scripts/liveness.py`, HTTP-first (httpx déjà dans requirements), zero browser, zero LLM.

### Interface publique

```python
def check_liveness(url: str, *, timeout: int = 15) -> tuple[str, str]:
    """Check if a job URL is still active.
    
    Returns (status, reason) where status is:
    - "active"    — offer is open
    - "expired"   — offer is definitively closed
    - "uncertain" — could not determine (network error, timeout, etc.)
    """
```

### Stratégie de détection (ordre)

1. **Validation URL** — URL vide ou non-HTTP → `("uncertain", "no_url")`
2. **HEAD request** (timeout 8s) — status 404/410 → `("expired", "http_404")` ou `"http_410"`
3. **URL patterns** — URL contient `expired`, `not-found`, `error=`, `closed` → `("expired", "url_pattern")`
4. **GET request** (timeout 15s, max 50KB via `stream`) — analyse le corps :
   - Patterns FR : `"offre expirée"`, `"offre pourvue"`, `"poste pourvu"`, `"ce poste n'est plus disponible"`, `"cette offre a expiré"`
   - Patterns EN : `"job no longer available"`, `"position has been filled"`, `"this job has expired"`, `"job has been removed"`, `"no longer accepting"`
   - Match → `("expired", "body_pattern:<pattern>")`
5. **Status 2xx + aucun pattern** → `("active", "ok")`
6. **Toute exception réseau** (timeout, connexion refusée, SSL, redirect infini) → `("uncertain", "network_error")` — **jamais `expired` sur erreur réseau**

### Intégration dans `import_offers.py`

Nouveau flag `--check-liveness` (opt-in, désactivé par défaut) :
- `active` → importé normalement
- `expired` → skippé, compté dans `skipped_expired`
- `uncertain` → importé normalement (comportement conservateur)

Output avec `--dry-run --check-liveness` :
```
[expired] REDOPUS / Network Engineer Lead Expert — http_404
[active]  Mistral AI / AI Engineer — ok
```

---

## Tests

### `tests/test_pre_filter.py` — nouveaux tests dans `TestNewSignals`

| Test | Assertion |
|------|-----------|
| `test_salary_13th_month` | desc "43k + 13e mois" → package ~46.9k → dans cible → +0.5 |
| `test_salary_with_rtr_tr` | desc "40k + 10 RTT + TR" → package ~42.4k → +0.5 |
| `test_salary_out_of_range_penalty` | desc "80k" → -0.3 |
| `test_salary_no_info_neutral` | desc sans salaire → 0.0 |
| `test_legitimacy_thin_description` | desc < 300 chars → -0.5 pénalité |
| `test_legitimacy_no_tech` | desc longue mais 0 skills → -0.3 |
| `test_legitimacy_tag_suspicious` | pénalité ≥ 0.3 → tag `legitimacy:suspicious` |

### `tests/test_liveness.py` — nouveau fichier

| Test | Assertion |
|------|-----------|
| `test_404_returns_expired` | mock HTTP 404 → `("expired", "http_404")` |
| `test_410_returns_expired` | mock HTTP 410 → `("expired", "http_410")` |
| `test_body_pattern_fr` | body contient "offre expirée" → `("expired", "body_pattern:...")` |
| `test_body_pattern_en` | body contient "job no longer available" → `("expired", ...)` |
| `test_200_no_pattern_active` | status 200, body propre → `("active", "ok")` |
| `test_network_error_uncertain` | ConnectError → `("uncertain", "network_error")` |
| `test_empty_url_uncertain` | url="" → `("uncertain", "no_url")` |

### `tests/test_generate_pdf.py` — tests ATS normalisation

| Test | Assertion |
|------|-----------|
| `test_normalize_em_dash` | `"foo—bar"` → `"foo--bar"` |
| `test_normalize_smart_quotes` | `"“foo”"` → `'"foo"'` |
| `test_normalize_zero_width` | `"foo​bar"` → `"foobar"` |
| `test_style_block_preserved` | `<style>.em { }` non modifié |

---

## Out of scope

- Liveness check via Playwright (Indeed + APEC derrière Cloudflare) — complexité trop élevée pour le gain, `uncertain` suffit
- Stockage de `salary_normalized` comme colonne DB — calculé à la volée au scoring, pas besoin de persister
- Ancienneté de l'offre > 90j — `detection_date` est la date d'import, pas de publication
- Normalisation Unicode dans les templates HTML Jinja2 (templates sont contrôlés)
