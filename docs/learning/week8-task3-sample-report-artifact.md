# Task 3: Sample Diagnostic Report Artifact

## What Was Built

This task adds a reproducible sample of Skiljo's diagnostic report at
`docs/demo-artifacts/sample-diagnostic-report.html`. The artifact is created
by `scripts/generate_sample_report.py`, which builds a typed
`SimulationReport` and renders the production Jinja2 report template.

## Why It Is Generated

The sample is not hand-authored marketing copy. It exercises the same report
template and schema-backed data contract as a completed simulation, so changes
to report rendering can be regenerated and reviewed from a known input. The
fixed timestamp and UUIDs keep the output reproducible.

## Where To Look

- `scripts/generate_sample_report.py` builds the sample model and renders the
  template.
- `packages/api/src/skiljo_api/templates/report.html` defines the standalone,
  print-friendly report layout.
- `packages/api/tests/test_report_html.py` verifies the generator produces the
  required report sections.

Regenerate the committed artifact with:

```bash
uv run python scripts/generate_sample_report.py
```
