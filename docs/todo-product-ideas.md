# Diggo — Idées d'améliorations (backend, onboarding, LLM, divers)

Date : 2026-07-08
Contexte : rédigé pendant la migration frontend vers Next.js. Ce sont des pistes à évaluer, pas un plan engagé — chaque item mérite son propre brainstorm avant implémentation.

Voir aussi [docs/todo-deployment.md](todo-deployment.md) (audit du 2026-07-03) : une partie est maintenant faite (auth Supabase, multi-tenant Postgres, settings/profil par user — Groupes 0 et 5), le reste (sécurité/RGPD Groupe 6, scraping à l'échelle Groupe 3) reste ouvert et pertinent — à ne pas dupliquer, juste à prioriser après la refonte frontend.

---

## 1. Backend — changement de framework ou de langage

**État actuel** : Python 3.13, FastAPI (routes majoritairement sync), `psycopg2` sync, WeasyPrint pour les PDFs, Playwright pour le scraping Indeed.

**Options** :
- **Rester en Python, passer full async** — `asyncpg` ou `psycopg3` async + routes FastAPI async partout. Risque faible, gain de perf réel sur les endpoints qui touchent la DB, pas de réécriture logique métier.
- **Changer de framework Python** (Litestar, Django) — Litestar a une forme proche de FastAPI, parfois plus rapide ; Django apporte un admin panel et des outils RGPD (export/suppression de compte) prêts à l'emploi, mais implique une réécriture complète.
- **Changer de langage (Go)** — bien meilleur pour la concurrence des scans/scraping et l'empreinte mémoire, mais WeasyPrint (génération PDF) est Python-only : il faudrait retrouver une solution PDF en Go (Chrome headless piloté, ou service PDF séparé).
- **Node/TypeScript** — cohérent avec le frontend Next.js déjà choisi ; possibilité à terme de fusionner `api`+`web` en une seule app Next.js (API routes/Server Actions), ce qui supprimerait le besoin du reverse proxy actuel. Même problème PDF : remplacer WeasyPrint par Puppeteer/Playwright PDF.

**Recommandation** : ne pas réécrire le backend pour l'instant — le vrai verrou n'est pas FastAPI, c'est le pipeline scraping/PDF qui est Python-spécifique (WeasyPrint, Playwright). Si un changement de langage est vraiment voulu, faire d'abord un spike isolé sur la génération PDF dans le langage cible avant de trancher.

---

## 2. Parcours d'inscription — import CV / LinkedIn

- **Import CV** : à l'inscription, upload PDF/DOCX → extraction du texte → un appel LLM (le pipeline existe déjà dans `dashboard/llm.py`) transforme le texte en JSON structuré correspondant au schéma CV actuel (`user_data.py`, tables CV) → écran de relecture/édition avant sauvegarde (ne jamais enregistrer le parsing brut sans validation humaine) → fallback "pas de CV, je remplis à la main" toujours disponible.
- **Import LinkedIn** — deux niveaux :
  - **(a) Export PDF LinkedIn → même pipeline que l'import CV.** Zéro dépendance à l'API LinkedIn, marche dès aujourd'hui.
  - **(b) "Se connecter avec LinkedIn" (OAuth + Profile API)** — l'accès officiel à l'export de profil personnel via l'API LinkedIn est très restreint depuis ~2018 (accès partenaire, validation longue). Effort et incertitude d'approbation nettement plus élevés que ce que le nom suggère.
  - Recommandation : commencer par (a), ne considérer (b) que si la demande utilisateur le justifie.

---

## 3. Connecter d'autres LLM

**État actuel (vérifié dans le code)** : `dashboard/llm.py` code en dur Hugging Face Inference Providers comme unique fournisseur (`_HF_MODEL = "openai/gpt-oss-120b:fastest"`, client OpenAI SDK pointé sur `router.huggingface.co`). Chaque utilisateur apporte déjà son propre token HF (`/settings`, `validate_hf_token` déjà en place).

Comme l'appel passe déjà par un client au format OpenAI-compatible, ajouter un autre fournisseur revient surtout à :
- extraire une petite abstraction (`call_llm(prompt, provider, api_key)` → route vers le bon `base_url`/modèle selon le provider),
- laisser l'utilisateur choisir son provider dans `/settings` (token HF, clé OpenAI, clé Anthropic, clé Groq...),
- garder le modèle "bring your own key" déjà en place plutôt que de centraliser la facture LLM sur le compte Diggo — cohérent avec l'architecture actuelle, évite que le service absorbe le coût d'inférence de tous les utilisateurs.

---

## 4. Autres idées (non demandées, mais qui valent le coup d'œil)

- **CI/CD** : il n'existe **aucun** pipeline GitHub Actions aujourd'hui (`.github/workflows/` absent). Minimum : lancer `pytest` + typecheck/lint frontend à chaque PR. Vu la taille actuelle du repo (backend + frontend + Docker), c'est probablement l'investissement infra le plus rentable à court terme.
- **Observabilité** : pas de tracking d'erreurs (Sentry ou équivalent) ni de logging structuré visible — pour un service public multi-utilisateur, une exception non gérée aujourd'hui est silencieuse.
- **Notifications email** : rappel automatique pour les candidatures "Envoyée" en retard de relance (la bannière ambre existe déjà dans le dashboard — un digest email prolongerait ça hors de l'onglet navigateur).
- **Détection auto des réponses** : intégration Gmail/IMAP pour détecter une réponse recruteur et avancer automatiquement le statut. Ambitieux, forte valeur, mais sensible côté vie privée — à cadrer avec soin.
- **Scoring plus intelligent** : le scoring actuel est basé sur des règles (mots-clés/signaux de description). Un score de matching assisté par LLM ou par embeddings contre le profil réel de l'utilisateur réduirait les faux positifs/négatifs, mais ajoute un coût par offre scannée — à modéliser vu l'architecture "bring your own LLM key".
- **Extension navigateur** : bouton "sauvegarder cette offre dans Diggo" pour les portails mal couverts par le scraper (WTTJ authentifié, Indeed anti-bot) — contourne la fragilité du scraping pour ces cas-là.
- **Partage/coaching** : pas de besoin identifié aujourd'hui (toujours un compte = un utilisateur), mais si l'audience "cadres" grandit, une vue coach/mentor (lien en lecture seule vers le pipeline d'un candidat) pourrait être un différenciateur — spéculatif, aucun signal utilisateur pour l'instant.
- **PWA/mobile** : cohérent avec la décision déjà prise ("vraiment responsive / mobile important") — un manifest PWA (installable, tolérant au offline) est une étape additive légère une fois la migration Next.js terminée sur toutes les pages.
- **Tests frontend** : aucune suite Playwright/Vitest n'existe encore pour `frontend/` — à ajouter au fur et à mesure que les pages arrivent, pour que les régressions de la refonte soient détectées automatiquement plutôt qu'à l'œil.
