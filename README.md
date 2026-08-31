# Skiljo

Skiljo is a policy-fidelity system that turns refund, credit, and billing-adjustment policies into versioned, executable **Skills**: structured workflow specifications that AI agents can follow with approval gates, source citations, and an audit trail.

The core workflow compares written policy against historical support behavior to identify where documented rules and real-world decisions diverge. The project is built as a production-minded diagnostic prototype: the valuable output is a historical simulation report and a policy-vs-practice contradiction report, not live refund automation.

## Status

The core diagnostic workflow is implemented and locally test-covered:

```text
policy upload -> extraction -> structured Skill -> immutable SkillVersion
              -> ticket import -> simulation -> JSON/HTML diagnostic report
```

The v1.05 consistency-checker surface is also present through cross-document contradiction detection and Streamlit workflow pages. Default extraction evals run in an explicit offline mode; real-provider measurement remains opt-in, so mock/default output is not a product-quality metric.

## Engineering Highlights

- **Structured LLM extraction:** converts policy documents into validated, executable `Skill` specifications.
- **Source-grounded rules:** every extracted rule carries character-offset citations and quoted source text.
- **Immutable workflow versions:** policy-derived logic is persisted as new `SkillVersion` rows instead of mutating previous versions.
- **Policy-vs-practice simulation:** replays Skills against historical tickets to surface contradictions between written policy and actual outcomes.
- **Validation and retry pipeline:** structured outputs are validated with Pydantic and retried when schemas are not satisfied.
- **Evaluation harness:** extraction and simulation behavior are measured through local/CI eval plumbing.
- **LLM auditability:** every model call goes through the `LLMClient` abstraction and is logged for inspection.
- **Cross-language contracts:** canonical JSON Schema generates both Python/Pydantic models and TypeScript/Zod SDK types.

## Core Workflow

```text
Policy document
      |
      v
FastAPI policy upload
      |
      v
Four-pass LLM extraction
      |
      v
Validated Skill with citations
      |
      v
Immutable SkillVersion in Postgres
      |
      +------------------------+
      |                        |
      v                        v
Historical ticket import    Cross-document checks
      |                        |
      v                        v
Simulation engine          Consistency detection
      |                        |
      +-----------+------------+
                  v
       Diagnostic report
```

A typical workflow is:

1. Upload a policy document.
2. Extract a structured `Skill`.
3. Validate the extracted output and source citations.
4. Persist a new immutable `SkillVersion`.
5. Import historical tickets.
6. Replay the Skill against those tickets.
7. Compare simulated decisions against historical outcomes.
8. Generate a JSON or standalone HTML diagnostic report.

## Architecture

Skiljo is organized as a Python monorepo with a TypeScript SDK.

```text
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Demo                              │
│       upload policy -> extract -> review -> simulate            │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend                           │
│   extraction | simulation | versioning | reporting              │
│   background jobs tracked in PostgreSQL                         │
└──────────────┬─────────────────────┬────────────────────────────┘
               │                     │
               ▼                     ▼
        ┌─────────────┐       ┌──────────────┐
        │ LLM Client  │       │ PostgreSQL   │
        │             │       │ 11 tables    │
        └─────────────┘       └──────────────┘
               │
               ▼
        ┌─────────────┐
        │ Eval Harness│
        │   Inspect   │
        └─────────────┘

Canonical JSON Schema
       |
       +--> Pydantic models for Python
       +--> Zod schemas for the TypeScript SDK
```

## Design Invariants

Three invariants shape the system:

1. **Every LLM call is auditable.** Model calls are routed through the `LLMClient` abstraction and recorded in `llm_calls`.
2. **Skill versions are immutable.** Existing versions are never updated in place; a changed policy or extraction produces a new `SkillVersion`.
3. **Extracted rules require citations.** A rule must resolve back to source text through character offsets and quoted text before it can be trusted.

## Data Model

The core entities are:

- `Policy`: uploaded source policy text and source metadata.
- `Skill`: logical decision surface, such as refund handling.
- `SkillVersion`: immutable version of an extracted workflow specification.
- `TicketBatch`: imported or generated historical-ticket collection.
- `TicketRecord`: ordered ticket payload inside a batch.
- `SimulationRun`: evaluation of one Skill version against one ticket batch.
- `SimulationResult`: per-ticket decision, zone, match flag, and reasoning.
- `Job`: async status record for extraction and simulation.
- `LLMCall`: auditable record of model interaction.
- `LLMCache`: cache for deterministic model calls.
- `EvalRun`: persisted evaluation run metadata and metrics.

## Demo Artifacts

- [Sample diagnostic report](docs/demo-artifacts/sample-diagnostic-report.html)
- [Desktop report screenshot](docs/demo-artifacts/screenshots/sample-report-desktop.png)
- [Mobile-width report screenshot](docs/demo-artifacts/screenshots/sample-report-mobile.png)
- [5-minute demo script](docs/DEMO_SCRIPT.md)
- [Architecture one-pager](docs/ARCHITECTURE_ONE_PAGER.md)
- [Interview readiness guide](docs/INTERVIEW_READINESS.md)
- [Must Knows prep sheet](docs/MUST_KNOWS.md)
- [Golden path demo dataset](data/demo/golden_path/README.md)

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python, FastAPI |
| Database | PostgreSQL, SQLAlchemy, Alembic |
| Validation | Pydantic |
| Frontend demo | Streamlit |
| TypeScript SDK | TypeScript, Zod |
| Schema source | JSON Schema |
| LLM integration | Structured-output extraction pipeline |
| Evaluation | Inspect |
| Testing | Pytest, Vitest |
| Quality | Ruff, mypy, tsc |
| Local infrastructure | Docker Compose |

## Repository Structure

```text
skiljo/
├── schemas/            # Canonical JSON Schemas and codegen scripts
├── packages/
│   ├── core/           # Extraction, simulation, persistence, evals
│   ├── api/            # FastAPI backend
│   ├── demo/           # Streamlit demo workflow
│   └── sdk-ts/         # TypeScript client SDK
├── data/
│   ├── demo/           # Golden-path demo inputs
│   ├── eval/           # Train/dev/test extraction examples
│   ├── policies/       # Policy corpus documents
│   └── synthetic_tickets/
├── docs/               # Product, architecture, eval, and interview docs
├── infra/              # Deployment configuration
├── docker-compose.yml
├── Makefile
└── README.md
```

## Quick Start

Prerequisites:

- [uv](https://docs.astral.sh/uv/)
- [pnpm](https://pnpm.io/)
- Docker Desktop

Clone the repo and start Postgres:

```bash
git clone https://github.com/chrisokor/skiljo.git
cd skiljo
cp .env.example .env
docker compose up -d postgres
```

Install dependencies and apply migrations:

```bash
make setup
```

Start the API:

```bash
make api
```

The FastAPI server starts at `http://localhost:8000`. Verify it with:

```bash
curl localhost:8000/health
```

Start the demo:

```bash
make demo
```

## Development Commands

```bash
make api              # Start FastAPI development server
make demo             # Start Streamlit demo workflow
make test             # Run pytest + vitest
make lint             # Run Ruff
make typecheck        # Run mypy + tsc
make codegen          # Regenerate Pydantic/Zod models from JSON Schema
make eval-extraction  # Run extraction eval suite in default offline mode
make help             # Show all available targets
```

## Evaluation Philosophy

Skiljo treats model output quality as something to measure, not assume. Structured extraction outputs are schema-validated before persistence, and failures can trigger retry logic. Citation resolution is checked mechanically so source grounding is part of correctness, not a UI detail.

Default extraction evaluations run in an explicit offline mode. Real-provider evaluation is opt-in and should be reported with the exact model, prompt version, date, and split. Mock or offline results should not be interpreted as real model-quality metrics.

## Current Scope

Implemented:

- policy upload
- structured Skill extraction
- validation and retry handling
- required source citations for extracted rules
- immutable Skill version persistence
- historical-ticket CSV import
- ticket simulation
- contradiction detection
- cross-document consistency checks
- JSON and standalone HTML diagnostic reports
- Streamlit workflow surfaces
- CI-backed tests and eval plumbing

Intentionally deferred:

- live refund or billing execution
- durable distributed job processing
- multi-tenant auth and organization management
- production observability stack
- private customer-data redaction and retention controls
- payment/onboarding flow

## Product Context

The initial use case is operational policy enforcement for workflows such as refunds, credits, billing adjustments, exception handling, and approval-gated decisions.

The long-term idea is that an AI agent should not infer business policy from loose context. It should execute against a versioned, inspectable workflow with explicit delegated authority.

For more detail:

- [Business requirements](docs/BRD.md)
- [Product framing](docs/PRFAQ.md)
- [Technical design](docs/DESIGN_DOCUMENT.md)
- [Evaluation notes](docs/evals.md)
- [Simulation notes](docs/simulation.md)

## License

MIT — see `LICENSE`.
