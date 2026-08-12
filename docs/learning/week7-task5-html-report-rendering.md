# Week 7 Task 5: HTML report rendering

## What was built

`GET /simulations/{sim_id}/report.html` now renders a standalone, print-friendly
policy consistency report from the persisted `SimulationReport`. The existing
authenticated simulations router remains the sole endpoint owner. The report
includes an executive summary, contradiction evidence with source citations and
financial impact, ROI estimates, automation candidates, an explicit limitation
for exception classifications not represented by the current contract, and a
per-ticket evidence appendix.

The simulation background job now converts detected contradictions into the
existing report schema before persisting the run summary. That conversion carries
the matching extracted-rule citation forward, including the mechanically
validated character offsets and quoted source text.

## Non-obvious concepts

### Persisted report contracts

The detector returns internal dataclasses, while the API persists and serves the
Pydantic `SimulationReport` schema. Converting the detector data at the job
boundary avoids putting internal types into JSONB and means both the JSON and
HTML report endpoints read the same versioned report contract. A rendered report
is then a pure presentation of recorded results, not a second detector run that
could drift from the JSON report.

### Citation provenance in diagnostic output

Contradictions need to show the policy text that produced the written decision.
The report conversion resolves the first skill rule whose action matches the
detected written decision and copies its citation span and quote into the public
report record. When an LLM-assisted decision has no matching rule action, the
report omits a citation instead of fabricating one.

### Honest unavailable metrics

`SimulationReport` tracks matches and decision zones, but does not distinguish a
mismatch as a missed escalation versus an over-approval. The report calls this
out and directs readers to per-ticket evidence rather than deriving unsupported
counts from incomplete data.

## Why this approach

The task brief proposed a new core renderer and reports router, but both would
duplicate the existing route and use obsolete simulation types. Extending the
existing route preserves its bearer-auth dependency and error-envelope handling,
keeps the product report tied to the stored run summary, and avoids a schema
change solely for presentation.

The template uses only inline CSS and standard HTML. It has no CDN or external
asset dependency, so the response remains usable when saved, emailed, or printed.
Print rules remove the browser-only surface and move the evidence appendix to a
new page.

## Where to look

- `packages/api/src/skiljo_api/routers/simulations.py`: persists report-safe
  contradiction evidence and supplies template metadata.
- `packages/api/src/skiljo_api/templates/report.html`: self-contained printable
  report layout and conditional sections.
- `packages/api/tests/test_report_html.py`: endpoint tests for the report
  sections, citation rendering, financial impact, ROI, and persistence path.

## Verification

`make lint typecheck test` passed: Ruff clean, mypy clean, 232 Python tests
passed with 2 skipped, and 27 SDK tests passed.

## Review fix: ambiguous rule actions

The first implementation selected the first rule whose `action` matched a
contradiction's written decision. That was unsafe because actions such as
`approve_refund` can occur in multiple rules. The resolver now gathers matches
across every decision zone and emits a citation only when exactly one rule has
that action. The regression test creates two matching rules with distinct source
quotes and verifies that both the persisted report and rendered HTML omit the
citation. This is intentionally conservative: the detector does not currently
preserve matched rule identity, so a more specific citation cannot be justified.
