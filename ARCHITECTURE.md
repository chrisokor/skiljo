# Skiljo — Architecture Reference

This document is the code-reader's companion to `docs/DESIGN_DOCUMENT.md`. Where the design document explains what the system is and what decisions were made, this document shows where those decisions live in the code, explains the mechanics of each layer, and answers "why this, not that" at the implementation level.

Read time: ~10 minutes.

---

## Table of Contents

1. [System Purpose](#1-system-purpose)
2. [Component Map](#2-component-map)
3. [Data Model](#3-data-model)
4. [Key Abstractions](#4-key-abstractions)
   - [Predicate DSL](#41-predicate-dsl)
   - [Decision Zones](#42-decision-zones)
   - [Shadow Policy](#43-shadow-policy)
   - [Contradiction Detection](#44-contradiction-detection)
5. [Extraction Pipeline](#5-extraction-pipeline)
6. [Simulation Engine](#6-simulation-engine)
7. [LLM Client and Cache](#7-llm-client-and-cache)
8. [API Layer](#8-api-layer)
9. [TypeScript SDK](#9-typescript-sdk)
10. [Streamlit Demo](#10-streamlit-demo)
11. [Testing Strategy](#11-testing-strategy)
12. [Performance Characteristics](#12-performance-characteristics)
13. [Security Model](#13-security-model)
14. [Future Roadmap](#14-future-roadmap)
15. [Developer Setup](#15-developer-setup)

---

## 1. System Purpose

Skiljo extracts a company's refund and credit policy from documents, encodes it as a structured executable skill, simulates that skill against historical or synthetic tickets, and surfaces contradictions between the written policy and observed behavior.

The output is a **SimulationReport**: match rate, escalation accuracy, a contradiction list with citations and estimated financial impact, and a per-ticket evidence appendix. The report is the deliverable — the first artifact a buyer can act on.

The underlying discipline the system enforces: every LLM call is logged and traced, every extracted rule cites the text it came from, and every quality metric is measured against held-out data in CI.

---

## 2. Component Map

```
┌──────────────────────────────────────────────────────────────┐
│                  Streamlit Demo (packages/demo)               │
│         upload policy → extract → review → simulate           │
└───────────────────────────────┬──────────────────────────────┘
                                │ HTTP (Bearer auth)
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                 FastAPI Backend (packages/api)                │
│                                                              │
│  POST /skills/extract      POST /simulations                 │
│  GET  /skills/{id}         GET  /simulations/{id}/report     │
│  POST /tickets/import      GET  /simulations/{id}/report.html│
│  GET  /jobs/{id}           (all routes require Bearer token) │
│                                                              │
│        Background jobs via FastAPI BackgroundTasks           │
│              Job state tracked in Postgres                   │
└───────┬───────────────────────┬──────────────────────────────┘
        │                       │
        ▼                       ▼
┌──────────────┐       ┌────────────────────────────────────┐
│  LLM Client  │       │         Postgres 16                │
│  (packages/  │       │                                    │
│   core/llm)  │       │  policies        llm_cache         │
│              │       │  skills          jobs              │
│  Anthropic   │       │  skill_versions  eval_runs         │
│  tool-use;   │       │  simulation_runs                   │
│  provider    │       │  simulation_results                │
│  abstraction │       │  llm_calls                         │
└──────────────┘       └────────────────────────────────────┘
        ▲
        │ consumed by
┌───────┴────────────────────────┐
│  TypeScript SDK (packages/     │
│  sdk-ts)                       │
│                                │
│  Zod types from same JSON Schema│
│  tsup → dual ESM/CJS bundle    │
└────────────────────────────────┘
```

**Monorepo layout:**

```
skiljo/
├── schemas/                    # JSON Schema — canonical source of truth
│   ├── skill.schema.json
│   ├── rule.schema.json
│   ├── ticket.schema.json
│   ├── simulation_report.schema.json
│   └── codegen/                # Scripts that produce typed bindings
├── packages/
│   ├── core/                   # Python: extraction + simulation + eval harness
│   │   └── src/skiljo_core/
│   │       ├── extraction/     # Four-pass pipeline
│   │       ├── simulation/     # Engine, evaluator, contradictions
│   │       ├── llm/            # Client, cache, logging
│   │       ├── schemas/        # Generated Pydantic models (do not hand-edit)
│   │       └── db/             # SQLAlchemy models + Alembic
│   ├── api/                    # Python: FastAPI backend
│   │   └── src/skiljo_api/
│   │       ├── routers/        # skills, simulations, jobs, tickets
│   │       └── templates/      # Jinja2 HTML report template
│   ├── demo/                   # Python: Streamlit three-page app
│   │   └── src/
│   │       ├── app.py          # Entry point
│   │       └── pages/          # 1_Extract.py, 2_Review.py, 3_Simulate.py
│   └── sdk-ts/                 # TypeScript: client SDK
│       └── src/                # client.ts, skills.ts, simulations.ts, types.ts
├── data/
│   ├── policies/               # Policy corpus source texts
│   ├── eval/                   # train/ dev/ test/ — labeled examples
│   └── synthetic_tickets/      # Committed synthetic ticket batches
└── docs/
```

---

## 3. Data Model

All schema changes go through Alembic migrations in `packages/core/alembic/`. The database is Postgres 16. UUID primary keys throughout; all timestamps are `TIMESTAMPTZ`; flexible payloads use `JSONB`.

### Core Tables

**`policies`** — raw uploaded documents, stored verbatim. The `raw_text` column is the input to the extraction pipeline.

**`skills`** — identity records; one row per named skill regardless of version. `current_version_id` FK points at the active `skill_versions` row.

**`skill_versions`** — immutable snapshots. `spec JSONB` holds the full Skill structure (see Section 4). Never updated after creation; `status` moves from `draft` → `approved` → `archived` via explicit API calls, never via UPDATE to the spec.

**`simulation_runs`** — one row per batch simulation. `summary JSONB` stores the SimulationReport aggregate (match rate, escalation accuracy, contradiction count, automation candidates). Status transitions: `pending` → `running` → `completed` / `failed`.

**`simulation_results`** — one row per ticket per simulation run. Captures the per-ticket decision, zone, reasoning, and a FK to the originating `llm_calls` row so every LLM-assisted decision is traceable.

**`llm_calls`** — append-only log. Every LLM call writes here before returning, including cache hits (which log `cached=true`, `latency_ms=0`). Columns: `provider`, `model`, `prompt_version`, `prompt_text`, `response_text`, `input_tokens`, `output_tokens`, `latency_ms`, `cost_estimate_usd`.

**`llm_cache`** — Postgres-backed response cache keyed on `sha256(provider|model|prompt_version|prompt_text)`. Temperature-0 calls check here before hitting the API.

**`jobs`** — background job tracking. `kind` ∈ {`extract`, `simulate`}. `result_ref UUID` points at the resulting `skill_version` or `simulation_run` on success. `error TEXT` captures the failure message on failure. Jobs lost on process restart (known limitation; see Section 6.2).

**`eval_runs`** — metric history written by the eval harness on every CI run. Queryable via `make eval-history`.

### Invariants the Code Enforces

1. No LLM call occurs outside `AnthropicClient.generate_structured` — the only path to the Anthropic SDK. Every call writes a `llm_calls` row before returning (`packages/core/src/skiljo_core/llm/anthropic_client.py`).

2. Skill specs are never overwritten. The API's approve endpoint promotes `status`; it does not touch `spec`. Any re-extraction creates a new `skill_versions` row with `version_number = max(existing) + 1`.

3. Every extracted rule carries at least one citation with character-offset spans and quoted text. Citation resolution (quoted text must appear at the claimed offsets in the source) is verified in Pass 4 and is a CI-blocking eval metric.

4. All queries go through SQLAlchemy parameterized queries. No raw SQL string interpolation anywhere in the codebase.

---

## 4. Key Abstractions

### 4.1 Predicate DSL

The predicate language is intentionally small. It lives in `schemas/rule.schema.json` (canonical) and `packages/core/src/skiljo_core/schemas/rule_schema.py` (generated Pydantic).

**Operators:** `eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `in`, `not_in`, `contains`, `empty`, `not_empty`

**Composition:** `all` (AND) and `any` (OR) over a list of predicates or nested conditions.

A condition evaluating `purchase_days_ago ≤ 30 AND refund_amount ≤ 100 AND fraud_flags is empty` looks like:

```json
{
  "all": [
    { "field": "purchase_days_ago", "op": "lte", "value": 30 },
    { "field": "refund_amount",     "op": "lte", "value": 100 },
    { "field": "fraud_flags",       "op": "empty" }
  ]
}
```

The evaluator is 52 lines of pure Python with no external dependencies:
`packages/core/src/skiljo_core/simulation/evaluator.py`

**Why a custom DSL, not JSONLogic or Python eval?**
- JSONLogic is verbose for the shapes this system needs and harder for an LLM to generate reliably.
- Python `eval` is a security vulnerability and produces unauditable rule artifacts.
- A constrained DSL is easy for the LLM to generate, easy to render in a human-review UI, and evaluable with a trivially auditable evaluator.

### 4.2 Decision Zones

Every Skill partitions its rules into three zones, evaluated in priority order:

| Zone | Evaluated by | Requires human approval |
|------|-------------|------------------------|
| `deterministic` | Predicate evaluator (pure Python) | No |
| `llm_assisted` | Predicate evaluator matches; LLM provides recommendation | Yes |
| `human_only` | Predicate evaluator matches; ticket escalated | Always |

The executor in `packages/core/src/skiljo_core/simulation/executor.py` implements this cascade:

1. Walk deterministic rules in order. First match → return decision immediately.
2. If no deterministic match, walk LLM-assisted rules. First match → invoke the LLM with ticket context, return structured recommendation.
3. If no LLM-assisted match, walk human-only rules. First match → return escalation record.
4. If no rule matched at all → default escalation (`escalate_to_human`).

The zone assignment is set at extraction time (Pass 3) and is immutable within a skill version.

### 4.3 Shadow Policy

The synthetic ticket generator (`packages/core/src/skiljo_core/simulation/generator.py`) does **not** generate tickets from the written policy. That would make simulation circular: the skill would always match the tickets it was designed for, and contradiction detection would have nothing to find.

Instead, tickets are generated from a **shadow policy**: the written policy plus a structured divergence spec that describes informal rules the real team actually follows. Examples:
- VIP customers (segment = `enterprise`) get approved at 2× the documented threshold.
- Refunds slightly above the limit (e.g., $105 when the limit is $100) get quietly approved during Q4.
- Fraud-flagged tickets get escalated even when the written policy says approve.

The divergence spec authors these patterns explicitly: which rule diverges, under what field conditions, at what frequency. Ground-truth decisions in the generated tickets follow the shadow policy, not the written one.

This makes contradiction detection measurable. The planted divergences are known ground truth; the detector's job is to recover them from ticket outcomes alone. That yields real precision and recall numbers rather than anecdotal "it found something."

Acceptance target: ≥0.8 recall on planted divergences, ≤1 false positive per run.

### 4.4 Contradiction Detection

`packages/core/src/skiljo_core/simulation/contradictions.py`

The detector groups per-ticket results into clusters by `(amount_band, customer_segment)` — the first-version clustering dimensions. For each cluster with at least `min_cluster_size` tickets:

1. Compute the divergence rate: fraction of tickets where the skill's decision differs from ground truth.
2. If rate exceeds the threshold (default 5%), flag as a contradiction.
3. Find the most common `(written_decision, observed_decision)` pair among divergent tickets.
4. Compute financial impact: divergent ticket count × average refund amount in the cluster.

Each `Contradiction` record carries: the cluster key, written vs. observed decision, frequency, affected ticket count and IDs, optional citation (linking to the written rule), and an estimated financial impact in USD.

The current version clusters on two dimensions with a frequency threshold. A6 (week 5) adds reason category and time window as dimensions and replaces the frequency threshold with a binomial test.

---

## 5. Extraction Pipeline

`packages/core/src/skiljo_core/extraction/pipeline.py` — entry point: `run_extraction_pipeline()`

The pipeline is four sequential passes, each an LLM call with a Pydantic-validated structured output:

**Pass 1 — Segmentation** (`extraction/segmentation.py`)
The raw policy text is segmented into typed logical sections: eligibility, thresholds, approvals, exceptions, refund methods, audit requirements. A Claude call with a small structured output schema produces the segment list. Segmentation keeps the heavy extraction passes focused and improves rule quality on long policies.

**Pass 2 — Rule Extraction** (`extraction/rules.py`)
For each segment, a segment-type-specific prompt extracts candidate rules in the predicate DSL. Eligibility segments get a different prompt from threshold segments because the condition shapes differ enough to degrade a single uber-prompt. Each rule must include citations: character-offset `start`/`end` into the segment text plus the `quoted_text` captured at extraction time.

**Pass 3 — Zone Classification** (`extraction/zones.py`)
A classifier prompt takes each candidate rule and assigns it to `deterministic`, `llm_assisted`, or `human_only`. A rule with mechanical numeric conditions → deterministic. A "goodwill exception that requires manager judgment" → llm_assisted. A "refund above $10K" → human_only.

**Pass 4 — Assembly and Validation** (`extraction/assembly.py`)
The assembled Skill is validated against `schemas/skill.schema.json`. Every citation is resolved: the `quoted_text` must appear at or near the claimed character offsets in the source document. A rule with an unresolvable citation is a probable hallucination.

If schema validation fails, the validation error is fed back to a repair prompt — up to 2 repair attempts before the extraction job fails. If a citation fails resolution, the rule is either repaired (repair prompt) or dropped with a logged warning.

The output is persisted as a new `skill_versions` row with `status='draft'`.

---

## 6. Simulation Engine

### 6.1 Batch Execution

`packages/core/src/skiljo_core/simulation/engine.py`

```python
async def simulate_batch(
    skill: Skill,
    tickets: list[Ticket],
    llm_client: LLMClient,
    max_concurrency: int = 5,
) -> list[Result]:
    sem = asyncio.Semaphore(max_concurrency)

    async def run_one(ticket: Ticket) -> Result:
        async with sem:
            return await asyncio.to_thread(simulate_ticket, skill, ticket, llm_client)

    return list(await asyncio.gather(*[run_one(t) for t in tickets]))
```

**Why `asyncio.to_thread`?** The Anthropic Python SDK's `messages.create` is a synchronous blocking call. The simulation engine is an `async` function (called from an async FastAPI background task), but we can't `await` a synchronous SDK call directly. `asyncio.to_thread` runs each `simulate_ticket` call in a thread pool, releasing the event loop while it waits, so the semaphore actually bounds the number of simultaneous in-flight Anthropic API calls rather than just bounding Python thread context switches.

The semaphore of 5 respects Anthropic's rate limits and keeps cost predictable. It is configurable per simulation run.

### 6.2 Report Aggregation

`compute_report()` in `packages/core/src/skiljo_core/simulation/engine.py` takes the flat `list[Result]` and produces a `SimulationReport`:

- **match_rate**: fraction of tickets where the skill's decision matches `ground_truth_decision`.
- **escalation_accuracy**: of tickets escalated to `human_only`, fraction that had a ground-truth decision in the escalation set.
- **automation_candidate_count**: tickets resolved in the `deterministic` zone (no LLM, no human needed).
- **results**: full per-ticket list, stored in `simulation_runs.summary JSONB`.

### 6.3 Background Job Limitation

Simulations run as FastAPI `BackgroundTasks`. If the API process restarts mid-simulation, the job row stays `running` forever. There is no sweeper in v1. The README documents this and the upgrade path (move to a real task queue). The `jobs` table's `started_at` column supports building a future sweeper.

---

## 7. LLM Client and Cache

### 7.1 Protocol

`packages/core/src/skiljo_core/llm/base.py` defines the `LLMClient` Protocol:

```python
class LLMClient(Protocol):
    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        model: str,
        prompt_version: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> StructuredResponse[T]: ...
```

`StructuredResponse[T]` carries `.data: T` (the validated Pydantic model), `.attempts: int`, and `.llm_call_id: UUID | None` for downstream FK linkage.

The Protocol means: swap in a mock for tests, add an OpenAI implementation in one file, never touch the extraction or simulation code. The only production implementation today is `AnthropicClient`.

### 7.2 Structured Output via Tool Use

`packages/core/src/skiljo_core/llm/anthropic_client.py`

Anthropic's tool-use mode is used instead of free-form JSON generation because it is Anthropic's most reliable structured-output mechanism. The Pydantic model's `model_json_schema()` is presented to Claude as a single tool's `input_schema`. Claude's tool-use output is the structured response — Claude commits to filling the schema, not just producing text that happens to look like JSON.

The retry loop (up to 3 attempts):
1. Call the API.
2. Extract the `tool_use` block from `response.content`.
3. Validate with `schema.model_validate(tool_use_block.input)`.
4. If `ValidationError`, append the error message to the prompt as feedback and retry.

On success, log to `llm_calls` and (if temperature=0) store in `llm_cache`. On exhausted retries, re-raise the last `ValidationError`.

### 7.3 Response Cache

`packages/core/src/skiljo_core/llm/cache.py`

Cache key: `sha256(provider|model|prompt_version|prompt_text)` — a deterministic fingerprint.

Cache hits:
- Return the stored JSON response without hitting the API.
- Log a `llm_calls` row with `cached=True`, `latency_ms=0`.
- Return `attempts=0` in `StructuredResponse`.

Temperature-0 calls are cached by default. Pass `temperature > 0` to bypass. This makes eval re-runs nearly free for unchanged prompts and makes CI reproducible.

---

## 8. API Layer

`packages/api/src/skiljo_api/`

FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.x (sync sessions, no async ORM — the async work happens at the `simulate_batch` level).

### 8.1 Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check, no auth |
| POST | `/policies` | Upload policy text |
| GET | `/policies/{id}` | Retrieve policy |
| POST | `/skills/extract` | Start extraction job (202 + job_id) |
| GET | `/skills` | List skills |
| GET | `/skills/{id}` | Current skill version |
| GET | `/skills/{id}/versions` | All versions |
| POST | `/skills/{id}/versions/{v}/approve` | Promote to approved |
| POST | `/tickets/import` | CSV ticket batch import |
| POST | `/simulations` | Start simulation job (202 + job_id) |
| GET | `/simulations/{id}` | Status + summary |
| GET | `/simulations/{id}/report` | Full SimulationReport JSON |
| GET | `/simulations/{id}/report.html` | Rendered HTML report |
| GET | `/jobs/{id}` | Poll job status |

All routes except `/health` require `Authorization: Bearer <API_KEY>`.

### 8.2 Authentication

`packages/api/src/skiljo_api/dependencies.py`

```python
def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(_bearer)) -> None:
    if not hmac.compare_digest(credentials.credentials, config.API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
```

`hmac.compare_digest` prevents timing attacks that could leak the key length via response-time differences.

### 8.3 Async Pattern

Long-running endpoints (extract, simulate):
1. Create a `jobs` row (`status='pending'`).
2. Register work with `BackgroundTasks`.
3. Return `202 Accepted` with `{"job_id": "...", "status": "pending"}`.
4. Background task: update job to `running`, do the work, update to `completed` with `result_ref`.
5. Client polls `GET /jobs/{id}` until terminal status.

### 8.4 Error Envelope

All errors use: `{"error": {"code": "...", "message": "...", "details": {...}}}`. Pydantic validation errors are caught and translated to `400` with field-level detail in `details`.

### 8.5 Rendered HTML Report

`GET /simulations/{id}/report.html` renders `packages/api/src/skiljo_api/templates/report.html` via Jinja2 into a standalone, print-friendly HTML document. Content: executive summary (match rate, escalation accuracy, contradiction count in plain language), contradiction list with citations and estimated financial impact, automation candidates, per-ticket evidence appendix. This is the BRD's Tier 1 diagnostic deliverable — treated as a first-class product artifact, not an afterthought.

---

## 9. TypeScript SDK

`packages/sdk-ts/src/`

The SDK is a thin, strongly-typed wrapper over the REST API. All types come from Zod schemas generated from the same `schemas/*.schema.json` files the Python side uses — meaning a schema change in `schemas/` propagates to both languages via `make codegen`.

**Key modules:**
- `client.ts` — `SkiljoClient` class, `fetch` wrapper, Bearer auth header injection, error parsing
- `policies.ts`, `skills.ts`, `simulations.ts`, `jobs.ts` — resource-scoped method groups
- `types.ts` — generated Zod schemas and inferred TypeScript types (do not hand-edit)

**Usage:**

```typescript
import { SkiljoClient } from "@skiljo/sdk";

const client = new SkiljoClient({ apiKey: process.env.SKILJO_API_KEY });
const policy  = await client.policies.upload({ text: policyText });
const job     = await client.skills.extract({ policyId: policy.id });
const skill   = await client.jobs.waitForCompletion(job.id);
const sim     = await client.simulations.create({ skillVersionId: skill.versionId, tickets });
const report  = await client.simulations.getReport(sim.id);
```

Built with `tsup` to dual ESM/CJS. No runtime dependencies beyond `zod`. Tested with Vitest.

---

## 10. Streamlit Demo

`packages/demo/src/`

Three pages, navigated via Streamlit's multi-page app:

**`pages/1_Extract.py`** — File upload or paste-text, "Extract" button, job poller with progress indicator, rendered skill view showing rules grouped by zone with citations. Developer-details expander shows the LLM calls (model, prompt version, cost) that drove the extraction.

**`pages/2_Review.py`** — Renders the draft skill; user can mark rules accepted/rejected; "Approve version" calls `POST /skills/{id}/versions/{v}/approve`, promoting the spec to `approved` in the database.

**`pages/3_Simulate.py`** — Skill picker (approved versions only), ticket batch picker (pre-loaded synthetic batches + CSV upload via `POST /tickets/import`), "Run simulation" button, report rendered with summary cards and a sortable per-ticket table. Links to the HTML report endpoint.

The demo calls the local API by default (configurable via env). The shared API client is `packages/demo/src/api_client.py`.

---

## 11. Testing Strategy

### Unit Tests

`packages/core/tests/` and `packages/api/tests/`

Current state: **110 passed, 1 skipped** (the skipped test requires live Anthropic API credentials).

Key test modules:
- `test_evaluator.py` — table-driven tests for every operator and `all`/`any` composition in the predicate DSL
- `test_simulation_engine.py`, `test_simulation_executor.py` — simulation engine against fixed skill + ticket fixtures; mock LLM client
- `test_contradictions.py` — detector against known-contradictory fixtures
- `test_rules.py`, `test_segmentation.py`, `test_zones.py`, `test_assembly.py` — per-pass extraction tests with mocked LLM
- `test_simulation_golden.py` — golden-fixture tests: run simulation against committed `data/synthetic_tickets/refund_v1/` batch, verify report matches a stored golden output; catches silent regressions in the simulation engine
- `test_report_html.py` — HTML report endpoint produces valid HTML with expected content sections
- `test_tickets_import.py` — CSV import validates columns, rejects malformed rows with row-level error detail
- `test_e2e_integration.py` — end-to-end flow (upload → extract → simulate → report), gated behind `INTEGRATION=1` env var (uses live API and real Anthropic calls)

TypeScript: `packages/sdk-ts/src/*.test.ts` tested with Vitest (21 tests, mocked fetch).

### Schema-Level Testing

`test_models.py` and `test_eval_data.py` verify that generated Pydantic models parse known-valid JSON and that every file in `data/eval/train/` and `data/eval/dev/` passes schema validation.

### Eval Harness (CI-Blocking)

Built on Inspect. Three suites, all run via GitHub Actions on every PR:

| Suite | What it measures | Block threshold |
|-------|-----------------|-----------------|
| `eval-extraction` | Extraction recall by field type, citation resolution rate | recall −2pts max; citation resolution must stay 100% |
| `eval-simulation` | Match rate, escalation accuracy, contradiction detector precision/recall | match rate −3pts max; contradiction recall −5pts max |
| `eval-e2e` | Full policy → extract → simulate flow | accuracy −3pts max |

Dataset split: 30 train / 15 dev / 15 test. Test set (`data/eval/test/`) is off limits for manual inspection — it runs only in CI. Metric history is persisted to `eval_runs` and comparable via `make eval-history`.

---

## 12. Performance Characteristics

**Extraction latency:** 3–6 seconds per policy for the four-pass pipeline against Claude claude-sonnet-4-5, depending on policy length. The extraction passes 1 (segmentation) and 3 (zone classification) are candidates for Haiku, which would cut extraction cost by ~60–70% with negligible quality loss. This optimization is deferred to measurement after the eval harness is expanded (week 5).

**Simulation throughput:** 100 tickets in approximately 30–90 seconds with `max_concurrency=5`. Tickets resolved in the deterministic zone take <1ms each (pure Python evaluator). Tickets hitting the LLM-assisted zone add one API round-trip each.

**LLM cache hit rate:** In development against a stable policy corpus, cache hit rates of 80–90% on re-runs are typical. This makes eval re-runs for unchanged prompts nearly free in cost and reduces CI wall-clock time.

**Database:** No query optimization beyond FK indexes in the current schema. The expected data volume (dozens of simulation runs, thousands of tickets) is well within Postgres's default planner behavior with no tuning.

**Concurrency:** The semaphore of 5 concurrent LLM calls is tunable per `simulate_batch` call. At 5 concurrent calls with typical Anthropic latency of 1–3 seconds per LLM-assisted ticket, throughput is approximately 2–5 LLM-assisted tickets per second.

---

## 13. Security Model

**Authentication:** Single API key from environment (`API_KEY` env var), checked on every non-health request via `Authorization: Bearer` header. `hmac.compare_digest` prevents timing oracle attacks. This is a demo-appropriate single-key approach, not production multi-tenant auth.

**LLM isolation:** Every LLM call goes through `AnthropicClient.generate_structured`. There is no path to call the Anthropic API that bypasses logging. The system never exposes the raw Anthropic API key to clients.

**SQL injection:** All database access through SQLAlchemy ORM with parameterized queries. No string-interpolated SQL anywhere in the codebase.

**Secret management:** `ANTHROPIC_API_KEY`, `API_KEY`, and `DATABASE_URL` live in `.env` (gitignored) for local development. Production secrets inject via Render's environment variable management.

**Audit trail:** `llm_calls` is the primary audit surface. Every LLM invocation — extraction, zone evaluation, repair attempts — is logged with full inputs, outputs, model version, prompt version, and cost. Per-ticket simulation results FK to the originating `llm_calls` row.

**Data residency:** Anthropic's API does not train on data submitted via the API by default. Policy documents are stored verbatim in `policies.raw_text`. For the current corpus (public policies or synthetic data), this is acceptable. A production version would add a PII redaction pass before storage.

**Known limitations:** No rate limiting on API endpoints. No per-client quotas. No audit log for human-facing actions (approve, reject). These are appropriate deferred items for v1.5 multi-tenant hardening.

---

## 14. Future Roadmap

### v1.05 — Self-serve policy consistency checker

Commits A2 (rendered HTML report) and A3 (cross-document contradiction detection) are the core of this tier. Given two or more policy document URLs from the same company, the system extracts a skill from each, aligns rules governing the same decision surface, and flags conflicts with citations from both sources. The A2 report becomes the deliverable. Add a Stripe payment flow and this is a transactable product.

The acceptance case for A3 is the Shopify ToS ("no refunds") versus help-center ("case-by-case review windows") contradiction from `docs/POLICY_CORPUS.md`.

### v1.1 — Real review UI

Replace Streamlit with a Next.js app that consumes the TypeScript SDK. The motivation is collaboration: the simulation report and skill review steps are artifacts a Controller shares with Support Ops, comments on, and references in audit conversations. Streamlit does not support this.

The TypeScript SDK built in week 4 is what this UI consumes, validating the SDK's design under real load.

### v1.2 — Real integrations replacing CSV upload

`POST /tickets/import` accepts CSV as a deliberate minimal starting point. v1.2 builds read-only integrations for Zendesk, Intercom, and Stripe. The hard part is data normalization, not API calls — the Ticket schema's extension points (optional source-specific fields) are designed for this.

### v1.3 — Governed runtime

The system transitions from simulation engine to execution layer. Per-skill delegated authority (permission engine), tool execution against sandboxed downstream systems (Stripe test mode, Zendesk sandbox), and full audit log infrastructure per the BRD. The hardest part is trust, not engineering — the simulation report earning buyer confidence is the prerequisite. Gate before committing to runtime: 3+ paid diagnostics delivered, at least one buyer asking for recurring monitoring.

### v1.4 — MCP integration

The skill spec becomes the canonical definition of an MCP tool. The runtime becomes the executor. Each skill maps to one MCP tool, or a single `execute_workflow` tool with a skill ID parameter — the right granularity depends on how agent platforms evolve.

### v1.5 — Multi-tenancy and production hardening

Real authentication (Clerk or Auth0), row-level security in Postgres, per-tenant LLM quotas, production observability (Honeycomb or Datadog), backup and disaster recovery, hard cost cutoffs per tenant.

---

## 15. Developer Setup

```bash
# One-time
git clone <repo>
cd skiljo
docker-compose up -d postgres
uv sync
pnpm install
make codegen
make migrate

# Daily
make api      # FastAPI on :8000
make demo     # Streamlit on :8501
make test     # before every commit
make lint typecheck

# Evals (local, train/dev sets only)
make eval-extraction
make eval-simulation
make eval-e2e
```

**Schema changes** require the full cycle: edit `schemas/*.schema.json` → `make codegen` → fix compile errors in both Python and TypeScript → commit schema + generated code together. Never hand-edit `packages/core/src/skiljo_core/schemas/` or `packages/sdk-ts/src/types.ts`.

**Commit format:** `<type>(<scope>): <summary>` — no body, no trailers. Type ∈ {feat, fix, chore, docs, test, refactor, data}. One commit per plan item from `docs/DESIGN_DOCUMENT.md` Section 12.

**CI gates:** Every commit must pass `make lint typecheck test`. Every PR runs the three eval suites against the held-out test set. A regression on any primary metric blocks merge.

**`data/eval/test/` is off limits.** Do not read, print, summarize, or tune against the test set during development. It runs only in CI.
