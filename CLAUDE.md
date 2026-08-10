# CLAUDE.md — Skiljo

Project context for Claude Code. Read this before doing anything in the repo.

## What this project is

Skiljo extracts refund/credit/billing policies from company documents and compiles them into structured, versioned, executable "skill" specifications, then simulates those skills against ticket data to measure policy fidelity and detect contradictions between written policy and actual behavior.

The problem: AI agents fail at company-specific judgment. A support bot can answer "where is my refund?" but can't safely decide whether to issue one, because that requires knowing the company's real decision logic. Skiljo builds the policy-fidelity layer that makes that safe.

This is a real project being built seriously by one developer part-time over summer/fall 2026, with a versioned roadmap (v1.05 → v1.5) if it continues. It is NOT a throwaway demo. Production-quality engineering standards apply.

## Document map

All planning docs live in the repo root (or `docs/planning/` if reorganized):

- **DESIGN_DOCUMENT.md** — the engineering source of truth. Architecture, data model, component design, key decisions with rationale, week-by-week build plan, and a commit-level breakdown (commits 1–63 plus scope additions A1–A6). When in doubt, DESIGN_DOCUMENT.md wins.
- **docs/BRD.md** — business context: the wedge (credit/refund workflows in usage-based billing), the buyer (Controller/Head of Finance Ops), pricing tiers (Tier 0 self-serve checker → diagnostic → recurring → runtime).
- **docs/PRFAQ.md** — customer-facing framing. Placeholder quotes; not for external use yet.
- **docs/POLICY_CORPUS.md** — the 14 real public policies used as extraction targets, with per-policy extraction challenges and instructions for slicing them into labeled eval examples.

## Current status

**Phase: v1.0 complete (week 6 shipped).** Commits 1–56 plus scope additions A1–A6 are done: the full extraction pipeline (4 passes), the simulation engine (3-zone routing, shadow-policy synthetic tickets, batch execution), contradiction detection completed to spec (A6 — amount band × segment × reason × time-window clustering with a binomial significance test, replacing the week-3 bare frequency threshold), cross-document contradiction detection (A3), the Streamlit demo, a TypeScript SDK with full endpoint coverage (including `evalRuns` and `crossDocument` resources), the Inspect eval harness wired to a real 60-example train/dev/test dataset (extraction recall is now genuinely measured; simulation/e2e metrics remain honestly vacuous pending ticket-level ground truth — see `packages/core/src/skiljo_core/eval/dataset_loader.py`), CI baseline refresh on merge to main, a real 5-policy corpus (Shopify/Stripe/Cloudflare/DigitalOcean) for cross-document testing, and a final quality pass (public `TaskState` import, bearer-auth negative test, consistent `{"error": {...}}` envelope on every error path, DESIGN_DOCUMENT.md endpoint documentation). 203 Python + 2 skipped and 27 TypeScript tests passing, all clean under `make lint typecheck test`.

**Known doc drift, flagged rather than silently resolved:** the week-6 work above landed under a revised plan (`docs/superpowers/plans/2026-08-10-week6-v1.0-completion.md`, plan #57–#61) that redirected week 6 toward finishing the eval harness, SDK, and A6 instead of DESIGN_DOCUMENT.md's original commit 57–63 breakdown (Render deployment blueprint, etc.). DESIGN_DOCUMENT.md Section 12's commit table has not been reconciled with what actually shipped — do that before numbering any v1.05 commits against it.

**Next: v1.05** — self-serve policy consistency checker (white-glove diagnostic), built on A2 (rendered report) + A3 (cross-document detector). Then v1.1 (review UI replacing Streamlit), v1.2 (Zendesk/Stripe/Intercom integrations replacing CSV upload). See DESIGN_DOCUMENT.md Section 14.

Track progress by which numbered commit was last completed. All scope additions (A1–A6) have landed. Update this section as v1.05 work begins.

## Architecture at a glance

Monorepo, Python-primary with one TypeScript package:

```
skiljo/
├── schemas/            # JSON Schema — CANONICAL source of truth for all data shapes
├── packages/
│   ├── core/           # Python: extraction pipeline, simulation engine, eval harness
│   ├── api/            # Python: FastAPI backend, SQLAlchemy models, Alembic migrations
│   ├── demo/           # Python: Streamlit three-page demo (extract / review / simulate)
│   └── sdk-ts/         # TypeScript: typed client SDK over the REST API
├── data/
│   ├── policies/       # Policy corpus source texts
│   ├── eval/           # train/ dev/ test/ — labeled examples. test/ is OFF LIMITS (see below)
│   └── synthetic_tickets/
├── infra/              # render.yaml (deployment target: Render.com)
└── docs/
```

Stack: Python 3.12 + uv workspaces, TypeScript 5.4+ + pnpm, Postgres 16 (Docker Compose locally), FastAPI + Pydantic v2, SQLAlchemy 2.x + Alembic, Streamlit, Inspect (eval framework), Anthropic API (Claude) via tool-use structured outputs.

## System invariants — never violate these

1. **Every LLM call is logged.** No LLM call happens outside the `LLMClient` abstraction, and every call writes a row to `llm_calls` (model, prompt_version, inputs, outputs, tokens, latency, cost).
2. **Skill versions are immutable.** A new version is a new row in `skill_versions`. Never UPDATE an existing version's spec.
3. **Every extracted rule carries resolvable citations.** Character-offset spans + quoted text into the source document. A rule without a valid citation is a hallucination and must be repaired or dropped. Citations are schema-required.
4. **The eval harness gates merges.** Evals run in CI on every PR. Regression thresholds (DESIGN_DOCUMENT.md Section 9): extraction recall −2pts max, citation resolution stays 100%, contradiction recall −5pts max, simulation match rate −3pts max, e2e accuracy −3pts max.
5. **`data/eval/test/` is off limits.** Never read, print, summarize, or tune against the held-out test set. It runs only in CI. If asked to debug a test-set failure, work from aggregate metrics, not example contents.

## Conventions

**Commits.** Conventional format: `<type>(<scope>): <summary>` where type ∈ {feat, fix, chore, docs, test, refactor, data}. One commit per plan item from DESIGN_DOCUMENT.md Section 12. Every commit leaves the repo green (`make lint typecheck test` passes). No `Co-Authored-By` trailer, no body.

**Schema changes.** schemas/*.json is canonical. Workflow: edit the JSON Schema → `make codegen` → fix resulting compile errors in BOTH Python and TypeScript → commit schema + regenerated code together. **Never hand-edit generated files** (packages/core/src/skiljo_core/schemas/, packages/sdk-ts/src/types.ts).

**Make targets.** `setup`, `codegen`, `migrate`, `test`, `lint`, `typecheck`, `api`, `demo`, `eval-extraction`, `eval-simulation`, `eval-e2e`. Prefer make targets over raw commands so behavior stays consistent.

**Python.** ruff for lint, mypy for types, pytest for tests. Type hints everywhere. structlog for JSON logging to stderr.

**TypeScript.** tsup for bundling (dual ESM/CJS), vitest for tests, Zod for runtime validation.

**Database.** All schema changes via Alembic migrations. UUID primary keys. TIMESTAMPTZ timestamps. JSONB for flexible payloads (skill specs, report summaries, LLM responses). Parameterized queries only.

## Key implementation specifics

**Predicate DSL.** Rules use a constrained language: `all`/`any` composition over operators {eq, neq, lt, lte, gt, gte, in, not_in, contains, empty, not_empty}. No arbitrary expressions, no eval. The evaluator is pure Python with table-driven tests.

**Extraction pipeline (4 passes).** (1) Segment policy text into typed sections → (2) extract candidate rules per segment WITH span citations → (3) classify each rule into a decision zone (deterministic / llm_assisted / human_only) → (4) assemble, validate against schema, resolve every citation against source text; repair loop max 2 attempts, then fail the job.

**Structured outputs.** Anthropic tool-use mode: the Pydantic schema (converted to JSON Schema) is presented as a single tool; the tool-use output is the structured response. On Pydantic validation failure, retry with the validation error fed back — max 3 attempts.

**LLM cache (commit A1).** Postgres table keyed on sha256(provider|model|prompt_version|prompt). Temperature-0 calls hit cache by default; per-call bypass available. Cache hits logged with `cached=true`.

**Shadow-policy synthetic data (week 3 — this is load-bearing).** Tickets are NOT generated from the written policy — that would make simulation circular. They're generated from a *shadow policy*: the written policy plus an authored divergence spec (which rules diverge, under what conditions, at what frequency — e.g., VIP exceptions, quiet over-threshold approvals). Ground truth follows the shadow policy. This makes contradiction detection measurable: precision/recall against the planted divergences. Acceptance for the detector: ≥0.8 recall on planted divergences, ≤1 false positive per run.

**Contradiction detection.** Cluster per-ticket results by features (amount band, segment, reason, time window) → divergence rate per cluster → flag with statistical support (min cluster size, binomial test against the base error rate). Each contradiction carries: written rule + citation, observed pattern, frequency, affected segment, estimated financial impact. The week-3 first version clusters on amount band × segment with a bare frequency threshold; A5 (week 4) adds the citation and financial-impact fields to the record, A6 (week 5) completes the clustering dimensions and the binomial test.

**Cross-document contradiction (commit A3).** Given N documents from one company, align extracted rules on the same decision surface, flag conflicting actions/thresholds. LLM-assisted alignment, mechanical conflict verification. Acceptance case: the Shopify ToS ("no refunds") vs. help-center (case-by-case review windows) pair from POLICY_CORPUS.md.

**Rendered report (commit A2).** Jinja2 → standalone print-friendly HTML at `GET /simulations/{id}/report.html`. This is a first-class product artifact (the BRD's first sellable deliverable), not an afterthought. Content is specced to BRD Section 11: executive summary, contradictions with citations and estimated financial impact, missed/over-escalations, automation candidates, ROI estimates (from A5's schema fields), per-ticket evidence appendix.

**Ticket CSV import (commit A4).** `POST /tickets/import` maps a documented CSV format onto the Ticket schema and creates a batch usable in simulations; the Streamlit simulate page gets an upload widget. Deliberately minimal — no Zendesk/Stripe connectors (v1.2) — but it's what lets a design partner run the diagnostic on their own data instead of a demo.

**Background jobs.** FastAPI BackgroundTasks + a `jobs` table (pending/running/completed/failed). Known limitation: jobs die on process restart — documented, not fixed in v1. Do NOT add Celery/Redis/Temporal.

**API.** Bearer auth with a single key from env. Error envelope: `{"error": {"code", "message", "details"}}`. Async pattern: POST returns 202 + job_id; client polls `GET /jobs/{id}`.

**Simulation concurrency.** asyncio with a semaphore of 5 for LLM-assisted zone calls.

## Environment

```
DATABASE_URL=postgresql://...   # docker-compose up -d postgres for local
ANTHROPIC_API_KEY=...           # never commit; .env is gitignored
API_KEY=...                     # inbound bearer auth key
LOG_LEVEL=info
```

Model selection is env-configurable per pipeline stage. During development, prefer Sonnet for iteration cost; the extraction passes may warrant a stronger model — measure with the eval harness before deciding. Passes 1 (segmentation) and 3 (zone classification) are candidates for Haiku (see DESIGN_DOCUMENT.md Section 15 cost optimization).

## What NOT to do

- Don't add infrastructure beyond the design: no Celery, Redis, Kafka, vector DBs, or microservices. The design is deliberately minimal.
- Don't hand-edit generated schema bindings. Change schemas/*.json and re-run codegen.
- Don't touch `data/eval/test/` contents. Ever.
- Don't tune prompts against the test set. Iterate on train/dev only.
- Don't skip the eval when it's inconvenient. If a change breaks eval thresholds, the change is wrong or the eval needs a deliberate, documented update — never a silent threshold bump.
- Don't build ahead of the commit plan without noting it. If a change of plan is genuinely better, update DESIGN_DOCUMENT.md Section 13 (open questions) or Section 12 (scope additions) in the same PR.
- Don't add features for hypothetical future needs. v1.05+ scope lives in DESIGN_DOCUMENT.md Section 14; it informs architecture but is not built now.
- Don't commit secrets, .env files, or API keys.

## Definition of done, per commit

1. The acceptance criterion from DESIGN_DOCUMENT.md Section 12 for that commit is met.
2. `make lint typecheck test` passes.
3. If schemas changed: codegen re-run, both languages compile.
4. If extraction/simulation behavior changed: relevant eval suite run locally on train/dev; no regression beyond thresholds.
5. Commit message follows the convention and references the plan item (e.g., `feat(core): shadow-policy ticket generator [plan #26]`).

## Where the project is going (context, not tasks)

After the 6-week v1.0: v1.05 is a self-serve policy consistency checker (lead magnet and first transaction, built on A2+A3 — the first *serious* revenue is the BRD's Tier 1 paid diagnostic delivered white-glove), v1.1 replaces Streamlit with a real review UI, v1.2 replaces CSV upload with real Zendesk/Intercom/Stripe integrations. Details in DESIGN_DOCUMENT.md Section 14. This matters for architectural decisions today: the cross-document detector and rendered report are product surfaces, not internal tools — build them accordingly.

**The revenue thread (DESIGN_DOCUMENT.md Section 11, "The revenue thread running through the build"):** Commits A2 and A3 are the v1.05 product minus a payment flow — hold them to product-grade quality on output, error handling, and presentation. Policy teardown posts are published during the build (teardown #1 during week 3 from extraction output; teardown #2 during week 6 from A3's Shopify finding). If asked to generate teardown material, the source is real extraction runs against corpus policies — never fabricated findings.

## Learning debriefs

After every implementation task's commit lands (the same checkpoint where `.superpowers/sdd/progress.md` gets updated, or immediately after the commit when not using subagent-driven-development), write a debrief to `docs/learning/week<N>-task<M>-<slug>.md` covering what was built, the non-obvious concepts involved, why that approach was chosen, and where to look in the code. Add new concepts to `docs/learning/GLOSSARY.md` (alphabetical, link back to the debrief) the first time they appear; later debriefs link to existing entries instead of re-explaining. Update `docs/learning/README.md`'s index. This is the orchestrator's responsibility, not a subagent's. See `docs/superpowers/specs/2026-06-21-learning-debrief-process-design.md` for the full design. New weekly plans (via `writing-plans`) should include a "write learning debrief" step per task by default.
