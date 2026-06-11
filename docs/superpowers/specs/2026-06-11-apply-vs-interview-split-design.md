# Design — Séparation candidature / entretien

**Date:** 2026-06-11
**Scope:** `templates/partials/offer_detail.html`, `modes/prepare-candidature.md`, `modes/prepare-entretien.md` (new)

## Contexte

Le bouton "Préparer candidature" génère actuellement CV + LM + fiche prep en une seule commande,
quel que soit le statut de l'offre. Deux problèmes identifiés :

1. Beaucoup de sites ne demandent pas de lettre de motivation — la générer systématiquement est du gaspillage.
2. La fiche prep d'entretien n'a de valeur qu'après sélection du CV (statut Entretien RH ou tech).

## Logique conditionnelle des boutons

Les boutons d'action dans la colonne gauche du panneau varient selon le statut de l'offre.

### Groupes de statuts

| Groupe | Statuts |
|--------|---------|
| `APPLY_STATUSES` | À envoyer, Envoyée, Relance |
| `INTERVIEW_STATUSES` | Entretien RH, Entretien tech, Offre |
| Terminaux | Acceptée, Refusée, Abandonnée |

### Comportement par groupe

**APPLY_STATUSES :**
- Checkbox "Inclure lettre de motivation" — décochée par défaut, état géré en JS (non persisté en DB)
- Bouton "✦ Préparer candidature" :
  - Sans LM → commande `generate-cv.md` (CV uniquement)
  - Avec LM → commande `prepare-candidature.md --no-prep` (CV + LM, sans fiche prep)

**INTERVIEW_STATUSES :**
- Bouton "✦ Préparer entretien" à la place du bouton candidature (+ checkbox disparaît)
- Commande `prepare-entretien.md` (fiche prep uniquement)

**Terminaux :**
- Aucun des deux boutons n'apparaît.

## Modes CLI

### `prepare-candidature.md` — ajout flag `--no-prep`

Ajout d'une règle en haut de la section Instructions :

> Si le message utilisateur contient `--no-prep`, sauter entièrement la Phase 5 (génération fiche prep).
> Mettre à jour la DB avec `cv_path` et `cover_letter_path` uniquement.

### `prepare-entretien.md` — nouveau fichier

Structure :
- **Phase 1** — Charger contexte offre (identique à `prepare-candidature.md`)
- **Phase 2** — Analyser l'offre (identique à `prepare-candidature.md`)
- **Phase 5** — Générer la fiche prep (identique à `prepare-candidature.md`)
- **Phase 6** — Résumé sans mise à jour `cv_path` / `cover_letter_path` en DB

### `generate-cv.md` — inchangé

Utilisé tel quel pour la commande "CV uniquement".

## Changements fichiers

| Fichier | Changement |
|---------|-----------|
| `templates/partials/offer_detail.html` | Bloc action buttons conditionnel Jinja2 + checkbox + JS dynamique |
| `modes/prepare-candidature.md` | Ajout règle `--no-prep` en tête de section Instructions |
| `modes/prepare-entretien.md` | Nouveau fichier (fiche prep uniquement) |
| `app.py` | Aucun |
| `db.py` | Aucun |
| Scripts Python | Aucun |

## Contraintes

- La checkbox n'est pas persistée en DB — état JS local, se réinitialise au rechargement.
- La commande copiée dans le presse-papiers doit toujours être prête à coller dans le terminal sans édition.
- Aucune nouvelle route FastAPI nécessaire.
