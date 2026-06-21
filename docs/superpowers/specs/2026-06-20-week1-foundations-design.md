# Design: Week 1 — Foundations (Skiljo monorepo bootstrap)

## Context

Skiljo is a fully-specified, pre-implementation portfolio project. `docs/DESIGN_DOCUMENT.md` already contains a complete architecture, data model, and a week-by-week build plan broken into atomic commits `(~11–12). This spec does not redesign anything — it scopes the **first** sub-project ("Week 1 — Foundations") for implementation and records the operational decisions needed to start, since the rest of the 6-week plan (extraction pipeline, simulation engine, demo UI/SDK, eval expansion, deployment) are separate sub-projects with their own future spec → plan → implementation cycles.

Source of truth for everything technical below: `docs/DESIGN_DOCUMENT.md` §11 "Week 1 — Foundations" and §12 "Commit-level breakdown → Week 1" (commits 1–13). Read those sections directly for full detail; this doc summarizes scope and the decisions made to fill gaps the design doc doesn't cover (tooling install, git/GitHub setup).

## Scope

Implement commits 1–13 from `docs/DESIGN_DOCUMENT.md` §12, each as its own atomic, working, conventional-commit-formatted git commit:

1. `chore: initialize repo with uv workspaces and pnpm workspace`
2. `chore: add Python package skeletons (core, api, demo)`
3. `chore: add TypeScript SDK skeleton`
4. `chore: docker-compose with Postgres 16`
5. `chore: Makefile with common dev tasks`
6. `feat(schemas): define skill.schema.json and rule.schema.json`
7. `feat(schemas): define ticket.schema.json and simulation_report.schema.json`
8. `feat(schemas): Pydantic codegen via datamodel-code-generator`
9. `feat(schemas): Zod codegen via json-schema-to-zod`
10. `feat(api): FastAPI skeleton with /health endpoint`
11. `feat(db): SQLAlchemy models and Alembic setup`
12. `chore: GitHub Actions CI for lint, typecheck, test`
13. `docs: README with architecture overview and setup instructions`

Each commit's acceptance criterion (quoted in the design doc) is the test for that commit — e.g. `uv sync && pnpm install` run cleanly, `make api` + `curl localhost:8000/health` returns 200, `make migrate` applies cleanly against the Docker Postgres, CI passes on a clean main branch on GitHub.

**Out of scope:** anything from Week 2 onward — Anthropic LLM client, extraction pipeline, simulation engine, Streamlit page content beyond what's needed to exist as an empty package, eval harness. Those get their own spec when we get there.

## Operational decisions (not covered by the design doc)

- **Python version:** the design doc targets Python 3.12; the system default is 3.13.5. Pin `requires-python = "3.12.*"` (or equivalent `.python-version`) in the root/package `pyproject.toml` files and let `uv` fetch 3.12 itself rather than relying on system Python.
- **Tooling installed this session:** `uv` and `gh` (GitHub CLI) via Homebrew — neither was present on the machine. `docker`, `node`, `pnpm`, `git` were already present.
- **GitHub:** authenticated `gh` as account `chrisokor`. A new **private** repo `chrisokor/skiljo` will be created and used as the `origin` remote. Commits are pushed as work progresses (not all at the end) so that the GitHub Actions workflow added in commit 12 can actually be verified running on GitHub, satisfying that commit's acceptance criterion.

## Verification

- Each commit's stated acceptance criterion must pass before moving to the next commit.
- After commit 12 is pushed, confirm via `gh run list` / `gh run watch` that the CI workflow run on GitHub is green.
- After commit 13, do a clean-room sanity check: a reader following only the new README should be able to `make setup && make api` successfully (per that commit's acceptance criterion).
