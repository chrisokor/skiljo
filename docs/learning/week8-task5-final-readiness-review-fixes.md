# Week 8 Task 5: Final Readiness Review Fixes

## What was built

The final readiness review wave made the committed diagnostic report internally
consistent, made the default extraction eval executable offline, preserved CSV
ticket order through persistence and simulation, and enforced exactly one policy
source on extraction requests. It also reconciled stale readiness and eval docs.

## Non-obvious concepts

**Aggregate fixtures need one source of truth.** The sample now contains all 12
ticket results behind its totals. Tests independently recompute match rate,
automation volume, contradiction frequency, financial impact, affected IDs, and
half-open citation span length from the fixture so contradictory evidence cannot
be committed silently. This extends the existing
[character-offset citation](GLOSSARY.md#character-offset-citation) discipline to
the product artifact itself.

**Offline is an execution mode, not a bypass.** The default `ExtractionEval` now
installs an explicit offline [eval solver](GLOSSARY.md#eval-solver) that records an
unavailable extraction result. Inspect still loads the train dataset and runs the
scorers, producing honest `0.0` recall and vacuous `1.0` citation resolution.
Injecting an application-configured `LLMClient` remains the only real-provider
path, preserving call logging and network-free defaults.

**Database reads do not preserve insertion order.** Ticket records now carry a
zero-based `position`; import writes it, retrieval and simulation order by it, and
the migration creates a composite `(batch_id, position)` index. See
[relational row ordering](GLOSSARY.md#relational-row-ordering).

**Either/or request contracts belong at validation.** `ExtractRequest` rejects
both missing and duplicate policy sources before route logic or database access,
while retaining the existing inline `policy_text` and persisted `policy_id` paths.

## Why this approach

The fixes stay within existing boundaries: no schema/codegen change was needed,
the unmerged Alembic migration was amended in place, and no provider client is
constructed inside the eval package. Focused tests cover each review finding,
including loading the extraction task through the same file entrypoint used by
`make eval-extraction`.

## Where to look

- Sample fixture and reproducibility: `scripts/generate_sample_report.py` and `packages/api/tests/test_report_html.py`
- Offline extraction task: `packages/core/src/skiljo_core/eval/extraction.py`
- Ticket ordering: `packages/core/alembic/versions/a7b2c9d4e5f6_ticket_batches.py`, `packages/core/src/skiljo_core/db/models.py`, and the ticket/simulation routers
- Extraction source validation: `packages/api/src/skiljo_api/routers/skills.py`
