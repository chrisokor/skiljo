# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status: bootstrapping Week 1 of 6 (no committed code yet)

The project is mid-bootstrap. `git init -b main` has been run and `.gitignore`, `LICENSE`, `README.md` (placeholder), and the root `pyproject.toml` exist on disk, but **nothing is committed yet** (`git log` is empty) and there is no GitHub remote. `src/` and `tst/` at the repo root are stale placeholder directories from before the design was finalized — ignore them; per the build plan, real code lands under `packages/<name>/src/` and `packages/<name>/tests/`, not at the repo root.

Implementation is driven by a spec → plan workflow under `docs/superpowers/`:
- `docs/superpowers/specs/2026-06-20-week1-foundations-design.md` — scopes Week 1 (commits 1–13 of `docs/DESIGN_DOCUMENT.md` §12) as its own sub-project; later weeks (extraction pipeline, simulation engine, demo/SDK, eval expansion, deploy) get their own future spec.
- `docs/superpowers/plans/2026-06-21-week1-foundations.md` — the atomic, commit-by-commit task breakdown for Week 1, meant to be executed with the `superpowers:subagent-driven-development` or `superpowers:executing-plans` skill. Each of its 13 tasks ends in one conventional commit; check this file's checkboxes to see what's actually done versus still pending before assuming a command (e.g. `make api`, `uv sync`) will work.

The original product/business docs remain the spec for everything beyond Week 1:
- `docs/DESIGN_DOCUMENT.md` — technical design: architecture, data model, API surface, and the full week-by-week build plan with ~63 atomic commits (Sections 11–12). Read this (and the current week's plan/spec above) before writing any code.
- `docs/BRD.md` — business requirements: problem, ICP, MVP scope, pricing, GTM, success metrics.
- `docs/PRFAQ.md` — press release / FAQ framing of the product.
- `docs/POLICY_CORPUS.md` — 14 real-world refund/billing policies (Stripe, AWS, OpenAI, Twilio, Vercel, Notion, Shopify, Steam) used as extraction/eval fixtures.

The product name is **Skiljo** (single L) — matches the directory name, the domain (skiljo.ai), and is used consistently throughout `docs/DESIGN_DOCUMENT.md`, `docs/BRD.md`, `docs/PRFAQ.md`, and `docs/POLICY_CORPUS.md`. The Week 1 spec/plan docs and README briefly drifted to a "Skilljo" double-L misspelling; that's been corrected — double-check new file, package, or repo names against this spelling.

## What Skiljo does

Skiljo converts a company's refund/credit/billing policy documents and historical ticket behavior into versioned, machine-executable **Skills** — structured workflow specs an AI agent can run safely. The MVP's sellable output is *not* live automation; it's a historical simulation report plus a "policy vs. practice" contradiction report (where written policy and actual behavior diverge).

## Planned architecture (docs/DESIGN_DOCUMENT.md)

Python monorepo (`uv` workspace: `packages/core`, `packages/api`, `packages/demo`) + TypeScript SDK (`pnpm` workspace: `packages/sdk-ts`):
- **FastAPI** backend (`packages/api`) — REST API, async jobs via `BackgroundTasks`; Week 1 only adds a `/health` route
- **Streamlit** demo UI (`packages/demo`) — 3 pages: extract, review, simulate (content lands Week 4)
- **Postgres 16** via Docker Compose — 8 tables: `policies`, `skills`, `skill_versions`, `simulation_runs`, `simulation_results`, `llm_calls`, `jobs`, `eval_runs`; managed with SQLAlchemy 2.x models + Alembic migrations in `packages/core`
- **LLM client** — abstraction over Anthropic (tool-use for structured output, retry-with-validation-feedback up to 3x), every call logged; not built until Week 2
- **Eval harness** — built on Inspect, gates CI on regression; not built until Week 5
- **TypeScript SDK** (`packages/sdk-ts`) — thin typed client generated from JSON Schema (Zod), mirrors the Pydantic models

`schemas/` holds the canonical JSON Schemas (`skill.schema.json`, `rule.schema.json`, `ticket.schema.json`, `simulation_report.schema.json`) — the single source of truth for types. `schemas/codegen/generate_pydantic.py` and `schemas/codegen/generate_zod.ts` regenerate Pydantic models (into `packages/core/src/skiljo_core/schemas/`) and Zod schemas (into `packages/sdk-ts/src/types.ts`) respectively; both outputs are committed deliberately so diffs are visible in review.

Core abstractions:
- **Skill** — versioned, immutable workflow spec with three decision zones: *deterministic* (mechanical rules), *LLM-assisted* (interpretation + required human approval), *human-only* (escalation)
- **Predicate DSL** — constrained rule language (`all`/`any` composition, fixed operators: `eq, neq, lt, lte, gt, gte, in, not_in, contains, empty, not_empty`) — chosen over JSONLogic/Python `eval`/CEL specifically for auditability and reliable LLM generation
- **Extraction pipeline** — 4 LLM passes: segment policy text → extract rules per segment → classify decision zone → assemble + validate spec (repair loop on schema failure, up to 2 retries)
- **Simulation engine** — replays a Skill against historical Tickets (deterministic rules first, then LLM-assisted, then escalate); aggregates match rate, escalation accuracy, and detects systematic Contradictions (≥5% deviation frequency)

## System invariants (non-negotiable per design doc)

1. Every LLM call is logged to `llm_calls` (model, prompt_version, inputs, outputs, latency, cost) — this is the primary observability surface, there is no Datadog/Honeycomb in MVP.
2. Skill specs are immutable once persisted — amendments always create a new `skill_versions` row (with `parent_version_id`), never an update.
3. The eval harness runs in CI on every PR and blocks merge on regression: extraction recall ≤2pt drop, simulation match rate ≤3pt drop, end-to-end accuracy ≤3pt drop.

## Commands

Most of these don't work yet — `packages/`, `package.json`, `pnpm-workspace.yaml`, and the `Makefile` don't exist on disk until later tasks in the Week 1 plan run. Check `docs/superpowers/plans/2026-06-21-week1-foundations.md` for what's actually been completed. Once Week 1 is finished, the Week 1 Makefile (Task 5) exposes:

```bash
docker compose up -d postgres   # Postgres 16
uv sync                          # Python deps (uv workspace)
pnpm install                     # TypeScript SDK deps
make codegen                     # JSON Schema -> Pydantic + Zod types
make migrate                     # Alembic migrations
make api                         # FastAPI on :8000
make demo                        # Streamlit on :8501 (functional from Week 4)
make test                        # pytest + vitest, repo-wide
make lint                        # ruff
make typecheck                   # mypy + tsc
```

A single test: `uv run pytest packages/api/tests/test_health.py -v` (Python) or `pnpm --filter @skiljo/sdk test` (TypeScript SDK — `vitest`).

`make eval-extraction` / `make eval-simulation` / `make eval-e2e` (per `docs/DESIGN_DOCUMENT.md` Appendix C) are **not** part of the Week 1 Makefile — they're added with the eval harness in a later week.

## Conventions to follow once code exists

- Commit format: `<type>(<scope>): <summary>` — types: `feat, chore, docs, test, fix, refactor, data`. Keep the message to that single line — no `Co-Authored-By` trailer, no body.
- `schemas/` (JSON Schema) is the single source of truth for types — run `make codegen` after any schema edit and commit the generated Pydantic/Zod output alongside it
- Follow the commit-by-commit build order in `docs/DESIGN_DOCUMENT.md` Section 12 (scoped week-by-week in `docs/superpowers/plans/`) rather than improvising project structure — it's designed so every commit leaves the repo in a working, CI-passing state
