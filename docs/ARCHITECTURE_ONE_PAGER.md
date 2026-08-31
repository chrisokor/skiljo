# Architecture One-Pager

Skiljo is a schema-first Python/TypeScript monorepo for policy-fidelity diagnostics.

## System Shape

```text
Policy document
      |
      v
FastAPI policy upload --------------+
      |                              |
      v                              |
Four-pass extraction pipeline        |
      |                              |
      v                              |
Structured Skill + citations         |
      |                              |
      v                              |
Immutable SkillVersion in Postgres   |
      |                              |
      +-----------+------------------+
                  |
Historical tickets imported from CSV |
                  |
                  v
Simulation engine runs Skill against tickets
                  |
                  v
Contradiction detector clusters mismatches
                  |
                  v
JSON report + standalone HTML diagnostic report
```

## Main Components

- `schemas/` — canonical JSON Schemas. Python and TypeScript types are generated from these.
- `packages/core/` — extraction pipeline, citation validation, simulation engine, contradiction detection, eval harness, and DB models.
- `packages/api/` — FastAPI endpoints, background jobs, ticket import, simulation/report routes.
- `packages/demo/` — Streamlit demo pages for extraction, review, simulation, and cross-document checks.
- `packages/sdk-ts/` — generated TypeScript SDK surface over the REST API.
- `data/` — policies, eval examples, synthetic tickets, and golden-path demo inputs.
- `docs/` — design, eval, simulation, interview, and learning documentation.

## Data Model To Explain

- `policies` store raw policy text and source metadata.
- `skills` identify a named decision surface, such as refund handling.
- `skill_versions` store immutable extracted specs, version numbers, status, and source-policy linkage.
- `ticket_batches` group imported or synthetic historical tickets.
- `ticket_records` store ordered ticket payloads inside a batch.
- `simulation_runs` track a run against one skill version and one ticket batch.
- `simulation_results` store per-ticket decisions and match/mismatch flags.
- `jobs` provide async status for extraction and simulation.
- `llm_calls` record provider, model, prompt version, inputs, outputs, token/cost metadata, latency, and cache status.

## Design Decisions

**Schema-first contracts:** JSON Schema is the source of truth, with generated Python/Pydantic and TypeScript/Zod types.

**LLM behind typed boundaries:** extraction uses structured outputs, retries, Pydantic validation, and citation validation.

**Mandatory citations:** every extracted rule must point back to character offsets and quoted text in the source document.

**Immutable versions:** a report should always be reproducible against the exact SkillVersion it used.

**Postgres plus JSONB:** relational entities need foreign keys and ordering; skill specs and summaries benefit from flexible JSON storage.

**BackgroundTasks for now:** enough for a local diagnostic prototype, with an explicit upgrade path to a durable queue.

**Shadow-policy simulation:** synthetic ground truth is generated from planted divergences so contradiction detection can be measured without circularity.

## Production Readiness Boundary

Production-minded today:

- typed contracts
- migrations
- persisted workflow state
- LLM call logging
- citation audit trail
- immutable versions
- API/E2E tests
- eval regression plumbing
- standalone report artifact

Not fully productionized yet:

- durable job runner
- tenant-aware auth
- hosted deployment operations
- private-data redaction/retention
- production metrics/alerts
- payment/onboarding

Best interview phrasing:

> The core diagnostic workflow is production-minded and locally verified. The next work is operational hardening, not proving the core architecture from scratch.
