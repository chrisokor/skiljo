# Week 8 Task 6: Contradiction Affected-Ticket Label Fix

## What was built

The HTML diagnostic report now labels `Contradiction.ticket_count` as "affected
tickets." The checked-in sample report was regenerated, and its rendering test
proves the report no longer calls that value a cluster size.

## Non-obvious concepts

**A rate and its numerator have different meanings.** A contradiction's
`frequency` is the affected-ticket count divided by all tickets in the feature
cluster. The report has only the numerator in `ticket_count`, so presenting it
as the denominator would turn a 3-of-6 finding into the misleading statement
that the cluster contains three tickets. See [Contradiction](GLOSSARY.md#contradiction-planted-divergence-detection).

## Why this approach

The detector and report schema already preserve the desired semantics. A
localized presentation change and a negative assertion correct the user-facing
claim without changing detection behavior or data contracts.

## Where to look

- HTML wording: `packages/api/src/skiljo_api/templates/report.html`
- Rendered regression: `packages/api/tests/test_report_html.py`
- Regenerated artifact: `docs/demo-artifacts/sample-diagnostic-report.html`
