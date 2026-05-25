# generate-cv

Generate a tailored CV PDF for a specific job offer. Called from Claude Code CLI after scoring ≥ 3.0.

## Input

- A score report in `reports/` (from score-offer skill)
- OR: paste the job description directly

## Instructions

1. Read `config/profile.md` (full skill inventory)
2. Read the score report or job description to identify:
   - Top 5–7 required skills mentioned in the offer
   - Keywords to surface (exact terms used in the job posting)
   - Any tech or domain to de-emphasize
3. Build a tailored context for the PDF:
   - `highlighted_skills`: list of skills from profile.md that match the offer keywords exactly
   - `summary`: rewrite the 2-sentence summary to mirror the offer's language (role title, key domain)
   - `experience.bullets`: for the NeuralVision AI/ML Engineer role, reorder bullets to lead with the most relevant ones for this offer. Do NOT invent new bullets.
4. Run the PDF generation script:

```bash
python scripts/generate_pdf.py \
  --offer "<company-slug>" \
  --date "<YYYY-MM-DD>" \
  --highlighted <skill1> <skill2> ...
```

5. Confirm the PDF was created at `output/cv-<company-slug>-<date>.pdf`

## Output

Print: `CV generated: output/cv-<slug>-<date>.pdf`
Remind the user to open and visually verify the PDF before sending.

## Constraints

- Never add skills not present in `config/profile.md`
- Never change dates or job titles
- Keep CV to 1 page
