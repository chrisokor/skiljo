# Task 7: Consistency checker workflow

## What was built

The Streamlit demo now presents Skiljo v1.05 as a policy consistency checker
while retaining its existing multipage workflow. Once a simulation completes,
the demo retrieves the existing standalone HTML report and offers it as a
browser download. The simulation summary remains visible if report retrieval
fails.

## Key concepts

The existing [Streamlit multipage navigation](GLOSSARY.md#streamlit-multipage-navigation)
discovers pages automatically from the `pages/` directory. The entrypoint only
sets shared page configuration and sidebar context, so this task did not add a
second navigation system.

`st.download_button` sends an in-memory value to the browser as a downloadable
file. It is appropriate for the report endpoint because the API already returns
a complete HTML artifact; the UI does not reconstruct or transform the report.

## Why this way

The task brief named page files that do not exist in this repository and
proposed a long instructional home page. The implemented version follows the
actual automatic page layout and keeps the product framing concise. Fetching
the report only after simulation completion preserves the API lifecycle: the
report endpoint is backed by a completed persisted `SimulationReport`, as
described by the [diagnostic report](GLOSSARY.md#diagnostic-report-standalone-html)
entry.

The API-client test asserts the exact authenticated report request, including
the endpoint and timeout. This keeps the integration boundary independently
testable without requiring a live API or a completed background job.

## Where to look

- `packages/demo/src/app.py` sets the shared checker title and sidebar context.
- `packages/demo/src/api_client.py` contains `get_simulation_report_html()`.
- `packages/demo/src/pages/3_Simulate.py` retrieves and exposes the report
  after a completed simulation.
- `packages/demo/tests/test_api_client.py` covers the report-client request.
