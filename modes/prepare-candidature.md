# prepare-candidature

Generate tailored CV PDF, cover letter PDF, and interview prep sheet PDF for a specific offer.

## Input

Called with:
```bash
claude --system-prompt "$(cat modes/prepare-candidature.md)" "Prépare la candidature pour l'offre ID <id>"
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
- `keywords`: tech/domain terms to mirror in CV summary and cover letter
- `company_context`: mission, product, estimated size, tech stack mentioned
- `gaps`: skills in the offer not present in `config/profile.md` (to omit from CV, never invent)
- `hook_angle`: one concrete "why this company" angle (product, mission, specific tech — not generic)

### Phase 3 — Generate CV

**Language rule:** The CV is always generated in French, regardless of the offer language. Exception: only generate an English CV if the offer explicitly requires it (e.g. "CV in English required", "Please submit your resume in English").

1. Select `highlighted_skills` from `config/profile.md` that match `top_skills` exactly (no invention)
2. Rewrite the 2-sentence summary to mirror the offer's language (role title, key domain) — in French
3. Run:
   ```bash
   python scripts/generate_pdf.py \
     --offer "<slug>" \
     --date "<YYYY-MM-DD>" \
     --highlighted <skill1> <skill2> ...
   ```
   Note the output path printed.

### Phase 4 — Generate cover letter

**MANDATORY grounding step before writing — do not skip.**

Build this table for every claim you plan to make:

| Claim envisaged | Exact source in profile.md | Section |
|-----------------|----------------------------|---------|
| e.g. "j'ai déployé des pipelines RAG" | ? | |

Rules:
- A claim is allowed ONLY if its source is in the **Experience** section of `config/profile.md` (a job or internship with explicit dates).
- Skills listed in the **Skills** section but annotated `[personal study]`, `[self-training]`, or `[not yet deployed in production]` are FORBIDDEN in the cover letter — they may appear in the CV skills list but never as claimed professional accomplishments.
- Skills listed in the **Personal Projects** section may only be mentioned as personal projects, never as professional experience.
- If fewer than 2 verifiable claims exist for the top requirements, say so explicitly rather than inventing.

1. Write 3 paragraphs (< 300 words total, in the language of the job posting):
   - Para 1 (hook): one concrete reason tied to `hook_angle` — never "Je suis passionné par l'IA"
   - Para 2 (proof): 2 specific experiences from the **Experience** section of `config/profile.md` — each backed by a row in the grounding table above
   - Para 3 (close): confident close. ALWAYS include one sentence about the career pivot (mandatory): adapt wording to letter language. EN: "A deliberate pivot — eight years leading a sales team, then retraining as an AI engineer — means I bring both technical depth and the communication skills to work directly with non-technical stakeholders." FR: "Une reconversion délibérée — 8 ans à manager une équipe commerciale, puis formation en AI engineering — me permet d'allier profondeur technique et capacité à travailler avec des interlocuteurs non techniques." Then mention availability (fin 2026 / dès que possible).
2. Never use: "Je suis très motivé", "passionné par", "je me permets de", "dans l'espoir de"
3. Build `/tmp/cl-context-<slug>.json`:
   ```json
   {
     "company": "<company>",
     "role": "<role>",
     "recipient": "Madame, Monsieur,",
     "date_str": "<YYYY-MM-DD>",
     "paragraphs": ["<p1>", "<p2>", "<p3>"]
   }
   ```
4. Run:
   ```bash
   python scripts/generate_cover_letter.py \
     --offer "<slug>" \
     --date "<YYYY-MM-DD>" \
     --context-file /tmp/cl-context-<slug>.json
   ```
   Note the output path printed.

### Phase 5 — Generate prep sheet

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
   Aim for 8–12 questions covering: technical depth (linked to top_skills), MLOps/deployment, behavioural (STAR format expected), and "why us / why this role".
2. Run:
   ```bash
   python scripts/generate_prep_sheet.py \
     --offer "<slug>" \
     --date "<YYYY-MM-DD>" \
     --context-file /tmp/prep-context-<slug>.json
   ```
   Note the output path printed.

### Phase 6 — Update DB and summarise

Run:
```bash
sqlite3 dashboard/data/applications.db \
  "UPDATE applications SET cv_path='<cv_path>', cover_letter_path='<cl_path>' WHERE id=<offer_id>;"
```

Print:
```
✅ Candidature prête — <company> / <role>

CV:             output/<slug>-<date>/cv-<slug>-<date>.pdf
LM:             output/<slug>-<date>/cover-letter-<slug>-<date>.pdf
Fiche révision: output/<slug>-<date>/prep-sheet-<slug>-<date>.pdf

Ouvre les 3 PDFs et vérifie avant d'envoyer.
```

## Constraints

- Never add skills not present in `config/profile.md`
- Never change dates or job titles in the CV
- CV must stay 1 page
- Cover letter max 300 words
- Prep sheet: 8–12 questions minimum
