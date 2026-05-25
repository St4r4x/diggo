# generate-cover-letter

Write a tailored cover letter for a specific job offer. Called from Claude Code CLI.

## Input

- Job description (pasted) or score report path
- Company name and role title

## Instructions

1. Read `config/profile.md` for Arnaud's background and tone.
2. Read the job description / score report to identify:
   - What the company builds / its mission
   - The 2–3 most important technical requirements
   - Any specific "why us" angle (tech, mission, product, team)
3. Write the cover letter in the language of the job posting (French if French, English if English).
4. Structure: 3 short paragraphs, < 300 words total:
   - **Para 1 (hook):** Why this company specifically — one concrete reason tied to their product or mission. No generic "Je suis passionné par l'IA".
   - **Para 2 (proof):** 2 specific experiences from profile.md that directly address the top 2 requirements. Use numbers or outcomes where possible.
   - **Para 3 (close):** Short, confident close. Mention availability (fin 2026 / dès que possible).
5. Tone: direct, professional, no filler phrases ("Je suis motivé", "passionné", etc.)
6. Save the draft text to `output/<company-slug>-<date>/cover-letter.md` for reference.
7. Build a JSON context file at `/tmp/cl-context.json`:

```json
{
  "company": "<company name>",
  "role": "<role title>",
  "recipient": "Madame, Monsieur,",
  "date_str": "<YYYY-MM-DD>",
  "paragraphs": [
    "<paragraph 1 text>",
    "<paragraph 2 text>",
    "<paragraph 3 text>"
  ]
}
```

8. Generate the PDF:

```bash
python scripts/generate_cover_letter.py \
  --offer "<company-slug>" \
  --date "<YYYY-MM-DD>" \
  --context-file /tmp/cl-context.json
```

9. Confirm: `Cover letter generated: output/cover-letter-<slug>-<date>.pdf`
   Remind the user to open and visually verify the PDF before sending.

## Constraints

- Never mention skills not in `config/profile.md`
- Never use: "Je suis très motivé", "passionné par", "je me permets de", "dans l'espoir de"
- Max 300 words
- Must cite at least one specific project from profile.md by name
