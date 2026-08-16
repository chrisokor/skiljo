# Skiljo — Design Document

| Field | Value |
|---|---|
| **Project** | Skiljo: Governed Workflow Skills for AI Agents |
| **Status** | Draft v1 — pre-build |
| **Author** | [Founder] |
| **Last updated** | 2026-06-14 |
| **Scope** | Portfolio build, 6 weeks |
| **Companion docs** | BRD_v3.md, PRFAQ.md |

---

## Table of Contents

1. Background and motivation
2. Goals and non-goals
3. System overview
4. Core abstractions and data model
5. Component design
6. Key design decisions
7. Failure modes and observability
8. Security and data handling
9. Testing and evaluation strategy
10. Deployment
11. Build plan (week-by-week)
12. Commit-level breakdown
13. Open questions
14. Paths forward beyond the 6-week build
15. Future work (smaller technical improvements)
16. Appendices

---

## 1. Background and motivation

AI agents can hold conversations and call tools, but they fail when work requires company-specific judgment. A support agent can answer "where is my refund?" but typically cannot safely decide whether to issue one above a company's approval threshold, because doing so requires comparing written policy to actual behavior, knowing the contract terms, getting Finance approval, and logging the right audit trail. The bottleneck is no longer model capability — it is the absence of a structured representation of how a specific company is allowed to operate.

This project builds a defensible technical implementation of one slice of that problem: extracting refund and credit policy from documentation, comparing it against historical behavior, and producing a versioned executable skill specification that an agent could in principle act on. The slice is narrow on purpose. Finance-sensitive workflows are where policy fidelity matters most and where mistakes are most expensive, which makes them both the right wedge and the right testbed for the underlying ideas.

The deeper technical problem is non-determinism. LLMs produce different outputs for the same input, hallucinate policy that doesn't exist in source documents, and degrade silently as prompts or models change. A system that turns policy into executable rules has to handle this honestly: with structured outputs, schema validation, eval harnesses, contradiction detection between extracted rules and historical behavior, and human-reviewable artifacts. Those are the disciplines this project is built around.

The system is scoped to be completable as a serious technical project over summer and into fall, with a single developer working part-time alongside school. The scope reflects that reality, not a smaller ambition for the underlying problem. The components excluded from the 6-week build — governed runtime, MCP server, real customer integrations — are tracked in Section 14 as paths forward if the project continues past December.

## 2. Goals and non-goals

### Goals

The system should ingest a real refund or credit policy document and produce a structured, schema-valid skill specification capturing the policy's decision logic. It should generate synthetic historical tickets matching realistic distributions and simulate the extracted skill against them, producing a simulation report with match rate, escalation accuracy, and contradiction detection. Every LLM call should be logged with model version, prompt version, latency, and cost. A held-out evaluation set should run in CI on every commit, blocking merges that regress key metrics. The end-to-end flow should be demonstrable through a Streamlit UI, and the system should expose a TypeScript SDK in addition to its Python interface.

### Non-goals

The exclusions below are scoped on engineering grounds — they're either prerequisites for a different version of the product or they require infrastructure (real customer data, real integrations) the build does not have.

Multi-tenancy, authentication beyond a single hardcoded API key, and any form of payment infrastructure are out of scope because the system is single-tenant and not commercially deployed. Real runtime execution against production systems (Stripe, Zendesk) is out of scope because it requires customer integrations and a permission-enforcement layer that this version doesn't build — this is a simulation system, not an execution layer. The full audit-log infrastructure described in the BRD is not built; the LLM call log persisted in Postgres is sufficient for the simulation phase. Permission enforcement and the governed runtime described in the BRD's v1.1+ architecture are out of scope and tracked in Section 14. UI polish beyond what's needed for clear usage of the three core flows is out of scope — the Streamlit interface is intentionally functional rather than designed.

### Success criteria

The build succeeds if a real refund or credit policy from a target ICP company (the corpus in `POLICY_CORPUS.md`) can be extracted into a schema-valid skill spec, simulated against a realistic batch of tickets, and produce a simulation report whose match rate, escalation accuracy, and contradiction detection are measurably correct against a held-out test set. The eval harness running in CI is the discipline that makes this claim verifiable rather than anecdotal. A working deployed URL is preferred but not required.

## 3. System overview

### Architectural shape

The system is a multi-stage LLM pipeline with structured outputs, persistent storage, versioned artifacts, and a reproducible evaluation framework. It is organized as a Python monorepo with one TypeScript subpackage. The Python side hosts the extraction and simulation pipeline (`core`), the FastAPI backend (`api`), and the Streamlit demo (`demo`). The TypeScript side hosts a client SDK (`sdk-ts`) that wraps the same API. JSON Schema serves as the single source of truth for data shapes, with codegen producing Pydantic models for Python and Zod schemas for TypeScript.

### Component diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Demo (Python)                      │
│       upload policy → extract skill → review → simulate          │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend (Python)                   │
│                                                                  │
│  POST  /policies          POST /simulations                      │
│  POST  /skills/extract    GET  /simulations/{id}                 │
│  GET   /skills/{id}       GET  /simulations/{id}/report          │
│  GET   /skills/{id}/versions    GET /jobs/{id}                   │
│                                                                  │
│              Background tasks via FastAPI BackgroundTasks        │
│                    Job state tracked in Postgres                 │
└────┬─────────────────────────┬──────────────────┬───────────────┘
     │                         │                  │
     ▼                         ▼                  ▼
┌──────────┐            ┌─────────────┐    ┌────────────────┐
│   LLM    │            │  Postgres   │    │  Eval Harness  │
│  Client  │            │             │    │   (Inspect)    │
│          │            │  policies   │    │                │
│ Claude   │            │  skills     │    │ Runs in CI on  │
│ primary, │            │  skill_vers │    │ every PR;      │
│ provider │            │  sim_runs   │    │ blocks merge   │
│ abstr.   │            │  sim_results│    │ on regression  │
│          │            │  llm_calls  │    │                │
│          │            │  jobs       │    │                │
│          │            │  eval_runs  │    │                │
└──────────┘            └─────────────┘    └────────────────┘

         ▲                                          ▲
         │                                          │
         └────── consumed by ──────┐    ┌──────────┘
                                   │    │
                          ┌────────┴────┴───────┐
                          │  TypeScript SDK     │
                          │  (skiljo-sdk-ts)    │
                          │                     │
                          │  Zod types from     │
                          │  same JSON Schema   │
                          └─────────────────────┘
```

### System invariants

Four invariants hold throughout the system. First, every LLM call is logged with model version, prompt version, inputs, outputs, latency, and token counts. There is no LLM call that does not write a row to the `llm_calls` table. Second, skill specifications are immutable once persisted. A new "version" is always a new row in `skill_versions`, never an update to an existing row. Third, every extracted rule carries one or more resolvable citations into the source document — character-offset spans plus the quoted text. A rule with no valid citation is a probable hallucination and must be repaired or dropped; citation resolution rate is a CI-blocking metric. Fourth, the eval harness runs in CI on every pull request against a held-out test set, with regressions on primary metrics blocking merge.

## 4. Core abstractions and data model

### The Skill primitive

A Skill is the central abstraction. It represents the structured, versioned, machine-executable encoding of a company's decision logic for a workflow. The schema is defined in JSON Schema in the canonical `schemas/` directory and codegen produces both Pydantic models and Zod schemas.

A Skill has metadata (name, owner, version, created_at), a trigger (what initiates the workflow), an inputs declaration (what data is available), and three decision zones: deterministic rules that can be evaluated programmatically, LLM-assisted rules where the model interprets context and recommends an action requiring human approval, and human-only rules where the agent prepares a case and escalates. It also has audit requirements (what must be logged when this skill executes) and permissions (data access, allowed actions, restricted actions).

A simplified shape, with full schema in Appendix A:

```yaml
skill_name: process_refund_request
owner: finance_ops
version: 1
trigger: customer_requests_refund
inputs:
  - name: refund_amount
    type: number
  - name: purchase_days_ago
    type: integer
  - name: fraud_flags
    type: array
decision_zones:
  deterministic:
    - condition:
        all:
          - { field: purchase_days_ago, op: lte, value: 30 }
          - { field: refund_amount, op: lte, value: 100 }
          - { field: fraud_flags, op: empty }
      action: approve_refund
  llm_assisted:
    - condition:
        any:
          - { field: refund_reason, op: contains, value: goodwill }
      action: draft_recommendation
      requires_human_approval: true
  human_only:
    - condition:
        all:
          - { field: refund_amount, op: gt, value: 500 }
      action: escalate_to_finance
audit_requirements:
  - log_reason
  - store_policy_reference
```

### The Rule predicate language

The deterministic and LLM-assisted zones use a small predicate language for conditions. The grammar is intentionally constrained — only `all`/`any` composition, only a fixed set of operators (`eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `in`, `not_in`, `contains`, `empty`, `not_empty`). This keeps the evaluator small and auditable.

The choice to invent a constrained predicate language rather than embedding Python expressions or JSONLogic is deliberate. A constrained language is easier to validate, easier to display in a UI for human review, and easier for an LLM to generate correctly. JSONLogic was considered but rejected because it's verbose for the shape of conditions we need. Python `eval` was rejected because it's a security disaster and unauditable.

### Source citations

Every extracted rule carries one or more citations into the source policy: character-offset spans (`start`, `end`) plus the quoted text captured at extraction time. Citations are a schema-level requirement, not optional metadata — a rule without at least one citation fails validation.

Citations serve three purposes. They are the anti-hallucination mechanism: a rule whose citation does not resolve to real text in the source document is a fabrication by definition, and the assembly pass rejects it. They are the evidence the review UI displays, so a human approving a threshold sees the sentence it came from. And they create a mechanically checkable eval metric — citation resolution rate — that catches extraction drift without additional human labeling.

### The Ticket primitive

A Ticket represents one historical (or synthetic) refund/credit/billing case. It has a fixed schema with fields for amount, days since purchase, customer segment, fraud indicators, refund reason, and a ground-truth human decision. For synthetic tickets, the ground truth is produced by the shadow policy described in Section 5.4 — the decision a real team following its informal rules would have made, which may deliberately diverge from the written policy.

### The SimulationReport primitive

A SimulationReport is the structured output of running a Skill against a batch of Tickets. It aggregates per-ticket results into summary metrics: match rate against historical decisions, escalation accuracy, count of policy/practice contradictions detected, count of cases auto-approvable under the skill, estimated automation potential. It also retains per-ticket detail so the UI can drill down into specific cases.

### Database schema

The Postgres schema is normalized but uses JSONB for the flexible payloads (skill spec, simulation results, LLM responses):

```sql
-- Policies as uploaded by the user
CREATE TABLE policies (
  id UUID PRIMARY KEY,
  source_filename TEXT,
  raw_text TEXT NOT NULL,
  uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Skill identity (the "concept" of a skill)
CREATE TABLE skills (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  owner TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  current_version_id UUID  -- FK to skill_versions
);

-- Skill versions (immutable)
CREATE TABLE skill_versions (
  id UUID PRIMARY KEY,
  skill_id UUID NOT NULL REFERENCES skills(id),
  version_number INT NOT NULL,
  spec JSONB NOT NULL,
  parent_version_id UUID REFERENCES skill_versions(id),
  source_policy_id UUID REFERENCES policies(id),
  status TEXT NOT NULL,  -- 'draft' | 'approved' | 'archived'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (skill_id, version_number)
);

-- Simulation runs
CREATE TABLE simulation_runs (
  id UUID PRIMARY KEY,
  skill_version_id UUID NOT NULL REFERENCES skill_versions(id),
  ticket_batch_id UUID NOT NULL,
  status TEXT NOT NULL,  -- 'pending' | 'running' | 'completed' | 'failed'
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  summary JSONB  -- SimulationReport summary
);

-- Per-ticket simulation results
CREATE TABLE simulation_results (
  id UUID PRIMARY KEY,
  run_id UUID NOT NULL REFERENCES simulation_runs(id),
  ticket_id UUID NOT NULL,
  ticket_data JSONB NOT NULL,
  decision TEXT NOT NULL,
  zone TEXT NOT NULL,  -- 'deterministic' | 'llm_assisted' | 'human_only'
  matched_human_decision BOOLEAN,
  reasoning TEXT,
  llm_call_id UUID REFERENCES llm_calls(id)
);

-- LLM call log
CREATE TABLE llm_calls (
  id UUID PRIMARY KEY,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  prompt_text TEXT NOT NULL,
  response_text TEXT NOT NULL,
  input_tokens INT,
  output_tokens INT,
  latency_ms INT,
  cost_estimate_usd NUMERIC(10, 6),
  called_at TIMESTAMPTZ DEFAULT NOW()
);

-- LLM response cache (temperature-0 calls)
CREATE TABLE llm_cache (
  cache_key TEXT PRIMARY KEY,  -- sha256(provider|model|prompt_version|prompt)
  response_text TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Background job tracking
CREATE TABLE jobs (
  id UUID PRIMARY KEY,
  kind TEXT NOT NULL,  -- 'extract' | 'simulate'
  status TEXT NOT NULL,  -- 'pending' | 'running' | 'completed' | 'failed'
  payload JSONB,
  result_ref UUID,  -- ID of the resulting skill_version or simulation_run
  error TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

-- Eval run history (for tracking regression)
CREATE TABLE eval_runs (
  id UUID PRIMARY KEY,
  commit_sha TEXT NOT NULL,
  dataset_version TEXT NOT NULL,
  model TEXT NOT NULL,
  metrics JSONB NOT NULL,
  ran_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 5. Component design

### 5.1 Schemas as source of truth

All cross-language data shapes are defined as JSON Schema in `schemas/`. Codegen scripts produce typed bindings for Python (Pydantic v2 via `datamodel-code-generator`) and TypeScript (Zod via `json-schema-to-zod`). The codegen is run via `make codegen` and the outputs are committed — this is deliberate so that diffs in generated code are visible in code review.

Source files: `schemas/skill.schema.json`, `schemas/rule.schema.json`, `schemas/ticket.schema.json`, `schemas/simulation_report.schema.json`.

When a schema changes, both Python and TypeScript code that uses the affected type breaks at compile time until the codegen is re-run and dependent code is updated. This is exactly the discipline you want.

### 5.2 LLM client

The LLM client is a thin abstraction over provider-specific SDKs. The interface:

```python
from typing import Protocol, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMClient(Protocol):
    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        model: str,
        prompt_version: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> StructuredResponse[T]:
        """Generate output constrained to the given Pydantic schema.

        Logs the call to llm_calls before returning. Retries on schema
        validation failure up to N times with feedback.
        """
        ...
```

The Anthropic implementation uses tool-use mode to enforce structure: the Pydantic schema is converted to a JSON Schema, presented to Claude as a single tool, and Claude's tool-use output is the structured response. Validation happens via Pydantic on receipt; if validation fails, the loop retries with the validation error fed back to the model. The retry budget is 3 attempts before raising.

The provider abstraction is implemented but only Anthropic is implemented for now. Adding OpenAI later is a one-file change.

Every call writes a row to `llm_calls`. The `llm_call_id` is returned in `StructuredResponse.metadata` so downstream code (simulation results, extraction outputs) can foreign-key to the originating call for full traceability.

The client also maintains a response cache in Postgres keyed on `(provider, model, prompt_version, sha256(prompt))`. Cache hits skip the API call and are logged with `cached=true`. Temperature-0 calls are cacheable by default, with per-call bypass for sampling experiments. This makes eval re-runs nearly free, makes CI reproducible for unchanged prompts, and cuts iteration cost during prompt development substantially.

### 5.3 Extraction pipeline

Extraction is a multi-pass pipeline:

**Pass 1 — segmentation.** The raw policy text is segmented into logical sections (eligibility, thresholds, approvals, exceptions, refund methods, audit requirements). A small Claude call with structured output produces the segments. This pass keeps the heavy extraction passes focused on the right text and improves quality on long policies.

**Pass 2 — rule extraction.** For each segment, an extraction prompt produces candidate rules in the constrained predicate language. Different segments use different prompts (eligibility rules vs. threshold rules vs. exception rules) because the structures differ enough that a single uber-prompt degrades quality. Each rule must include citations: character-offset spans into the segment plus the quoted text, identifying exactly which sentences the rule was derived from.

**Pass 3 — decision zone assignment.** A classifier prompt takes each candidate rule and assigns it to the deterministic, LLM-assisted, or human-only zone based on whether it's mechanically evaluable, requires interpretation, or is too high-stakes for automation.

**Pass 4 — assembly and validation.** The assembled Skill is validated against the JSON Schema, and every citation is resolved against the source document: the quoted text must appear at (or within a small tolerance of) the claimed offsets. A rule with an unresolvable citation is treated as a probable hallucination and either repaired or dropped with a logged warning. If schema validation fails, the failure is fed back to a repair prompt that asks the model to fix the specific violation. Up to 2 repair attempts before failing the extraction.

The extraction output is stored as a new row in `skill_versions` with `status='draft'`. Human review (or in the demo, just user click-through) promotes it to `status='approved'`.

### 5.4 Simulation engine

Given an approved skill version and a batch of tickets, the simulation engine runs each ticket through the skill's decision zones:

1. Check deterministic rules first. If any condition matches, record the deterministic decision and stop.
2. If no deterministic rule matched, check LLM-assisted rules. If a condition matches, invoke the LLM to interpret context and produce a recommendation. The recommendation is recorded with `requires_human_approval=true`.
3. If no rule matched at all, the ticket is escalated to human-only.

Each ticket produces a `simulation_results` row capturing the decision, zone, reasoning, and (if LLM was invoked) the `llm_call_id`.

After all tickets are processed, the aggregator computes the SimulationReport: match rate (decisions matching the ticket's `ground_truth_decision`), escalation accuracy (escalations that were correctly escalated vs. cases that should have been escalated but weren't), and detected contradictions.

**Shadow-policy synthetic data.** A naive generator would produce tickets from the same policy the skill was extracted from — which makes the simulation circular: match rate would measure the model's self-consistency, and contradiction detection would have nothing to find. Instead, the generator works from a *shadow policy*: the written policy plus a hidden layer of informal rules that mimic how real teams actually behave. Examples: VIP customers get exceptions the policy doesn't allow, refunds slightly above the threshold get quietly approved, holiday-season cases get extra leniency. The shadow policy is authored per corpus policy as a structured divergence spec (which rules diverge, under what conditions, at what frequency), and ground-truth decisions come from the shadow policy, not the written one.

This turns contradiction detection into a measurable problem. The divergence spec is known ground truth: the detector's job is to recover it from ticket outcomes alone. That yields real precision (of flagged contradictions, how many are genuine planted divergences) and recall (of planted divergences, how many were flagged) — the first quantitative footing for the system's flagship feature.

**Contradiction detection.** The detector groups per-ticket results by feature clusters (amount band, customer segment, reason category, time window), computes the divergence rate between the skill's decision and the ground truth within each cluster, and flags clusters whose divergence exceeds a threshold with statistical support (minimum cluster size, binomial test against the base error rate). Each flagged contradiction carries: the written rule (with its citation), the observed behavior pattern, frequency, affected segment, and an estimated financial impact.

### 5.5 Storage layer

Postgres 16 via SQLAlchemy 2.x with Alembic migrations. JSONB columns for flexible payloads (skill specs, simulation summaries, LLM responses). UUID primary keys throughout. All timestamps as `TIMESTAMPTZ`.

Connection pooling via SQLAlchemy's default pool, sized to 10 connections. For local dev, Docker Compose spins up Postgres; the connection string comes from `DATABASE_URL` env var. In production (Render), the managed Postgres connection string is injected via env.

### 5.6 API layer

FastAPI 0.115+ with Pydantic v2. Routes are organized by resource:

```
POST   /policies                        # Upload a policy document
GET    /policies/{id}                   # Retrieve a policy
POST   /skills/extract                  # Kick off extraction (async)
GET    /skills                          # List skills
GET    /skills/{id}                     # Get current version of a skill
GET    /skills/{id}/versions            # List versions of a skill
POST   /skills/{id}/versions/{ver}/approve  # Promote version to 'approved'
POST   /tickets/import                  # Import a ticket batch from CSV (A4)
POST   /simulations                     # Start a simulation run (async)
GET    /simulations/{id}                # Get simulation status + summary
GET    /simulations/{id}/report         # Get full SimulationReport
GET    /simulations/{id}/report.html    # Get rendered HTML report (A2)
POST   /cross-document-contradictions   # Detect cross-document policy conflicts (A3)
POST   /eval-runs                       # Record an eval run's metrics
GET    /eval-runs                       # List eval run history (filter by model/commit_sha)
GET    /jobs/{id}                       # Poll a background job's status
```

Authentication is a single API key passed in the `Authorization: Bearer <key>` header. The key is hardcoded in env for the demo — this is fine because the deployed instance is for demonstration only.

Errors use a consistent envelope: `{"error": {"code": "...", "message": "...", "details": {...}}}`. Pydantic validation errors are translated into 400s with field-level detail.

`POST /policies` accepts `{"raw_text": str, "source_filename": str | null}` and returns the persisted `{id, source_filename, raw_text, uploaded_at}` policy. `GET /policies/{id}` returns that same policy payload.

`POST /skills/extract` accepts the skill metadata plus either inline `policy_text` or a previously uploaded `policy_id`. Inline policy text remains supported for existing clients; supplying a policy ID reuses that persisted source document for the immutable extracted skill version.

### 5.7 Background jobs

Long-running operations (extraction, simulation) are async. The pattern:

1. Client POSTs to `/skills/extract` or `/simulations`.
2. The endpoint creates a `jobs` row with `status='pending'`, kicks off a `BackgroundTasks` task, returns `{job_id, status: 'pending'}` with 202 Accepted.
3. The background task updates the `jobs` row to `status='running'`, does the work, writes the result, updates the job to `status='completed'` with `result_ref` pointing at the resulting skill version or simulation run.
4. Client polls `GET /jobs/{id}` until status is `completed` or `failed`.

This uses FastAPI's `BackgroundTasks` rather than Celery or Temporal. The tradeoff is acknowledged: if the API process restarts mid-job, the job is lost (the row stays `running` forever). For this version of the system this is acceptable, and the README explicitly notes the limitation along with the upgrade path (move to a real queue) when it becomes a problem.

### 5.8 TypeScript SDK

The TypeScript SDK is a thin, well-typed wrapper over the REST API:

```typescript
import { SkiljoClient } from "@skiljo/sdk";

const client = new SkiljoClient({ apiKey: process.env.SKILJO_API_KEY });

const policy = await client.policies.upload({ text: policyText });
const job = await client.skills.extract({ policyId: policy.id });
const skill = await client.jobs.waitForCompletion(job.id);
const simulation = await client.simulations.create({
  skillVersionId: skill.versionId,
  tickets: ticketBatch,
});
const report = await client.simulations.getReport(simulation.id);
```

Built with TypeScript 5.4+, no runtime dependencies beyond Zod (for response validation) and a fetch wrapper. Bundled with `tsup` to dual ESM/CJS. Tested with Vitest against a mocked API.

The SDK is structured as a publishable npm package. Whether it's actually published to a registry depends on whether the system has external consumers; in v1 it lives in the monorepo and is consumed by integration tests.

### 5.9 Streamlit demo

Three pages, navigated via Streamlit's multi-page app feature:

**Page 1 — Extract.** User uploads a policy document (file upload or paste). On submit, calls `POST /skills/extract`, polls the job, displays the extracted skill in a readable format (collapsible YAML, with rules grouped by zone). Shows the LLM calls behind the extraction in a "developer details" expander.

**Page 2 — Review.** User reviews the extracted skill, can mark rules as accepted/rejected, can promote the version to `approved`. This is intentionally minimal — the point is to demonstrate the workflow, not build a real review UI.

**Page 3 — Simulate.** User picks an approved skill, picks a ticket batch (synthetic batches are pre-loaded; a CSV upload widget creates a new batch via A4's import endpoint), runs simulation, sees the report rendered with match rate, breakdown by zone, contradiction list, and a sortable table of per-ticket outcomes.

Styled with Streamlit's defaults plus minimal custom CSS. No attempt to look like a polished product — it looks like a working tool, which is appropriate for the audience.

### 5.10 Eval harness

Built on Inspect (Anthropic's open-source eval framework). The eval dataset is in `data/eval/` split into train, dev, and test directories. Each example is a JSON file with a policy text, the ground-truth Skill spec, and (for end-to-end evals) a batch of tickets with ground-truth decisions.

Three eval suites:

**Extraction eval.** Runs the extraction pipeline against the labeled examples and measures field-level precision/recall for: detected thresholds (numerical accuracy within ±10%), detected conditions (structural match), zone assignment (categorical accuracy), and end-to-end schema validity.

**Simulation eval.** Runs the simulation engine against known-good skills with known-good tickets and measures match rate against the ground truth decisions.

**End-to-end eval.** Combines both: extract a skill from a policy, simulate it against tickets, measure how often the final decision matches the ground truth.

The harness runs in CI on every PR via `.github/workflows/eval.yml`. Metrics are compared against the previous commit's metrics; a regression on any primary metric (extraction recall, simulation match rate) blocks merge. Results are stored in `eval_runs` so historical metric trends are visible.

The test set is kept in `data/eval/test/` with a CODEOWNERS rule and a `.gitattributes` note that it should not be examined during development to prevent overfitting. This is mostly social hygiene rather than enforcement, but it's the right discipline.

### 5.11 Cross-document contradiction detection

Companies rarely have one policy document — they have a ToS, a refund help-center page, a support macro, and a pricing FAQ, written by different teams at different times. These documents contradict each other more often than any of them contradicts behavior. The corpus contains a live example: Shopify's Terms of Service state that refunds are not allowed, while its help center documents time-window-based eligibility for case-by-case review.

Cross-document detection runs entirely on extraction output — no ticket data required. Given N documents from the same company, the system extracts a skill from each, aligns rules that govern the same decision surface (same trigger, overlapping conditions), and flags pairs whose actions or thresholds disagree. Alignment is LLM-assisted (a comparison prompt over rule pairs with citations); conflict verification is mechanical (the predicate structures either conflict or they don't).

This matters for two reasons. It's the highest-value output per unit of customer friction — a customer supplies two URLs and gets findings, with no data export, no integration, and no trust barrier. And it's the engine behind the self-serve consistency checker described in Section 14 (v1.05), the first monetizable artifact on the roadmap.

### 5.12 Report rendering

The SimulationReport and the contradiction findings compile to a rendered artifact — a standalone HTML document (print-friendly for PDF) with the summary metrics, the contradiction list with citations and evidence, and a per-ticket appendix. The BRD identifies this report as the first sellable deliverable; the system treats it accordingly, as a first-class output rather than a JSON payload someone else must make presentable.

Rendering is a Jinja2 template over the report data — deliberately boring technology. No charting library in v1; tables and typography carry it. The Streamlit demo links to the rendered artifact.

#### `GET /simulations/{id}/report.html`

Returns the standalone diagnostic report for a completed simulation.

- **Response:** `200 text/html; charset=utf-8` with a complete printable HTML document. CSS is inlined and the document has no external resources.
- **Content:** executive summary, contradiction evidence and citations, automation and ROI analysis, and a per-ticket appendix.
- **Errors:** `404` when the simulation does not exist; `409` when it has not completed.

## 6. Key design decisions

This section captures the decisions where alternatives were seriously considered. For each, the chosen path, what was considered, and why.

### Polyglot architecture with Python primary

**Chosen:** Python for extraction, simulation, API, and demo. TypeScript for client SDK only.

**Alternatives considered:** Pure Python (simpler but limits who can consume the system); pure TypeScript (the LLM eval ecosystem in TS is meaningfully weaker than Python's); Python backend with Next.js frontend (more frontend work for the lowest-leverage component).

**Why:** The system's intended downstream consumers are AI agents and agent frameworks, and the agent ecosystem is overwhelmingly TypeScript — the Anthropic Claude Agent SDK, Vercel AI SDK, OpenAI's official SDK, and most agent platform integrations ship TS-first. A typed TypeScript client is the natural integration surface, not a stretch goal. Python wins for the core because that's where the LLM, eval, and structured-output tooling lives. The split mirrors how Stripe, Anthropic, and OpenAI ship their own products: Python and TypeScript SDKs over a single canonical API.

### Schema-first with codegen

**Chosen:** JSON Schema as canonical, Pydantic and Zod generated from it.

**Alternatives considered:** Pydantic as canonical with TS types generated from it (works but couples the canonical definition to a specific Python version); separate hand-written schemas in each language (drifts immediately); Protobuf (overkill, adds tooling burden).

**Why:** JSON Schema is the lingua franca for LLM structured outputs (Anthropic tool use, OpenAI structured outputs, JSON Schema directly). Having it as the source of truth means the schemas used by the LLM are the same schemas the application enforces.

### Constrained predicate DSL for rules

**Chosen:** Small custom predicate language with `all`/`any` composition and a fixed operator set.

**Alternatives considered:** JSONLogic (verbose for our shape); embedded Python (security disaster); Common Expression Language / CEL (heavyweight, JVM-flavored); a real rule engine like Drools (massive overkill).

**Why:** The DSL has to be (a) easy for an LLM to generate correctly, (b) easy to render in a UI for human review, (c) safely evaluable. A small custom language wins on all three.

### Anthropic tool-use for structured output

**Chosen:** Anthropic's tool-use API with a single tool whose input schema is the desired output schema.

**Alternatives considered:** Free-form generation + JSON parsing + retries (fragile); OpenAI structured outputs (locks in to OpenAI); Outlines / constrained generation (requires self-hosted models); DSPy (interesting but heavy abstraction for a 6-week build).

**Why:** Tool-use is Anthropic's most reliable structured-output mechanism, gives the model the full reasoning surface, and the schema is reusable across languages. The retry-with-validation-feedback pattern handles the edge cases.

### Postgres with JSONB rather than a document database

**Chosen:** Postgres 16 with JSONB columns for flexible payloads.

**Alternatives considered:** MongoDB (poor querying story for the relational parts); SQLite (doesn't signal production); separate document store for skills + relational for everything else (overcomplicated).

**Why:** Postgres + JSONB gives you the best of both worlds — full relational integrity for the parts that need it (foreign keys, transactions), flexible storage for the parts that don't (skill specs, LLM responses). It's also what 90% of production AI systems actually use.

### FastAPI BackgroundTasks instead of Celery

**Chosen:** FastAPI's built-in `BackgroundTasks` with job state in Postgres.

**Alternatives considered:** Celery with Redis (heavier, more moving parts, more impressive on a resume but overengineered here); Temporal (workflow engine; way overkill); RQ (Redis Queue; better than Celery but still extra infra); synchronous-only (cheaper but the demo loses the "watch this job run" experience).

**Why:** For a single-machine demo with low concurrency, BackgroundTasks is enough. The job state lives in Postgres so the database is the single source of truth. Explicitly documenting the limitation (jobs lost on restart) and the upgrade path is itself a signal of engineering maturity.

### Inspect for evals

**Chosen:** Anthropic's Inspect framework.

**Alternatives considered:** Braintrust (more polished UX, broader provider support); Weights & Biases (broader ML focus, not LLM-specific); custom eval harness (lots of work for limited benefit).

**Why:** Inspect is purpose-built for LLM evals, integrates cleanly with Anthropic's tooling, and is actively maintained. The framework is well-designed and the choice holds up on technical merits.

### uv as the Python package manager

**Chosen:** uv with workspaces.

**Alternatives considered:** Poetry (more mature, slower); pip + setuptools (older, no workspace support); Hatch (good but less momentum).

**Why:** uv is what Anthropic and most newer Python projects are adopting in 2025–2026. It's fast enough that the developer experience is materially better, and the workspace model maps cleanly to the monorepo structure.

## 7. Failure modes and observability

### LLM failure modes

The LLM is the primary source of non-determinism and the primary failure mode. Specific failures the system handles:

**Schema violation.** The model produces output that fails Pydantic validation. Handled by the retry loop in the LLM client — up to 3 attempts with the validation error fed back. If all retries fail, the extraction fails and the job is marked failed with the validation error preserved.

**Refusal or empty output.** The model refuses to extract (rare with policy text but possible) or produces an empty response. Detected by the LLM client; treated as a non-retryable failure with the response logged.

**Hallucinated content.** The model invents thresholds or conditions not present in the source policy. The primary defense is citation resolution in Pass 4: a rule whose quoted text does not appear at or near the claimed character offsets in the source document fails assembly and is either repaired or dropped. The eval harness measures citation resolution rate as a CI-blocking metric (must stay at 100%). At runtime, the human review step shows each rule alongside its source citation, so an approver can verify the provenance of every threshold.

**Token limit exceeded.** The model produces output that hits the max_tokens limit and is truncated. Detected via the `stop_reason` field on the response; treated as a retryable failure with a higher max_tokens budget.

### System failure modes

**Database connection lost.** SQLAlchemy's connection pool handles transient failures with retries. Persistent failures bubble up as 500s with a clear error envelope.

**Background job lost on restart.** As noted, BackgroundTasks doesn't survive process restart. The `jobs` table has a `started_at` timestamp and a background sweeper could mark jobs as failed if they've been `running` for too long. This sweeper is not implemented in v1; it's noted in the README as a known limitation with a clear path to fix.

**Cost runaway.** The LLM is expensive. The system tracks `cost_estimate_usd` per call and the eval harness has a configurable budget cap that aborts the eval if it's exceeded. The Streamlit demo shows running cost so the user can see what they're spending.

### Observability

Every LLM call is logged with full inputs, outputs, model version, and cost. This is the primary observability surface. Beyond that:

- Application logs go to stderr in JSON format (using `structlog`).
- Job state changes are logged at INFO level with the job ID.
- Eval runs persist full metrics to `eval_runs` so trends are queryable.

No external observability stack (Datadog, Honeycomb) in v1. Structured logs to stderr are sufficient for the current scope and the upgrade path is straightforward when production usage justifies it.

## 8. Security and data handling

This version is single-tenant and intentionally minimal on security infrastructure. The notes here are about what's explicitly considered, what's deferred, and why.

**Authentication.** Single hardcoded API key in env, checked on every API request. Not real auth; clearly documented as a demo concession.

**API key handling.** The Anthropic API key is in `.env` (gitignored). The deployment platform's secret manager (Render's env vars) holds the production key.

**PII in policy documents.** Policy documents may contain employee names, internal email addresses, or other PII. The system stores them verbatim in `policies.raw_text`. For the demo, this is fine because the policies used are either public documents or synthetic. A production version would need a PII redaction pass before storage.

**LLM data residency.** Anthropic's API does not train on data passed via the API by default. This is noted in documentation.

**SQL injection.** SQLAlchemy parameterized queries throughout; no raw SQL with string interpolation.

## 9. Testing and evaluation strategy

### Unit tests

Standard unit tests with pytest for the extraction pipeline (mocking the LLM client), the simulation engine (using fixed skill + ticket inputs), the rule evaluator (table-driven tests of the predicate language), and the storage layer (against a test Postgres instance via Docker Compose).

Test coverage target: 70%+ on the core package. Not measured in CI but checked locally before commits.

### Integration tests

A small set of integration tests that exercise the full FastAPI app against a test database. Tests the API contract (request shapes, response shapes, status codes) and the database side effects.

### Eval-based tests (the important ones)

The eval harness is where the real testing happens. Three suites:

**Extraction precision/recall.** Per-field metrics on extracted vs. ground-truth Skills.

**Simulation match rate.** How often the simulation's decision matches the ground-truth human decision in the synthetic dataset.

**End-to-end.** Full policy → extract → simulate flow, measuring final decision accuracy.

Datasets:

- Training set (`data/eval/train/`): 30 examples, used freely during development for iteration.
- Dev set (`data/eval/dev/`): 15 examples, used to validate changes before opening a PR.
- Test set (`data/eval/test/`): 15 examples, only run in CI on PRs and never examined manually.

Regression thresholds: extraction recall must not drop more than 2 percentage points, citation resolution rate must stay at 100% (any rule with an unresolvable citation is a broken build), contradiction recall must not drop more than 5 percentage points, simulation match rate must not drop more than 3 points, end-to-end accuracy must not drop more than 3 points. Hitting any of these blocks merge.

## 10. Deployment

### Local development

`docker-compose up -d postgres` starts Postgres. `uv sync` installs all Python dependencies across workspaces. `make setup` runs migrations and codegen. `make api` starts FastAPI on port 8000. `make demo` starts Streamlit on port 8501. The Streamlit demo is configured to talk to the local API by default.

### Production deployment

Render.com is the deployment target. Two services:

- **Web service** (FastAPI backend) — `api` workspace, Python 3.12, command `uvicorn skiljo_api.main:app --host 0.0.0.0 --port $PORT`.
- **Streamlit service** — `demo` workspace, Python 3.12, command `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`.

Managed Postgres on Render's free tier (sufficient for the demo's load).

Environment variables: `DATABASE_URL`, `ANTHROPIC_API_KEY`, `API_KEY` (the inbound auth key), `LOG_LEVEL`.

Estimated cost: $7/month for the web service, $7 for Streamlit, $7 for Postgres = ~$21/month.

## 11. Build plan (week-by-week)

### Week 1 — Foundations

By end of week 1, the system has a working monorepo, the canonical JSON schemas and their generated Pydantic/Zod types, a Postgres database with the initial schema applied, a FastAPI skeleton serving a health check, and a CI pipeline running lint, typecheck, and tests on every push. The infrastructure that the rest of the project depends on is in place and verified.

**Deliverables:** Working monorepo with `core`, `api`, `demo`, `sdk-ts` packages. JSON Schemas for Skill, Rule, Ticket, SimulationReport. Codegen producing Pydantic and Zod types. Docker Compose with Postgres. Makefile with `setup`, `codegen`, `test`, `api`, `demo` targets. GitHub Actions CI running lint, typecheck, and tests on every push. README with architecture overview.

**Risk to manage:** It's tempting to start building extraction immediately. Don't. The schema and codegen pipeline is the most important infrastructure in the project and it must be right before anything else gets built on top of it.

### Week 2 — Extraction pipeline

By end of week 2, the system can accept a real refund or credit policy document and produce a schema-valid Skill spec, persisted as an immutable version row. This includes the LLM client abstraction, the multi-pass extraction pipeline, schema validation with retry, and the first 20 hand-labeled examples for the eval set.

**Deliverables:** LLM client with Anthropic implementation and call logging. Four-pass extraction pipeline (segment, extract, classify zones, assemble). Pydantic validation with retry. POST `/skills/extract` endpoint with background job execution. 20 hand-labeled policy-to-skill examples in `data/eval/train/`. First Inspect eval running locally with extraction precision/recall metrics.

**Risk to manage:** Hand-labeling is tedious and you'll want to skip it. Don't. The eval data is the single most valuable artifact of this project — the labeled examples are what let you actually measure quality.

### Week 3 — Simulation engine

By end of week 3, the system can take an extracted skill and a batch of tickets, run each ticket through the skill's decision zones, and produce a SimulationReport with match rate, escalation accuracy, and detected contradictions. This includes the synthetic ticket generator, the rule evaluator for deterministic zones, the LLM-assisted zone executor, the contradiction detector, and the simulation API.

**Deliverables:** Shadow-policy ticket generator producing realistic refund/credit cases with ground-truth decisions authored against the shadow policy (not the written policy), covering all expected decision paths with planted divergences. Rule evaluator for the predicate language. Per-zone executors. SimulationReport aggregation. Contradiction detection with precision/recall against planted divergences. POST `/simulations` and GET `/simulations/{id}/report` endpoints. 100 synthetic tickets covering the eligibility surface. Unit tests for the simulation engine.

**Risk to manage:** The shadow-policy ticket generator is load-bearing — read the shadow-policy design in Section 5.4 before starting. Generating tickets from the written policy is circular and makes contradiction detection unverifiable. The shadow policy + divergence spec is what gives the contradiction detector measurable ground truth.

### Week 4 — Demo UI, SDK, integration

By end of week 4, a user can run the full flow end-to-end: upload a policy through the Streamlit UI, watch extraction complete, review and approve the extracted skill, kick off a simulation, and view the resulting report. The TypeScript SDK exposes the same flow programmatically and is tested against the API. The polyglot integration path is real, not aspirational.

**Deliverables:** Streamlit app with three pages (extract, review, simulate). TypeScript SDK with types generated from JSON Schema, basic methods for upload/extract/poll/simulate, Vitest tests. End-to-end integration test that exercises the full flow. README sections for the demo and SDK.

**Risk to manage:** Don't over-invest in Streamlit UI polish. The interface needs to be usable for the three flows; visual refinement beyond that is wasted effort that could go into eval quality.

### Week 5 — Eval expansion and quality

By end of week 5, the system has a held-out test set of 15 examples that runs in CI on every PR and blocks merge on regression, with quality bugs surfaced by expanded labeling fixed in train and dev. The system has moved from "works on the happy path" to "handles edge cases responsibly."

**Deliverables:** Eval dataset expanded to 60 examples (30 train, 15 dev, 15 test). Train/dev/test split with held-out test set. CI workflow that runs the eval on every PR and blocks merge on regression. Per-field metric breakdown in eval output. Bug fixes for the failure modes surfaced by the expanded eval. Documentation: `docs/extraction.md`, `docs/simulation.md`, `docs/evals.md`.

**Risk to manage:** You will discover the system is worse than you thought when the eval expands. This is the entire point. Resist the urge to game the metrics by tuning prompts to the test set — only use train and dev for iteration.

### Week 6 — Deploy and documentation

By end of week 6, the system is deployed and accessible at a public URL, with documentation that explains the architecture, the design choices, and how to extend it. The repo state is the v1.0 release.

**Deliverables:** `render.yaml` and deployment configured. Live deployed URL. Comprehensive README with architecture diagram, demo link, and clear explanation of the system. `ARCHITECTURE.md` deep-dive. Documentation blog post draft (1500–2500 words) on the extraction architecture. 4-minute demo video for documentation walking through the system.

**Risk to manage:** Deployment always takes longer than expected. Start it on Monday of week 6 so debugging time is available.

### The revenue thread running through the build

Commits A2 (rendered report) and A3 (cross-document contradiction) are the v1.05 product minus a payment flow. Every other commit in weeks 1–4 is infrastructure for them. Hold A2 and A3 to product-grade quality on output, error handling, and presentation — they are not internal tools. Published teardown posts drive distribution during the build: teardown #1 from extraction output during week 3, teardown #2 from A3's Shopify finding during week 6. If asked to generate teardown material, source it from real extraction runs against corpus policies — never fabricated findings.

## 12. Commit-level breakdown

Each commit below should be atomic, leave the repo in a working state, and pass CI. Conventional commit prefixes (`feat`, `chore`, `docs`, `test`, `fix`, `refactor`, `data`) are used throughout. Commit messages should follow the form `<type>(<scope>): <summary>`.

### Week 1

1. `chore: initialize repo with uv workspaces and pnpm workspace`
   Creates root `pyproject.toml` with workspace config, `package.json` with pnpm workspace, `.gitignore`, MIT license, empty README.
   *Acceptance:* `uv sync` and `pnpm install` run cleanly at the root.

2. `chore: add Python package skeletons (core, api, demo)`
   Creates `packages/core/`, `packages/api/`, `packages/demo/` each with `pyproject.toml`, `src/<name>/__init__.py`, and minimal README.
   *Acceptance:* Each package has its own dependencies resolvable via uv.

3. `chore: add TypeScript SDK skeleton`
   Creates `packages/sdk-ts/` with `package.json`, `tsconfig.json`, `src/index.ts`, Vitest config.
   *Acceptance:* `pnpm --filter @skiljo/sdk build` produces a dist/ directory.

4. `chore: docker-compose with Postgres 16`
   Adds `docker-compose.yml` defining a Postgres 16 service with a named volume. Adds `.env.example` documenting `DATABASE_URL`.
   *Acceptance:* `docker-compose up -d postgres` starts a healthy Postgres instance.

5. `chore: Makefile with common dev tasks`
   Adds top-level `Makefile` with targets: `setup`, `codegen`, `test`, `lint`, `typecheck`, `api`, `demo`, `migrate`, `clean`.
   *Acceptance:* `make help` lists all targets with descriptions.

6. `feat(schemas): define skill.schema.json and rule.schema.json`
   Adds `schemas/skill.schema.json` and `schemas/rule.schema.json` with full structural definitions for the Skill primitive and the predicate DSL.
   *Acceptance:* JSON Schemas validate against the JSON Schema meta-schema.

7. `feat(schemas): define ticket.schema.json and simulation_report.schema.json`
   Adds `schemas/ticket.schema.json` and `schemas/simulation_report.schema.json`.
   *Acceptance:* All four schemas pass `ajv compile`.

8. `feat(schemas): Pydantic codegen via datamodel-code-generator`
   Adds `schemas/codegen/generate_pydantic.py`. Outputs into `packages/core/src/skiljo_core/schemas/`. Wired into `make codegen`.
   *Acceptance:* `make codegen` produces importable Pydantic models that match the schemas.

9. `feat(schemas): Zod codegen via json-schema-to-zod`
   Adds `schemas/codegen/generate_zod.ts`. Outputs into `packages/sdk-ts/src/types.ts`.
   *Acceptance:* `make codegen` produces Zod schemas that parse valid example data.

10. `feat(api): FastAPI skeleton with /health endpoint`
    Adds minimal FastAPI app in `packages/api/src/skiljo_api/main.py` with `/health` returning `{"status": "ok"}`. Configured to read `DATABASE_URL` from env.
    *Acceptance:* `make api` starts the server; `curl localhost:8000/health` returns 200.

11. `feat(db): SQLAlchemy models and Alembic setup`
    Adds SQLAlchemy 2.x models for `policies`, `skills`, `skill_versions`, `simulation_runs`, `simulation_results`, `llm_calls`, `jobs`, `eval_runs`. Configures Alembic and generates the initial migration.
    *Acceptance:* `make migrate` applies the migration cleanly against the Docker Postgres.

12. `chore: GitHub Actions CI for lint, typecheck, test`
    Adds `.github/workflows/ci.yml` running ruff (lint), mypy (Python typecheck), tsc (TS typecheck), pytest, and vitest on every push.
    *Acceptance:* CI passes on a clean main branch.

13. `docs: README with architecture overview and setup instructions`
    Writes the top-level README explaining what the project is, the architecture (with the component diagram), and how to run it locally.
    *Acceptance:* A reader unfamiliar with the project can clone and run `make setup && make api` successfully following only the README.

### Week 2

14. `feat(core): LLM client protocol and Anthropic implementation`
    Defines the `LLMClient` Protocol in `packages/core/src/skiljo_core/llm/base.py`. Implements `AnthropicClient` using the official anthropic SDK with tool-use mode.
    *Acceptance:* A unit test calls the client with a trivial Pydantic schema and gets back validated output.

15. `feat(core): structured output via tool-use with validation retry`
    Adds the retry loop: validation error → feedback into next attempt, max 3 attempts. Logs each attempt.
    *Acceptance:* A unit test forces the model to produce invalid output on the first attempt (via prompt injection) and verifies retry succeeds.

16. `feat(core): LLM call logging to Postgres`
    Adds `LLMCallLogger` that writes every call to `llm_calls`. Wired into `AnthropicClient`.
    *Acceptance:* After a test LLM call, `SELECT COUNT(*) FROM llm_calls` returns 1 with all expected fields populated.

17. `feat(core): extraction pass 1 — policy segmentation`
    Adds the segmentation prompt and pipeline stage. Takes raw policy text, returns a list of typed segments.
    *Acceptance:* Run against a sample policy returns segments covering at least eligibility, thresholds, and exceptions.

18. `feat(core): extraction pass 2 — rule extraction per segment`
    Adds per-segment-type prompts. Outputs candidate rules in the predicate DSL.
    *Acceptance:* Given a segment about "refunds under $100 within 30 days", the extracted rule has the expected condition structure.

19. `feat(core): extraction pass 3 — decision zone classification`
    Classifies each candidate rule into deterministic, llm-assisted, or human-only.
    *Acceptance:* A rule with mechanical conditions classifies as deterministic; a "goodwill exception" rule classifies as llm-assisted.

20. `feat(core): extraction pass 4 — assembly and schema validation`
    Assembles the final Skill spec from the extracted rules. Validates against `skill.schema.json`. Includes the repair loop for schema violations.
    *Acceptance:* A full extraction run on a sample policy produces a schema-valid Skill spec.

21. `feat(api): POST /skills/extract endpoint with background job`
    Adds the endpoint. Creates a `jobs` row, kicks off extraction in a `BackgroundTasks` task, returns 202 with `job_id`.
    *Acceptance:* `curl POST` returns 202; polling `/jobs/{id}` eventually returns `completed` with `result_ref` pointing to a new `skill_version` row.

22. `feat(api): GET /jobs/{id} polling endpoint`
    Adds the polling endpoint with consistent status enum.
    *Acceptance:* End-to-end integration test passes.

23. `feat(api): GET /skills, /skills/{id}, /skills/{id}/versions endpoints`
    Adds the read endpoints for skills and their versions.
    *Acceptance:* After an extraction, the new skill and version appear in the list and detail endpoints.

24. `data: 20 hand-labeled policy-to-skill examples`
    Adds 20 examples in `data/eval/train/` — each is a policy text file plus the ground-truth Skill spec as YAML.
    *Acceptance:* All 20 examples have valid ground-truth specs that pass schema validation.

25. `test(core): unit tests for extraction pipeline`
    Adds pytest unit tests for each extraction pass, mocking the LLM client.
    *Acceptance:* `make test` passes with >70% coverage on the extraction module.

### Week 3

26. `feat(core): shadow-policy ticket generator`
    Adds the shadow-policy generator for realistic synthetic ticket batches. Accepts a written policy and a structured divergence spec (which rules diverge, under what conditions, at what frequency). Generates tickets whose ground-truth decisions follow the shadow policy, not the written policy, creating planted contradictions the detector can recover.
    *Acceptance:* Generating 50 tickets produces a varied set; at least 2 planted divergence patterns are present with the expected frequency; detector recall ≥0.8 on planted divergences with ≤1 false positive per run.

27. `feat(core): rule evaluator for deterministic zone`
    Implements the predicate DSL evaluator. Pure Python, no LLM. Comprehensive table-driven tests.
    *Acceptance:* All operators (`eq`, `neq`, `lt`, etc.) and compositions (`all`, `any`) pass their unit tests.

28. `feat(core): LLM-assisted zone executor`
    Implements the LLM-assisted zone: when matched, invokes the model with the ticket context and the rule's recommendation prompt, returns a structured recommendation.
    *Acceptance:* Given a "goodwill exception" rule and a matching ticket, the executor returns a recommendation with reasoning.

29. `feat(core): human-only zone routing`
    Implements the human-only escalation: produces a structured escalation record with reason and recommended routing.
    *Acceptance:* High-value tickets escalate with the expected payload.

30. `feat(core): single-ticket simulation engine`
    Combines the three zones in priority order. Returns a per-ticket result with decision, zone, reasoning, optional `llm_call_id`.
    *Acceptance:* A test ticket through a test skill produces a deterministic per-ticket result with all expected fields.

31. `feat(core): batch simulation with parallel execution`
    Wraps the single-ticket simulator with batching. Uses asyncio + bounded concurrency (semaphore of 5) to parallelize LLM calls.
    *Acceptance:* Simulating 100 tickets completes in <2 minutes against the live API.

32. `feat(core): SimulationReport aggregation`
    Computes match rate, escalation accuracy, zone breakdown, decision distribution. Persists to `simulation_runs.summary`.
    *Acceptance:* A batch simulation produces a SimulationReport that passes schema validation.

33. `feat(core): contradiction detection`
    Implements the detector: groups tickets by similar features, finds systematic divergences from ground truth above a 5% frequency threshold, returns a list of `Contradiction` records.
    *Acceptance:* Run against a known-contradictory skill+ticket pair, the detector flags the expected contradictions.

34. `feat(api): POST /simulations and GET /simulations/{id} endpoints`
    Adds simulation creation (async via job) and status polling.
    *Acceptance:* End-to-end: extract a skill, kick off a simulation, poll, receive the report.

35. `feat(api): GET /simulations/{id}/report endpoint`
    Returns the full report including per-ticket detail.
    *Acceptance:* Report payload matches the JSON Schema.

36. `data: 100 synthetic tickets in data/synthetic_tickets/refund_v1/`
    Generates and commits a stable batch of 100 tickets for reproducible demos and tests.
    *Acceptance:* The batch covers all expected decision paths (low-dollar, near-threshold, exception, fraud, enterprise).

37. `test(core): simulation engine tests with golden fixtures`
    Adds tests that run the simulation against known skill + ticket fixtures and verify the report matches a golden output.
    *Acceptance:* `make test` passes, including the golden-fixture comparisons.

### Week 4

38. `feat(demo): Streamlit app skeleton with three-page navigation`
    Creates `packages/demo/src/app.py` and the three page files. Sidebar nav, shared API client.
    *Acceptance:* `make demo` starts Streamlit and all three pages load.

39. `feat(demo): page 1 — upload policy and extract skill`
    File upload widget, paste-text widget, "Extract" button, job polling with progress indicator, rendered skill view.
    *Acceptance:* Uploading a sample policy and clicking extract produces a visible skill spec.

40. `feat(demo): page 2 — review and approve skill version`
    Renders the draft skill, lets the user mark rules accepted/rejected, "Approve version" button calls the approve endpoint.
    *Acceptance:* Approving a version updates the database status to `approved`.

41. `feat(demo): page 3 — run simulation and render report`
    Skill picker, ticket batch picker, "Run simulation" button, report rendered with summary cards + per-ticket sortable table.
    *Acceptance:* Running a simulation displays a complete SimulationReport with all expected sections.

42. `feat(demo): LLM call inspector (developer details expander)`
    Adds an expandable section on each page showing the LLM calls that drove the current view, including model, prompt version, cost.
    *Acceptance:* The expander shows accurate call data.

43. `feat(sdk-ts): SkiljoClient class with policies and skills methods`
    Implements `policies.upload`, `skills.extract`, `skills.get`, `jobs.get`, `jobs.waitForCompletion` in TypeScript with full type safety.
    *Acceptance:* Vitest tests using msw to mock the API all pass.

44. `feat(sdk-ts): simulations methods`
    Adds `simulations.create`, `simulations.get`, `simulations.getReport`.
    *Acceptance:* End-to-end SDK usage from the README works against the local API.

45. `docs(sdk-ts): README with usage examples and API reference`
    Documents installation, configuration, and every method with TypeScript examples.
    *Acceptance:* An engineer integrating the SDK can use it from the README without reading source.

46. `test: end-to-end integration test from upload to report`
    Adds a pytest integration test that uploads a policy, extracts a skill, runs simulation, fetches the report. Uses real API and real Anthropic calls (gated by `INTEGRATION=1` env var).
    *Acceptance:* `INTEGRATION=1 make test` passes.

47. `docs: ARCHITECTURE.md with full system deep dive`
    Writes the architecture document covering the same ground as this design doc but tightened for a code reader.
    *Acceptance:* The document compiles to readable Markdown in GitHub.

### Week 5

48. `feat(eval): Inspect harness setup with extraction eval suite`
    Adds `packages/core/src/skiljo_core/eval/` with Inspect task definitions. Implements the extraction eval scoring precision/recall by field type.
    *Acceptance:* `inspect eval skiljo_core.eval.extraction` runs against the train set and reports metrics.

49. `feat(eval): simulation eval suite`
    Adds the simulation eval that scores match rate, escalation accuracy, contradiction detection precision.
    *Acceptance:* The simulation eval runs and reports metrics.

50. `feat(eval): end-to-end eval suite`
    Combines extraction + simulation against full policy → ticket batches with ground-truth decisions.
    *Acceptance:* The E2E eval runs and reports a coherent set of metrics.

51. `data: expand labeled set to 60 examples with train/dev/test split`
    Adds 40 more examples and reorganizes into `data/eval/{train,dev,test}/`. Test set goes into a separate directory with a CODEOWNERS rule and a README warning against manual inspection.
    *Acceptance:* All 60 examples pass schema validation; split sizes are 30/15/15.

52. `ci: eval workflow that blocks merge on regression`
    Adds `.github/workflows/eval.yml` that runs the three eval suites on every PR, compares against main, and exits non-zero on regression beyond the configured thresholds.
    *Acceptance:* Opening a PR that intentionally degrades extraction quality causes CI to fail.

53. `feat(eval): persistent metric history in eval_runs table`
    Eval runs in CI write results to the database. A simple `make eval-history` command shows the trend.
    *Acceptance:* Running an eval twice produces two rows in `eval_runs`.

54. `fix: extraction quality bugs surfaced by expanded eval`
    Catch-all commit for the bugs found during eval expansion. May be multiple commits in practice; this is the one slot in the plan that absorbs unexpected work.
    *Acceptance:* Eval metrics on the dev set improve materially.

55. `docs: extraction.md, simulation.md, evals.md in docs/`
    Three focused documentation files. Each explains the design, key prompts, failure modes, and how to extend.
    *Acceptance:* The docs are readable standalone.

56. `refactor: cleanup pass on core package`
    Removes dead code, tightens types, improves error messages. Probably 200–400 lines of diff.
    *Acceptance:* `make lint typecheck test` still passes; coverage doesn't drop.

### Week 6

57. `infra: render.yaml for backend + Streamlit + Postgres`
    Adds the Render blueprint defining all three services and their env vars.
    *Acceptance:* Deploying via Render's blueprint creates the services correctly.

58. `chore: production migrations and seed data`
    Runs the initial migration against production Postgres. Optionally seeds a couple of demo policies and skills.
    *Acceptance:* The production database has the expected schema and seed data.

59. `chore: deploy to Render and verify end-to-end`
    Actually deploys. Verifies the deployed URL works, the demo flow completes against production Anthropic, costs are within budget.
    *Acceptance:* The deployed Streamlit URL successfully runs a full extract+simulate flow.

60. `docs: comprehensive README with architecture, setup, and demo link`
    Final pass on the top-level README. Includes the deployed URL, the architecture diagram, a "What the system does" section, and prominent links to ARCHITECTURE.md and the documentation blog post.
    *Acceptance:* A first-time reader can understand the system in 60 seconds of scrolling and clone-and-run successfully within 10 minutes.

61. `docs: documentation blog post in docs/blog-post.md`
    Writes the 1500–2500-word post on the extraction architecture, the structured-output approach, the eval harness, and what was learned during the build. Functions as long-form documentation; publishable to a personal blog if desired.
    *Acceptance:* The post reads cleanly as documentation of the system.

62. `chore: demo polish for screencast recording`
    Final tweaks to make the demo recordable in a single take: clear page titles, sensible default selections, removal of in-progress UI artifacts.
    *Acceptance:* A 4-minute walkthrough can be recorded without retakes.

63. `docs: record demo video and embed in README`
    Records the demo video walking through the system, uploads, embeds in README as a visual companion to the written documentation.
    *Acceptance:* The README displays the video thumbnail and the video plays.

### Scope additions

These commits were added after the initial design and slot into the weekly schedule at the points noted.

**A1 (week 2, after commit 16):** `feat(core): LLM response cache`
    Adds a `llm_cache` Postgres table and a new Alembic migration. Cache key is `sha256(provider|model|prompt_version|prompt)`. Temperature-0 calls check the cache before calling the API; hits are logged with `cached=true`. Per-call bypass flag available for sampling experiments.
    *Acceptance:* Running the same extraction twice returns the same structured output without a second API call; `llm_calls` row for the second call has `cached=true`.

**A2 (week 4, after A5):** `feat(api): rendered report at GET /simulations/{id}/report.html`
    Adds a Jinja2 template that compiles the SimulationReport into a standalone print-friendly HTML document. Content is specced to the report the BRD describes in Section 11 — this is the Tier 1 diagnostic deliverable, written for a Controller: an executive summary (match rate, escalation accuracy, contradiction count in plain language), the contradiction list with citations, observed pattern, frequency, affected segment, and estimated financial impact, missed and over-escalated cases, automation candidates, the ROI estimates from A5's schema fields, and a per-ticket evidence appendix. Linked from the Streamlit demo.
    *Acceptance:* `GET /simulations/{id}/report.html` returns valid HTML that renders correctly in a browser and produces a readable PDF when printed; every BRD Section 11 content element is present; every contradiction shown carries a resolvable citation.

**A3 (week 5, after commit 54):** `feat(core): cross-document contradiction detection`
    Given N policy documents from the same company, extracts a skill from each, aligns rules governing the same decision surface, and flags pairs with conflicting actions or thresholds. Alignment is LLM-assisted; conflict verification is mechanical. The Shopify ToS ("no refunds") vs. help-center (case-by-case review windows) pair from POLICY_CORPUS.md is the acceptance case.
    *Acceptance:* Running the detector against the Shopify document pair flags the conflict with citations from both sources.

**A4 (week 4, after commit 41):** `feat(api): minimal ticket CSV import`
    Adds `POST /tickets/import` accepting a CSV whose columns map onto the Ticket schema (`refund_amount`, `purchase_days_ago`, `customer_segment`, `fraud_flags`, `refund_reason`, `ground_truth_decision`), creating a ticket batch usable in simulations. Column mapping is documented, validation errors use the standard envelope with row-level detail. The Streamlit simulate page gains a CSV upload widget alongside the pre-loaded synthetic batches. Deliberately minimal — no Zendesk/Stripe connectors (those are v1.2) — but it is the difference between a demo and a diagnostic a design partner can run on their own data.
    *Acceptance:* Importing a sample CSV creates a batch, a simulation runs against it end-to-end, and a malformed row produces a 400 with the offending row and column identified.

**A5 (week 4, after A4, before A2):** `feat(core): contradiction records and report ROI fields to design spec`
    Brings the detector's output up to what Section 5.4 already specifies: each Contradiction carries the written rule with its citation, the observed behavior pattern, frequency, affected segment, and an estimated financial impact (divergent-ticket count × average refund amount in the cluster, labeled as an estimate). Extends `simulation_report.schema.json` with the aggregate ROI fields the BRD's Section 11 report promises: estimated automation-safe ticket volume, estimated manual review hours saved per month, and estimated dollar value of contradicted decisions. Schema change → codegen → both languages compile.
    *Acceptance:* A simulation report validates against the extended schema in both Python and TypeScript; every contradiction in the report resolves its citation against the source policy text.

**A6 (week 5, after commit 54, before A3):** `feat(core): contradiction clustering to spec`
    Completes the Section 5.4 detector design: adds reason category and time window as clustering dimensions alongside amount band and customer segment, and replaces the bare frequency threshold with statistical support (minimum cluster size plus a binomial test against the base error rate). Tuned against the expanded eval set from commit 51.
    *Acceptance:* Detector maintains ≥0.8 recall on planted divergences with ≤1 false positive per run under the new clustering; the simulation eval suite reports precision/recall for it.

## 13. Open questions

A handful of decisions are deferred to the build phase rather than committed in this doc:

The exact prompt structure for the extraction passes is sketched but not finalized. Real prompt engineering happens against the labeled examples, and the prompts will be iterated during weeks 2 and 5. The plan reserves explicit time for this.

The contradiction detection algorithm's sensitivity threshold (currently 5%) is a guess. The expanded eval set should let you tune this empirically.

Whether to add a second LLM provider (OpenAI) during the build vs. leave it as an architecture-only signal. Default: skip the actual implementation, document the interface in the README. Add if there's time left in week 6.

Whether the documentation blog post is the right format for the long-form writeup, or whether something else (a deep-dive technical README, a multi-part series) would serve better. The blog post is the default; the choice can be made at the time of writing.

## 14. Paths forward beyond the 6-week build

The 6-week scope produces a working extraction and simulation system, but the underlying problem extends well past that. This section sketches what each subsequent version would look like if the project continues into fall and beyond. The versions are roughly sequenced by dependency — each one assumes the previous ones are in place — but the decision to keep going can be made at any inflection point.

### v1.05 — Self-serve policy consistency checker (lead magnet and first transaction)

Commits A2 and A3 form the core of this tier when combined with a Stripe payment flow. A customer supplies two or more policy document URLs, receives a rendered contradiction report with citations, and pays per document analyzed. No data export, no ticket history, no integrations — just document-in, findings-out. This is the shortest path to a transaction.

Positioning, to keep this consistent with the BRD: the self-serve checker is the low-ticket entry point and distribution tool, not the first-revenue bet. The first serious revenue is the BRD's Tier 1 paid diagnostic ($10–25K) — the same A2 report and A3 findings delivered white-glove against a buyer's own documents and case data (via A4's CSV import). The checker exists to generate diagnostic conversations: self-serve checker → paid diagnostic → continuous policy fidelity → runtime, matching the BRD Section 15 sequence.

The work adds a billing page to the Streamlit demo (or its Next.js replacement), a Stripe Checkout integration, and a per-customer usage ledger. The technical additions are small; the value is in the product framing: the contradiction report becomes the deliverable, not a demo artifact.

### v1.1 — Replace Streamlit with a real review UI

The first substantive expansion is a React-based UI replacing the Streamlit demo. The motivation is not aesthetics but workflow: the simulation report and skill review steps are genuinely collaborative artifacts that a Controller would want to share with their Support Ops counterpart, comment on, and reference in audit conversations. Streamlit doesn't support that; a real UI does.

The work is roughly four weeks of part-time effort: Next.js app with the same three flows as Streamlit, server-rendered for shareability, comments and approval threads on individual extracted rules, exportable PDF version of the simulation report. The TypeScript SDK built in week 4 is what the new UI consumes, which validates the SDK's design under real load.

This is the version where the project starts looking like a product rather than a demo.

### v1.2 — Real integrations replacing CSV upload

The minimal ticket CSV import from the 6-week build (scope addition A4) is the right scope for the build but the wrong shape for actual usage. Real customers have tickets in Zendesk or Intercom, refund history in Stripe or a custom billing system, approval threads in Slack. The v1.2 work builds real read-only integrations for the two or three most common combinations.

The hard parts are not the API calls — those are well-documented — but the data normalization. A Zendesk ticket has a different schema from an Intercom ticket; both have to map into the system's internal Ticket primitive without losing information that matters for extraction or contradiction detection. This is where the schema-first architecture from the original build pays off: extending the Ticket schema with optional source-specific fields is mechanical, not a rewrite.

Roughly six weeks of work. The output is a system that a sympathetic customer could actually try with their own data.

### v1.3 — Governed runtime (the BRD's central pivot)

This is the version where the system stops being a simulation engine and becomes an execution layer. The work splits into three concurrent tracks: per-skill delegated authority (the permission engine), tool execution against sandboxed downstream systems (Stripe test mode, Zendesk sandbox), and the audit log infrastructure the BRD describes (every action recorded with skill version, inputs, rules applied, sources referenced, human approvals obtained, final action taken).

The hardest part is not the engineering but the trust: a customer has to genuinely believe the system will not issue a refund it shouldn't. That trust comes from the simulation report having earned it first, which is why the build sequence in the BRD has the diagnostic and recurring tiers ahead of runtime.

Realistically a two-to-three-month effort if done well, and probably the natural inflection point where the project either becomes a company or hands off to one. A single developer building runtime against real customer systems is a different scope from building a simulation engine.

### v1.4 — Agent integration via MCP

Once runtime exists, exposing it to AI agents via MCP (Model Context Protocol) is a relatively small additional surface. The skill spec becomes the canonical definition of what an MCP tool does; the runtime is the executor; the audit log captures everything the agent did and why.

The interesting design question at this stage is granularity: does each skill become its own MCP tool, or do we expose a single "execute_workflow" tool that takes a skill ID? Either works architecturally; the right answer depends on how agent platforms evolve and how they prefer to discover tools.

Two to four weeks once runtime is solid.

### v1.5 — Multi-tenancy and production hardening

The components that were intentionally deferred in the 6-week build come back: real authentication (probably Clerk or Auth0 rather than building it), multi-tenant data isolation (row-level security in Postgres, tenant-scoped LLM call quotas), production observability (Honeycomb or Datadog), backup and disaster recovery, cost monitoring with hard cutoffs per tenant.

This is the work that turns the system from "a tool" into "a service that companies can buy." If the project becomes a real company, this work happens between the first paid pilot and the first non-design-partner customer.

### Inflection points worth being honest about

There are three points where the decision to continue is non-trivial.

The first is at the end of the 6-week build itself. The system works, the architecture is sound, but actually using it on real customer data means either v1.1 + v1.2 (to make it usable) or accepting that it's a technical artifact rather than a product. Both are legitimate stopping points.

The second is between v1.2 and v1.3. Going from a simulation system to a runtime is the largest single jump in the roadmap. It's where the project goes from "interesting technical work" to "real product with real liability." That transition deserves to be a conscious decision with explicit evidence of buyer pull, not just technical readiness. The gate before committing to runtime: 30+ target-buyer conversations run (the BRD Section 23 motion), 3+ paid or serious design-partner diagnostics delivered, at least one buyer explicitly asking for recurring monitoring, and at least one buyer saying they would pilot runtime once the simulation report has earned their trust. Without those, runtime is technically impressive but commercially unvalidated.

The third is at v1.5. By that point the project is either a company or it isn't. Continuing past v1.5 as a side project is possible but inefficient — the work that matters then is sales, hiring, and customer success, not engineering.

### What stays out of scope even at v1.5

A few things explicitly stay out of the roadmap because they belong to a different product. Customer-facing chat is not in scope — that's what Decagon and Sierra do, and Skiljo is positioned downstream of them. Workflow orchestration for non-finance workflows is not in scope until v2.0 or later — the BRD's wedge discipline matters more than the BRD's long-term vision in the first two years. Building a "company skill marketplace" is not in scope at any version in this roadmap — the value is in customer-specific skills, not portable ones.

## 15. Future work (smaller technical improvements)

Beyond the version roadmap above, a handful of smaller technical improvements are worth noting as targets of opportunity during the build or shortly after:

Cost optimization on the extraction pipeline. The current design uses Opus for all four passes. Pass 1 (segmentation) and Pass 3 (zone classification) are simpler and could likely run on Haiku with negligible quality loss, cutting extraction cost by 60–70%.

OpenAI as a second LLM provider behind the existing client abstraction. The interface is designed to support this; the actual implementation is roughly one day of work and unlocks A/B testing different models for different passes.

Streaming responses for the extraction pipeline. Currently the system waits for full LLM response before validating; streaming with progressive validation would cut perceived latency in the UI.

Vector embeddings of policy text for similarity search across the corpus. Useful both for finding similar policies for evaluation purposes and for detecting when a new policy upload is nearly identical to an existing one.

Eval result visualization. Current eval output is JSON; a small web view that renders extraction precision/recall trends over commits would make regressions easier to debug.

Prompt versioning as first-class artifacts. Currently prompts are versioned via the `prompt_version` field on LLM calls but the prompts themselves are inline strings. Extracting them into a `prompts/` directory with semantic version numbers and a diff-friendly format would make prompt regression analysis cleaner.

## 16. Appendices

### Appendix A: Full Skill schema (JSON Schema)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://skiljo.ai/schemas/skill.schema.json",
  "title": "Skill",
  "type": "object",
  "required": ["skill_name", "version", "trigger", "inputs", "decision_zones"],
  "properties": {
    "skill_name": { "type": "string", "pattern": "^[a-z_][a-z0-9_]*$" },
    "owner": { "type": "string" },
    "co_owners": { "type": "array", "items": { "type": "string" } },
    "version": { "type": "integer", "minimum": 1 },
    "trigger": { "type": "string" },
    "inputs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "type"],
        "properties": {
          "name": { "type": "string" },
          "type": { "enum": ["string", "number", "integer", "boolean", "array"] },
          "description": { "type": "string" }
        }
      }
    },
    "decision_zones": {
      "type": "object",
      "required": ["deterministic", "llm_assisted", "human_only"],
      "properties": {
        "deterministic": {
          "type": "array",
          "items": { "$ref": "rule.schema.json#/$defs/DeterministicRule" }
        },
        "llm_assisted": {
          "type": "array",
          "items": { "$ref": "rule.schema.json#/$defs/LLMAssistedRule" }
        },
        "human_only": {
          "type": "array",
          "items": { "$ref": "rule.schema.json#/$defs/HumanOnlyRule" }
        }
      }
    },
    "audit_requirements": { "type": "array", "items": { "type": "string" } }
  }
}
```

### Appendix B: API spec summary

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/health` | Health check | None |
| POST | `/policies` | Upload `{raw_text, source_filename?}` and return the persisted policy | Bearer |
| GET | `/policies/{id}` | Get a persisted policy | Bearer |
| POST | `/skills/extract` | Start extraction with either `policy_text` or `policy_id` | Bearer |
| GET | `/skills` | List skills | Bearer |
| GET | `/skills/{id}` | Get current version of a skill | Bearer |
| GET | `/skills/{id}/versions` | List versions | Bearer |
| GET | `/skills/{id}/versions/{v}` | Get a specific version | Bearer |
| POST | `/skills/{id}/versions/{v}/approve` | Approve version | Bearer |
| POST | `/tickets/import` | Import ticket batch from CSV | Bearer |
| POST | `/simulations` | Start simulation job | Bearer |
| GET | `/simulations/{id}` | Get simulation status | Bearer |
| GET | `/simulations/{id}/report` | Get full report | Bearer |
| GET | `/simulations/{id}/report.html` | Get rendered HTML report (A2) | Bearer |
| POST | `/cross-document-contradictions` | Detect cross-document policy conflicts (A3) | Bearer |
| POST | `/eval-runs` | Record an eval run's metrics (commit_sha, dataset_version, model, metrics) | Bearer |
| GET | `/eval-runs` | List eval run history, filterable by `model`/`commit_sha` | Bearer |
| GET | `/jobs/{id}` | Poll a background job | Bearer |

All requests use `Authorization: Bearer <API_KEY>`. Errors use `{"error": {"code", "message", "details"}}`.

### Appendix C: Development setup commands

```bash
# One-time setup
git clone <repo>
cd skiljo
docker-compose up -d postgres
uv sync
pnpm install
make codegen
make migrate

# Daily dev
make api      # in one terminal
make demo     # in another
make test     # before committing
make lint typecheck

# Running evals locally
make eval-extraction
make eval-simulation
make eval-e2e
```

### Appendix D: Glossary

**Skill** — A structured, versioned, permission-aware encoding of a workflow's decision logic. The central abstraction of the system.

**Decision zone** — One of three execution modes within a skill: deterministic (mechanical rules), LLM-assisted (model interprets context, recommends, requires human approval), human-only (escalation only).

**Predicate DSL** — The constrained rule language used for conditions in deterministic and LLM-assisted zones. Supports `all`/`any` composition and a fixed operator set.

**Skill version** — An immutable snapshot of a skill spec. New versions are new rows; old versions are never edited.

**Simulation run** — One execution of a skill version against a batch of tickets, producing per-ticket results and a SimulationReport.

**SimulationReport** — The structured output of a simulation run: aggregate metrics (match rate, escalation accuracy) plus per-ticket detail.

**Contradiction** — A case where the skill's deterministic decision systematically diverges from historical (or ground-truth) behavior at a frequency above the contradiction threshold.

**LLM call log** — The append-only record of every LLM invocation, with model, prompt version, inputs, outputs, latency, and cost. The primary observability surface.

**Eval harness** — The system that runs the project's evals (extraction, simulation, end-to-end) against held-out data, producing metrics tracked over time and gating CI on regression.
