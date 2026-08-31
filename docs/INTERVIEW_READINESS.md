# Interview Readiness

## 60-Second Summary

Skiljo turns refund, credit, and billing policies into versioned executable `Skill` specs, then simulates those specs against historical tickets to find where written policy and real behavior diverge.

## What Is Demonstrable

- Policy upload through FastAPI.
- Four-pass LLM extraction into structured `Skill` specs.
- Immutable `SkillVersion` persistence.
- Historical ticket CSV import and simulation.
- JSON and standalone HTML diagnostic reports.
- Cross-document contradiction detection.
- Schema-first Python/TypeScript type generation.

## Technical Stories

- Auditability: every rule requires character-offset citations.
- Reliability: structured outputs, Pydantic validation, retries, and citation validation.
- Measurement: train/dev eval corpus, regression gate plumbing, and explicit caveats where metrics are not fully meaningful.
- Product judgment: report artifacts are designed for finance/support-ops review, not just developer logs.

## Production Readiness Positioning

Use this framing:

> Skiljo has a production-minded core workflow: schema-first contracts, immutable policy-derived versions, auditable citations, persisted jobs/results, API tests, eval gates, and a report artifact a buyer could review. It is not yet a production SaaS platform; durable job processing, tenant isolation, hosted operations, and payment/onboarding are deliberately deferred until the diagnostic workflow is validated.

Safe claims:

- The complete diagnostic path is implemented and locally verified.
- The architecture is designed around auditability, repeatability, and measurable regressions.
- The project uses production-style boundaries: FastAPI API, Postgres persistence, Alembic migrations, schema codegen, and a typed SDK.
- Known production gaps are explicit rather than hidden.

Avoid claiming:

- Live customer deployment.
- Revenue or paid usage.
- Enterprise-ready multi-tenancy.
- Durable background processing.
- Real-provider extraction quality without a dated model/eval run.

## Productionization Roadmap

If asked what comes next, answer in this order:

1. **Durable jobs:** replace FastAPI `BackgroundTasks` with a queue/worker once jobs must survive process restarts. Keep the existing `jobs` table contract and move execution behind it.
2. **Tenant model:** add organizations, users, scoped API keys, and row-level access checks around policies, skills, ticket batches, simulations, and reports.
3. **Hosted operations:** deploy API/demo with managed Postgres, migration automation, health checks, secret management, and rollback procedure.
4. **Observability:** add metrics for job duration, failure rates, LLM cost, cache hit rate, extraction validation failures, and report generation latency.
5. **Real eval runs:** run extraction/simulation/e2e evals against dev and held-out test using recorded model versions, prompt versions, and dates.
6. **Data safety:** add PII redaction, retention controls, export/delete workflows, and stricter audit-log boundaries before using private customer tickets.
7. **Commercial surface:** add onboarding/payment only after the white-glove diagnostic proves buyer demand.

## Demo Readiness

Golden path to narrate:

1. Upload a policy.
2. Run extraction.
3. Show the structured `Skill` and rule citations.
4. Show the immutable `SkillVersion`.
5. Import historical tickets.
6. Run simulation.
7. Open the JSON/HTML diagnostic report.
8. Explain how contradictions and financial impact are derived.

Artifacts to show:

- `docs/demo-artifacts/sample-diagnostic-report.html`
- `docs/demo-artifacts/screenshots/sample-report-desktop.png`
- `docs/demo-artifacts/screenshots/sample-report-mobile.png`
- `docs/DEMO_SCRIPT.md`
- `docs/ARCHITECTURE_ONE_PAGER.md`
- `packages/api/tests/test_diagnostic_workflow.py`
- `docs/DESIGN_DOCUMENT.md`
- `docs/MUST_KNOWS.md`

One-sentence caveat to say upfront:

> This is a locally verified diagnostic product prototype with production-minded architecture; the operational hardening work is scoped and documented, but not overbuilt before validation.

## Honest Limitations

- No payment flow.
- No live customer deployment claim.
- Real-provider eval metrics require deliberate opt-in runs and should be reported with exact model/date/context.
- Background jobs use FastAPI `BackgroundTasks`, so jobs are not durable across process restarts.
- Single-key bearer auth is enough for the prototype but not a tenant-aware SaaS auth model.
- Private customer-ticket handling would need PII/redaction and retention work before production use.

## Verified Locally

Last verified: 2026-08-15

- `make lint typecheck test`: ruff: all checks passed; mypy: success, no issues found in 53 source files; TypeScript typecheck: passed; pytest: 274 passed, 2 skipped; vitest: 27 passed across 4 files.
- `uv run pytest packages/api/tests/test_diagnostic_workflow.py -v`: 1 passed.
- `make eval-extraction`: 30 train samples completed offline; `recall_scorer=0.000`, `citation_scorer=1.000`.
- `uv run python -m skiljo_core.eval.collect_metrics --output /tmp/skiljo-readiness-metrics.json --split train`: `citation_resolution=1.000`, `contradiction_precision=1.000`, `contradiction_recall=1.000`, `e2e_accuracy=1.000`, `extraction_recall=0.000`, `simulation_match_rate=1.000`. Caveat: this offline run uses `mockllm/model`; extraction executes its explicit offline solver because a real injected `LLMClient` is required, so these are not real-provider extraction-quality metrics.

## Resume Bullets

General:

- Built Skiljo, a Python/TypeScript policy-fidelity system that extracts refund and billing rules into versioned executable specifications using FastAPI, Pydantic, SQLAlchemy, Streamlit, and a generated TypeScript SDK.
- Designed a four-pass LLM extraction pipeline with structured outputs, validation retries, audit logging, and mandatory character-offset citations linking each rule to source text.
- Implemented historical-ticket simulation and contradiction detection with clustering, statistical support, and estimated financial impact reporting.
- Shipped a complete diagnostic workflow: policy upload, Skill extraction, immutable version persistence, ticket import, simulation, and standalone HTML reports.
- Framed and documented a productionization roadmap covering durable jobs, tenant isolation, hosted operations, observability, real-provider evals, and data-safety controls.

Backend-focused:

- Built a FastAPI/Postgres diagnostic backend with async job endpoints, Alembic migrations, bearer-auth protection, persisted ticket batches, immutable skill versions, and JSON/HTML report retrieval.
- Modeled policy extraction and simulation as durable workflow state across policies, skills, skill versions, ticket batches, simulation runs, simulation results, jobs, and LLM call logs.
- Added deterministic API coverage for the full persisted workflow from policy upload through HTML report generation.

AI infra-focused:

- Designed an LLM extraction pipeline that treats model output as untrusted: structured outputs, validation retries, citation resolution, and explicit offline/real-provider eval modes.
- Added mandatory character-offset citations for every extracted rule, turning LLM-derived policy logic into auditable, source-grounded evidence.
- Built eval/regression plumbing that separates harness health from quality claims, with documented caveats for mock/offline metrics.

Full-stack/product-focused:

- Shipped a Streamlit diagnostic workflow that connects extraction, review, approval, simulation, report download, and cross-document consistency checks.
- Created a buyer-facing standalone HTML report summarizing match rate, escalation accuracy, contradictions, affected tickets, and estimated financial impact.
- Packaged the project with demo artifacts, a golden-path dataset, a 5-minute demo script, and interview-ready productionization framing.
