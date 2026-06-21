# Skiljo

Skiljo extracts a company's refund, credit, and billing-adjustment policies — plus how the team actually handles cases historically — into versioned, executable **Skills**: structured workflow specs an AI agent can run safely, with approval gates and a full audit trail.

The MVP's value isn't live automation. It's a historical simulation report plus a "policy vs. practice" contradiction report: where written policy and actual behavior diverge. See `docs/BRD.md` and `docs/PRFAQ.md` for the product framing, and `docs/DESIGN_DOCUMENT.md` for the full technical design and the 6-week, commit-by-commit build plan this repo follows.

**Status:** Week 1 of 6 complete — foundations only (this commit). No extraction, simulation, or demo UI logic exists yet; see `docs/DESIGN_DOCUMENT.md` §11 for what's planned each week.

## Architecture

A Python monorepo (`core`, `api`, `demo`) plus a TypeScript SDK (`sdk-ts`), with JSON Schema as the single source of truth for data shapes — codegen produces Pydantic models for Python and Zod schemas for TypeScript.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Demo (Python)                      │
│       upload policy → extract skill → review → simulate          │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend (Python)                   │
│  Background tasks via FastAPI BackgroundTasks                    │
│  Job state tracked in Postgres                                   │
└────┬─────────────────────────┬──────────────────┬───────────────┘
     │                         │                  │
     ▼                         ▼                  ▼
┌──────────┐            ┌─────────────┐    ┌────────────────┐
│   LLM    │            │  Postgres   │    │  Eval Harness  │
│  Client  │            │  (8 tables) │    │   (Inspect)    │
└──────────┘            └─────────────┘    └────────────────┘
         ▲                                          ▲
         └────── consumed by ──── TypeScript SDK ───┘
                                  (Zod types from
                                   same JSON Schema)
```

Three invariants hold throughout: every LLM call is logged to `llm_calls`; skill specs are immutable (new versions are new `skill_versions` rows, never updates); the eval harness runs in CI on every PR and blocks merge on regression. Full detail in `docs/DESIGN_DOCUMENT.md` §3.

## Setup

Prerequisites: [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io/), Docker Desktop.

```bash
git clone https://github.com/chrisokor/skiljo.git
cd skiljo
cp .env.example .env
docker compose up -d postgres
make setup
make api
```

`make api` starts the FastAPI server on `localhost:8000` — confirm with `curl localhost:8000/health`.

## Daily dev

```bash
make api         # FastAPI dev server
make demo        # Streamlit demo (functional from Week 4 onward)
make test        # pytest + vitest
make lint        # ruff
make typecheck   # mypy + tsc
make codegen     # regenerate Pydantic/Zod types after a schema change
```

Run `make help` for the full list of targets.

## Repo layout

- `schemas/` — canonical JSON Schemas (source of truth) and the codegen scripts that generate Pydantic/Zod types from them.
- `packages/core/` — extraction, simulation, and storage logic; SQLAlchemy models and Alembic migrations.
- `packages/api/` — FastAPI backend.
- `packages/demo/` — Streamlit demo UI.
- `packages/sdk-ts/` — TypeScript client SDK.
- `docs/` — business requirements, design document, press release/FAQ, and the evaluation policy corpus.

## License

MIT — see `LICENSE`.
