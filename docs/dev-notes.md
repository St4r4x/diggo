# Dev Notes

Feature-by-feature status: what works, what's missing, known limits.

---

## Filtre de localisation

**Status : fonctionnel pour les nouveaux scans**

`pre_filter()` rejette les offres dont la localisation ne contient pas la valeur de `search.location` (settings.yaml) avant le scoring. Passe si vide, remote/hybride/télétravail, ou substring match insensible à la casse.

Fonctionne pour n'importe quelle ville — pas hardcodé Paris.

**Limites :**

- La colonne `location` n'existe pas dans `applications`. Les offres déjà en BDD ne sont pas refiltrables rétroactivement. Pour corriger : ajouter `location TEXT NOT NULL DEFAULT ''` via `_migrate()` et la peupler à l'import.
- Portails Playwright (APEC, WTTJ, LinkedIn, Glassdoor) : le format extrait par le sélecteur CSS n'a pas été vérifié empiriquement sur tous les portails. Le substring match couvre les formats courants (`"Paris"`, `"Paris (75)"`, `"Île-de-France"`), mais un format inattendu passerait silencieusement.
- Greenhouse multi-site : certaines offres ont une location composée (`"France, Paris; United States, New York"`). Le filtre laisse passer dès que la ville cible est présente — comportement correct.

---

## Retry ATS

**Status : en place**

`_fetch_with_retry()` dans `scan_ats.py` : 3 tentatives, backoff [1s, 2s, 4s], timeout 10s. Les 4xx (sauf 429) ne sont pas retentées. Appliqué aux 5 call sites Greenhouse/Lever/Ashby.

---

## Timeout description portails

**Status : en place**

`_enrich()` dans `scan_portals.py` wrappe `_fetch_description` dans `asyncio.wait_for(timeout=15.0)`. Les offres dont la page détail ne répond pas obtiennent une description vide.

**Limite :** Playwright a ses propres timeouts internes (20s `goto` + 10s `wait_for_selector`) qui absorbent la plupart des hangs avant que le `wait_for` extérieur déclenche. Ce dernier ne protège que contre un freeze complet du processus Playwright.

---

## Rescoring

**Status : script disponible, non intégré au dashboard**

`scripts/rescore.py` recalcule `score_value` et `score_grade` pour toutes les offres en BDD avec le scorer actuel.

```bash
python -m scripts.rescore --dry-run   # prévisualisation
python -m scripts.rescore             # application
```

À relancer manuellement après un changement de `config/settings.yaml` (seuils, salaires cibles, entreprises cibles).

**À faire :** bouton "Recalculer les scores" dans le dashboard.

---

## Indeed

**Status : désactivé**

Indeed bloque les requêtes Playwright sans proxy résidentiel. Le portail est présent dans `portals/fr/indeed.yaml` mais ne produit aucune offre en pratique.

**À faire :** réactiver quand une solution proxy est disponible.

---

## Backfill descriptions

**Status : script autonome, non intégré**

`scripts/backfill_descriptions.py` peuple les descriptions manquantes via Playwright pour les offres déjà en BDD. Non déclenché automatiquement.

---

## Pagination dashboard

**Status : non implémentée**

La vue liste charge toutes les offres en une seule requête SQL. À surveiller si le volume dépasse quelques centaines d'offres.
