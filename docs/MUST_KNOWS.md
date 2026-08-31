# Must Knows

This is the prep sheet for explaining Skiljo in interviews. Know these cold before adding more features.

## 1. The Product Loop

Skiljo's core workflow is:

`policy upload -> extraction -> structured Skill -> immutable SkillVersion -> ticket import -> simulation -> diagnostic report`

The point is not live automation yet. The MVP gives a finance/support-ops buyer a historical diagnostic: where written refund, credit, or billing policy disagrees with actual ticket outcomes.

Best phrase:

> Skiljo is a policy-fidelity diagnostic system. It turns written policy into executable decision logic, then compares that logic against historical behavior.

Where to look:

- `README.md`
- `docs/INTERVIEW_READINESS.md`
- `packages/api/tests/test_diagnostic_workflow.py`

## 2. Why Schema-First

JSON Schema is the source of truth for shared data shapes. Python Pydantic models and TypeScript/Zod SDK types are generated from the same schemas.

Why it matters:

- The API, core engine, and SDK do not drift silently.
- Schema changes force compile/test failures in both languages.
- LLM structured outputs validate against the same contracts the app uses.

Tradeoff:

- Codegen adds ceremony, but it prevents ambiguous contracts in a system where correctness and auditability matter.

Where to look:

- `schemas/`
- `packages/core/src/skiljo_core/schemas/`
- `packages/sdk-ts/src/types.ts`

## 3. Data Model

The minimum data model to explain:

- `Policy`: raw policy text plus source metadata.
- `Skill`: named decision surface, such as `process_refund_request`.
- `SkillVersion`: immutable extracted spec, version number, status, and source policy link.
- `TicketBatch`: imported or generated historical-ticket collection.
- `TicketRecord`: one ordered ticket payload inside a batch.
- `SimulationRun`: one run of one skill version against one ticket batch.
- `SimulationResult`: one ticket's decision, zone, match flag, and reasoning.
- `Job`: async status envelope for extraction and simulation.
- `LLMCall`: audit/cost/latency record for every provider call.

Interview answer:

> The data model separates source material, extracted decision logic, versioned evidence, ticket batches, and simulation outcomes. That keeps reports reproducible and gives each workflow step a durable boundary.

Where to look:

- `packages/core/src/skiljo_core/db/models.py`
- `docs/ARCHITECTURE_ONE_PAGER.md`
- `docs/learning/week8-task1-diagnostic-workflow.md`

## 4. Extraction Pipeline

The extraction pipeline is four passes:

1. Segment the policy into typed sections.
2. Extract candidate rules with citations.
3. Classify each rule into a decision zone.
4. Assemble and validate the final `Skill`.

The important engineering idea is that LLM output is never trusted directly. It goes through structured-output parsing, Pydantic validation, retries, and citation validation.

Interview answer:

> I treated the LLM as an unreliable parser behind a typed boundary. The model proposes structure, but the system validates shape, retries bad output, and rejects or repairs rules whose citations cannot be resolved against the source text.

Where to look:

- `docs/extraction.md`
- `packages/core/src/skiljo_core/extraction/`
- `docs/learning/week2-task7-assembly-pipeline.md`
- `docs/learning/week8-task2-extraction-eval-solver.md`

## 5. Citations Are the Audit Trail

Every extracted rule carries:

- character-offset span
- quoted source text

Why it matters:

- A rule without a citation is treated as a hallucination risk.
- Reviewers can trace policy logic back to the source document.
- The eval harness can check citation resolution mechanically.

Interview answer:

> The system does not just ask "did the model extract a plausible rule?" It asks "can this rule be tied back to exact source text?" That is the difference between extraction and auditable extraction.

Where to look:

- `schemas/rule.json`
- `docs/learning/week7-task4-eval-citations.md`
- `docs/learning/week8-task6-contradiction-affected-ticket-label.md`

## 6. Immutable Skill Versions

Extracted policy logic is persisted as immutable `SkillVersion` rows. If extraction changes, the system creates a new version instead of updating the old one.

Why it matters:

- Simulations are reproducible.
- Reports can say exactly which policy-derived logic was used.
- Policy evolution can be compared over time.

Interview answer:

> I used immutable versions because the output becomes evidence. If a diagnostic report says "this policy produced these decisions," changing that version later would corrupt the audit trail.

Where to look:

- `packages/core/src/skiljo_core/db/models.py`
- Alembic migrations under `packages/core/src/skiljo_core/db/migrations/`
- `docs/learning/week8-task1-diagnostic-workflow.md`

## 7. Shadow-Policy Simulation

Synthetic tickets are generated from a shadow policy, not from the written policy alone.

A shadow policy is the written policy plus authored divergences, such as "VIP customers over the normal refund threshold are approved 80% of the time."

Why it matters:

- If tickets were generated from the written policy, simulation would be circular.
- Planted divergences make contradiction detection measurable.
- The detector can be scored against known hidden differences.

Interview answer:

> The shadow-policy design avoids testing the model against itself. Ground truth follows hidden operational behavior, and the extracted skill follows written policy, so contradictions become measurable.

Where to look:

- `docs/simulation.md`
- `packages/core/src/skiljo_core/simulation/`
- `docs/learning/week3-task4-shadow-policy-generator.md`
- `docs/learning/week3-task5-contradiction-detection.md`

## 8. Contradiction Detection

Simulation compares predicted decisions from the extracted skill against ground-truth ticket outcomes. Contradiction detection clusters divergences into patterns such as customer segment and amount band, then reports affected tickets and estimated impact.

Why it matters:

- The buyer does not need a list of individual mismatches.
- They need patterns: who is affected, how often, and what it costs.

Interview answer:

> The report turns low-level simulation mismatches into operational findings: which rule was contradicted, which ticket segment showed the divergence, how many tickets were affected, and what the financial impact was.

Where to look:

- `packages/core/src/skiljo_core/simulation/contradictions.py`
- `packages/api/src/skiljo_api/templates/simulation_report.html.j2`
- `docs/demo-artifacts/sample-diagnostic-report.html`

## 9. Eval Posture

The eval harness exists and is wired into the development process, but default extraction evals currently run in explicit offline mode.

Say clearly:

- Offline evals prove the harness and citation plumbing run.
- They are not product-quality extraction metrics.
- Real-provider metrics require an intentional run with model, prompt version, date, and split recorded.

Interview answer:

> I separated harness readiness from quality claims. The offline path lets CI and local development stay deterministic, while real-provider evals are opt-in and must be reported with exact model and prompt context.

Where to look:

- `docs/evals.md`
- `.github/workflows/`
- `docs/INTERVIEW_READINESS.md`

## 10. Production-Minded, Not Fully Productionized

What is production-minded today:

- schema-first contracts
- typed API/SDK boundary
- Postgres persistence
- Alembic migrations
- immutable versions
- LLM call logging
- citation validation
- API tests and E2E workflow test
- report artifact generated through production templates

What is not productionized yet:

- durable background jobs
- tenant-aware auth
- hosted operations
- customer data retention/redaction
- production observability stack
- payment/onboarding

Best phrase:

> I intentionally stopped at a production-minded diagnostic core. The next layer is operational hardening, not more core product discovery.

## 11. The Productionization Roadmap

If asked "what would you do next?", answer in this order:

1. Durable jobs: replace FastAPI `BackgroundTasks` with a queue/worker while preserving the `jobs` table API contract.
2. Tenant isolation: add org/user models, scoped API keys, and row-level access checks.
3. Hosted deployment: managed Postgres, migrations on deploy, secrets, health checks, rollback.
4. Observability: metrics for job duration, failure rate, LLM cost, cache hit rate, validation failure rate, and report latency.
5. Real-provider evals: run dev/test with recorded model version, prompt version, date, and regression thresholds.
6. Data safety: PII redaction, retention policies, export/delete controls, and audit-log boundaries.
7. Commercialization: payment/onboarding after white-glove diagnostics prove demand.

## Questions You Should Be Able To Answer

- Why is every rule required to have a citation?
- Why are skill versions immutable?
- Why generate tickets from a shadow policy?
- Why use JSON Schema and codegen instead of hand-maintained types?
- Why use Postgres JSONB instead of a document database?
- Why is FastAPI `BackgroundTasks` acceptable for this stage?
- What breaks if the API process restarts during a job?
- What makes the current eval numbers meaningful, and what do they not prove?
- What would need to change before using private customer tickets?
- How would you productionize this in 30/60/90 days?

## Short Answers

**Why not Celery now?**
Because the current goal is validating the diagnostic workflow. `BackgroundTasks` keeps the system simple while preserving a `jobs` table contract that can move behind a durable worker later.

**Why Postgres?**
Because the system has relational entities, immutable versions, job state, and flexible JSON specs. Postgres plus JSONB covers both without adding another database.

**Why not live automation?**
Because policy fidelity must be proven before execution. The diagnostic report is the safer first product: it finds policy/practice mismatches before any agent is allowed to act.

**What is the strongest engineering decision?**
Mandatory citations plus immutable versions. Together they make LLM-derived policy logic auditable and reproducible.

**What is the biggest known gap?**
Operational hardening: durable jobs, tenant-aware auth, hosted observability, and data-safety controls for private customer data.
