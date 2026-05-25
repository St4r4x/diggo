# score-offer

Score a job offer against Arnaud Thery's profile. Called from Claude Code CLI.

## Input

The user pastes a job description in the conversation.

## Instructions

Read `config/profile.md` and `config/settings.yaml` before scoring.

Score the offer on 9 dimensions. For each dimension, assign a score 0–5 and a short justification (1 line).

| Dimension | Weight |
|-----------|--------|
| Technical relevance (Python, ML, CV, LLM/RAG, Docker match) | 25% |
| Salary (target: 40–55k€, Paris, CDI) | 20% |
| Contract type (CDI=5, CDD=3, freelance=1) | 15% |
| Remote policy (full remote=5, hybrid=4, on-site=2) | 10% |
| Company size & culture (startup energy vs grand groupe) | 10% |
| Tech stack modernity | 8% |
| Career growth potential | 7% |
| Paris location / transit | 3% |
| Company reputation (Glassdoor, LinkedIn presence) | 2% |

**Weighted score formula:** sum(score_i × weight_i)

**Letter grade:**
- A: ≥ 4.5
- B: ≥ 4.0
- C: ≥ 3.5
- D: ≥ 3.0
- F: < 3.0

## Output format

Save report to `reports/<company>-<YYYY-MM-DD>.md` with this structure:

```markdown
# Score Report — <Company> — <Role>
**Date:** YYYY-MM-DD
**Grade:** X  |  **Score:** X.X / 5

## Dimension Scores
| Dimension | Score | Weight | Contribution | Notes |
|-----------|-------|--------|--------------|-------|
| Technical relevance | X/5 | 25% | X.XX | ... |
...
| **TOTAL** | | | **X.XX** | |

## Strengths
- ...

## Weaknesses / Gaps
- ...

## CV Adaptation Suggestions
- Highlight: ...
- De-emphasize: ...
- Skills to surface: ...

## Recommendation
[APPLY / CONSIDER / SKIP] — one sentence justification.
```

If grade is F → do not suggest apply. Print: "Score below threshold (< 3.0) — skipping."
