# career-ops-fr — Claude Code instructions

## Documentation maintenance

**CHANGELOG.md and README.md must be kept up to date. This is mandatory, not optional.**

### When to update CHANGELOG.md

Update `CHANGELOG.md` before every commit that touches source code. The only exception is pure documentation commits (changelog/README edits only) — mark those `[skip ci]`.

**What to log:**

| Change type | Log it? |
|-------------|---------|
| New feature, script, route, template | Yes — under `### Added` |
| Behaviour change, refactor, renamed symbol | Yes — under `### Changed` |
| Bug fix | Yes — under `### Fixed` |
| Dependency added/removed/upgraded | Yes — under `### Changed` |
| Test-only commit | No |
| Comment or whitespace fix | No |

**Format:** add entries under `## [Unreleased]` at the top. Use today's date (`YYYY-MM-DD`) when the section is first written for a day. Be specific — name the file, the function, and what changed. One bullet per logical change.

```markdown
## [Unreleased]

## 2026-06-01

### Added
- `scripts/foo.py` — describe what it does and why

### Changed
- `dashboard/app.py` — describe what changed and why

### Fixed
- `dashboard/profile_parser.py` — describe the bug and fix
```

### Commit checklist — never skip

Before every commit that touches source code:
1. Update `CHANGELOG.md` under `## [Unreleased]` (or today's date section)
2. Update `README.md` if the public interface changed (new script, route, config, Docker step)
3. Run `pytest` and confirm all tests pass

**The CHANGELOG update must be in the same commit as the code change — not a follow-up commit.**

### When to update README.md

Update `README.md` when any of these change:

- A new script is added to `scripts/` → add it to the project structure table
- A new dashboard route is added → add it to the Dashboard pages table
- A new scraping platform or strategy is added → update the description fetching table
- A new Claude Code mode is added → update the modes section
- A new config file is introduced → add it to the Configuration table
- The Docker workflow changes → update the Docker section
- Setup steps change (new env var, new dependency) → update Quick start

Do **not** update the README for internal refactors that don't change the public interface or usage.

## Project conventions

### Git
- Commits in English, imperative mood, conventional commits prefix: `feat|fix|docs|chore|refactor|test|ci|style`
- Subject line max 72 chars, no trailing period
- Append `[skip ci]` only on zero-code commits (changelog-only edits, doc typos)
- SSH host: `github.com-personal` (personal repo)

### Python
- Type hints on all function signatures
- `pathlib.Path` over `os.path`
- f-strings over `.format()`
- Never bare `except:` — always specify the exception type
- Import order: stdlib → third-party → local, alphabetical within groups

### Testing
- Run `pytest` from repo root before committing
- Test files mirror source structure: `tests/test_<module>.py`
- Use fixtures for shared setup; monkeypatch `profile_parser._PROFILE_MD` / `_CONTACT_YAML` in profile tests

### Dashboard
- HTMX partials live in `dashboard/templates/partials/`
- Full pages use `base.html` layout with `{% block content %}`
- Active nav state via `request.url.path` comparison in Jinja2

### File deletion
- Use `gio trash <path>` instead of `rm -rf`

### Virtual environment
- Always use `.venv` at repo root — never install to system Python

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
