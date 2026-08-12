# Week 7 Task 8: Integration Testing and Final Polish

## What Was Built

The final Week 7 coverage adds a fake-client integration test for the complete
four-pass extraction pipeline. It segments a policy, extracts three candidate
rules, classifies each into a different decision zone, and verifies that every
resulting citation resolves against the complete source document after the
pipeline converts it from section-relative to document-relative offsets.

The report endpoint suite now also checks the product delivery contract: the
response is a complete HTML document with inline CSS and print rules, with no
external HTTP resources. Existing tests already covered report retrieval,
not-found and incomplete-run errors, diagnostic evidence, citation persistence,
and the demo API client's authenticated report fetch, so this task extends
those tests instead of duplicating them.

The design document now records the `GET /simulations/{id}/report.html`
response, content, and error behavior in the report-rendering section.

## Why This Way

The extraction pipeline deliberately asks the LLM for offsets within each
segment, because that is the text supplied to the extraction prompt. Before a
skill can be persisted, those offsets need to be translated to the policy
document and mechanically validated again. Exercising all decision zones proves
that the conversion is not accidentally limited to deterministic rules.

`FakeLLMClient` keeps that test deterministic and verifies the production
pipeline's real LLM interface without making network calls or bypassing the
`LLMClient` boundary. The report checks remain API-level tests because the
important product contract is the served artifact, not merely the Jinja
template in isolation.

## Where To Look

- `packages/core/tests/test_e2e_citations.py` covers end-to-end citation
  resolution across segmentation, extraction, zoning, and assembly.
- `packages/api/tests/test_report_html.py` verifies report response and
  standalone-printable artifact behavior.
- `docs/DESIGN_DOCUMENT.md` Section 5.12 specifies the rendered report
  endpoint.

## Verification

Run `make lint typecheck test` from the repository root. The core test uses no
real LLM calls and does not access the held-out eval split.
