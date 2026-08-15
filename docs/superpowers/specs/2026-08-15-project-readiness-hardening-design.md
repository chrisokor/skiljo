# Project Readiness Hardening Design

## Goal

Bring Skiljo as close as practical to portfolio/interview/demo readiness by making the repository's status accurate, activating the highest-value eval measurements, adding concrete evidence artifacts, and packaging the project story without overstating what is proven.

## Scope

This work is a credibility hardening pass after the citations and v1.05 product merge. It does not add new product surfaces beyond the existing extraction, simulation, report, and cross-document flows. It focuses on making those surfaces easier to trust, verify, and explain.

In scope:

- Update stale project-status documentation so `AGENTS.md`, `docs/evals.md`, `Makefile`, README-style docs, and learning docs agree with the actual code.
- Improve eval execution so train/dev runs produce the most meaningful local metrics currently possible without reading `data/eval/test/`.
- Add or refresh a polished sample diagnostic artifact that can be referenced from docs and interviews.
- Add a concise portfolio/interview readiness section covering architecture, technical highlights, honest limitations, and demo flow.
- Run full local verification and document any remaining caveats.

Out of scope:

- Reading or tuning against `data/eval/test/`.
- Adding payment flows, Stripe Checkout, or customer accounts.
- Replacing Streamlit with a production React UI.
- Adding external infrastructure such as Celery, Redis, Kafka, or a vector database.
- Claiming production revenue, customer usage, or real quality metrics that have not been measured.

## Approach

### 1. Documentation Truth Pass

The first task updates status-facing documentation to reflect what is actually merged on `main`. `AGENTS.md` currently says week 2 is complete even though the repo now includes citations, simulation, contradiction detection, reports, cross-document UI, and v1.05 consistency-checker workflow. The eval docs also contain stale language around dataset loading and vacuous metrics.

The result should make a first-time reviewer see a coherent project state:

- What is shipped.
- What is test-covered.
- Which eval numbers are meaningful today.
- Which eval numbers remain blocked by solver or ticket-level ground truth gaps.
- What should not be claimed yet.

### 2. Eval Activation Pass

The eval harness already has train/dev dataset loading and metric collection, but extraction recall remains low because no solver populates `state.metadata["actual_spec"]` from a real pipeline run. Simulation and e2e metrics remain partly vacuous because the eval corpus lacks ticket-level simulation ground truth.

The implementation should activate the highest-value eval gap first: extraction pipeline execution against train/dev examples. The solver should call the existing extraction pipeline through existing abstractions, avoid bypassing `LLMClient`, and work with mock or fixture-backed clients where tests need determinism. Real-model execution can remain opt-in through existing model/env configuration.

Acceptance target:

- `make eval-extraction` or the metric collector produces an extraction recall value derived from actual pipeline output, not an empty actual spec.
- `citation_resolution` remains enforced at `1.0`.
- `data/eval/test/` remains unread by local commands and loaders.
- Any simulation/e2e metrics that remain vacuous are explicitly documented rather than hidden.

### 3. Evidence Artifact Pass

The project needs one polished artifact a reviewer can open without running the full stack. The preferred artifact is a standalone HTML diagnostic report generated from a representative fixture or test-backed sample. It should demonstrate:

- Executive summary.
- Contradictions with source citations.
- Frequency phrasing that is evidence-accurate.
- Estimated financial impact.
- Automation candidates or related report fields.
- Evidence appendix.

The artifact should be generated from code or committed fixture data, not hand-authored as a fake report. Documentation should link to it and explain what it represents.

### 4. Portfolio Package Pass

Add a concise portfolio/interview section that translates implementation details into reviewer-readable claims. The section should include:

- A 60-second project summary.
- Architecture highlights.
- Reliability and auditability choices.
- Evaluation status and caveats.
- Suggested demo path.
- Resume bullets that avoid unsupported claims.

This can live in the top-level README or a dedicated docs file linked from README, depending on current README structure.

### 5. Verification Pass

Before calling the work complete, run:

- `make lint typecheck test`
- the available eval command or metric collector for train/dev, using mock/default model unless the user explicitly provides a real-model environment
- any focused tests added during the work

The final status must report exact command outcomes and remaining limitations.

## Testing Strategy

Use test-driven changes for behavior changes:

- Add failing tests before introducing an extraction eval solver or changing metric behavior.
- Add tests that prove `split="test"` remains rejected.
- Add tests for any artifact generation helper.
- Keep docs-only changes scoped and verify with status/grep checks rather than inventing unnecessary test machinery.

Existing full-suite verification remains the final gate.

## Risks And Controls

Risk: overstating eval quality.
Control: docs must distinguish activated measurements from architecture scaffolding and must include actual command output in the final report.

Risk: accidentally reading held-out test data.
Control: keep loader protections, do not run commands against `data/eval/test/`, and add or preserve tests around forbidden split handling.

Risk: introducing real LLM cost or flaky tests.
Control: tests should use deterministic fake clients or mock providers; real-provider evaluation remains opt-in.

Risk: hand-authored demo artifacts becoming marketing fiction.
Control: generate sample reports from fixture data or API/report code paths and document the fixture origin.

## Success Criteria

- Repository status docs match merged functionality.
- Extraction eval no longer reports recall from an empty actual spec.
- Citation resolution remains required and verified.
- A standalone diagnostic evidence artifact exists and is linked from docs.
- Portfolio/interview guidance is present in repo docs and avoids unsupported claims.
- Full verification passes, or any failure is documented with exact output and next action.
