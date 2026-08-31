# 5-Minute Demo Script

Use this when rehearsing or recording Skiljo. The goal is to show the complete diagnostic path without getting pulled into implementation details too early.

## Setup

Set both API keys to the same value for local development because the API reads `API_KEY` and the Streamlit client reads `SKILJO_API_KEY`.

```bash
export DATABASE_URL=postgresql+psycopg://skiljo:skiljo@localhost:5433/skiljo
export API_KEY=dev-local-key
export SKILJO_API_KEY=dev-local-key
export SKILJO_API_URL=http://localhost:8000
```

Start dependencies and services:

```bash
docker compose up -d postgres
make migrate
make api
```

In a second terminal:

```bash
make demo
```

For a deterministic full-workflow proof without a live LLM call:

```bash
uv run pytest packages/api/tests/test_diagnostic_workflow.py -v
```

## Files To Use

- Policy: `data/demo/golden_path/policy.txt`
- Tickets: `data/demo/golden_path/tickets.csv`
- Expected summary: `data/demo/golden_path/expected_summary.json`
- Report artifact: `docs/demo-artifacts/sample-diagnostic-report.html`
- Desktop screenshot: `docs/demo-artifacts/screenshots/sample-report-desktop.png`
- Mobile-width screenshot: `docs/demo-artifacts/screenshots/sample-report-mobile.png`

## Minute-By-Minute Flow

**0:00-0:30 — Problem**

Say:

> Support automation fails when it needs company-specific judgment. Skiljo extracts refund and billing policy into executable decision logic, then checks that logic against historical tickets to find where written policy and actual behavior diverge.

Show:

- `README.md` status line.
- `docs/demo-artifacts/sample-diagnostic-report.html`.

**0:30-1:20 — Extraction**

In Streamlit:

1. Open the Extract page.
2. Choose Upload file.
3. Upload `data/demo/golden_path/policy.txt`.
4. Set Skill name to `process_refund_request`.
5. Set Trigger to `refund_request`.
6. Click Extract Skill.
7. Show the resulting structured JSON.

Narrate:

> The LLM output is not trusted directly. It is forced through structured output parsing, Pydantic validation, retries, and citation validation.

**1:20-2:00 — Review And Versioning**

In Streamlit:

1. Open Review.
2. Select `process_refund_request`.
3. Expand the draft version.
4. Point to rule citations in the JSON.
5. Click Approve.

Narrate:

> Extracted logic is persisted as an immutable SkillVersion. If the policy or extraction changes, that creates a new version instead of mutating the old one.

**2:00-3:10 — Ticket Simulation**

For the visual Streamlit demo:

1. Open Simulate.
2. Select an approved skill.
3. Select the available `refund_v1` ticket batch.
4. Click Run Simulation.
5. Show match rate, escalation accuracy, contradiction count, and per-ticket results.

For the API-backed CSV-import path, use the exact API sequence in the next section.

Narrate:

> The system compares what the extracted policy would do against historical ticket outcomes. That exposes policy/practice gaps instead of just producing a nice-looking rule list.

**3:10-4:20 — Report**

Open:

- `docs/demo-artifacts/sample-diagnostic-report.html`
- `docs/demo-artifacts/screenshots/sample-report-desktop.png`

Show:

1. Executive summary.
2. Contradiction section.
3. Affected ticket count.
4. Estimated financial impact.
5. Citation quote.

Narrate:

> The buyer does not need every raw mismatch first. They need the pattern: which written rule was contradicted, where it happened, how often, and what it may cost.

**4:20-5:00 — Production Readiness**

Say:

> This is production-minded but not fully productionized. The core diagnostic workflow is implemented and locally verified. The next production layer would be durable jobs, tenant-aware auth, hosted operations, observability, real-provider eval runs, and private-data controls.

Show:

- `docs/INTERVIEW_READINESS.md`
- `docs/MUST_KNOWS.md`

## API Golden Path

This is the exact persisted process:

```bash
POLICY_ID=$(
  curl -sS -X POST http://localhost:8000/policies \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    --data-binary @- <<'JSON' | jq -r '.id'
{
  "raw_text": "Refunds under $100 within 30 days are approved automatically when there are no fraud flags.\n\nRefunds over $100 require human review.\n\nVIP customers may receive goodwill refunds after review when the account is in good standing.\n\nRefund requests with fraud flags must be escalated to human review.",
  "source_filename": "golden_path_policy.txt"
}
JSON
)
```

```bash
EXTRACT_JOB_ID=$(
  curl -sS -X POST http://localhost:8000/skills/extract \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"policy_id\": \"$POLICY_ID\",
      \"skill_name\": \"process_refund_request\",
      \"trigger\": \"refund_request\"
    }" | jq -r '.job_id'
)
```

```bash
curl -sS "http://localhost:8000/jobs/$EXTRACT_JOB_ID" \
  -H "Authorization: Bearer $API_KEY" | jq
```

```bash
TICKET_BATCH_ID=$(
  curl -sS -X POST http://localhost:8000/tickets/import \
    -H "Authorization: Bearer $API_KEY" \
    -F "file=@data/demo/golden_path/tickets.csv;type=text/csv" | jq -r '.batch_id'
)
```

After the extraction job completes, copy `result_ref` from the job response as `SKILL_VERSION_ID`, then run:

```bash
SIM_JOB_ID=$(
  curl -sS -X POST http://localhost:8000/simulations \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"skill_version_id\": \"$SKILL_VERSION_ID\",
      \"ticket_batch_id\": \"$TICKET_BATCH_ID\"
    }" | jq -r '.job_id'
)
```

```bash
curl -sS "http://localhost:8000/jobs/$SIM_JOB_ID" \
  -H "Authorization: Bearer $API_KEY" | jq
```

After the simulation job completes, copy `result_ref` as `SIMULATION_ID`:

```bash
curl -sS "http://localhost:8000/simulations/$SIMULATION_ID/report" \
  -H "Authorization: Bearer $API_KEY" | jq
```

```bash
curl -sS "http://localhost:8000/simulations/$SIMULATION_ID/report.html" \
  -H "Authorization: Bearer $API_KEY" \
  -o /tmp/skiljo-report.html
```

## Demo Caveats

- A real extraction demo requires `ANTHROPIC_API_KEY`.
- Real extraction output can vary; record model, prompt version, date, and metrics if you quote quality.
- The deterministic test path uses `FakeLLMClient` to prove the persisted workflow without network/API cost.
- The Streamlit simulate page currently uses the committed synthetic `refund_v1` fixture for visual simulation; CSV import is available through the API.
- The HTML report is print/report-first. The mobile-width screenshot is included to show responsive behavior, but the evidence table is intentionally denser than a production mobile review UI would be.
