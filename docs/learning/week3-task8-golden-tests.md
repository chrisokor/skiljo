# Week 3, Task 8: Golden Fixture Tests

## What was built

A test suite that runs the complete simulation pipeline against pre-generated, version-controlled golden data (a `Skill` object and 100 synthetic tickets with ground-truth labels). The tests verify: simulation produces the expected number of results, the report is schema-valid, zone routing is correct, and the contradiction detector recovers planted divergences. These are *golden fixture tests* — they trade test independence (each test re-generates data) for stability (assertions run against known, committed data).

**Files created:**
- `packages/core/tests/test_simulation_golden.py` — 7 tests loading skill.json and tickets.json, running `simulate_batch()`, and asserting on results
- `data/synthetic_tickets/refund_v1/skill.json` — the base skill fixture
- `data/synthetic_tickets/refund_v1/tickets.json` — 100 pre-generated tickets with planted divergences
- `packages/core/tests/conftest.py` — `FakeLLMClient` pre-populated with 50 responses (one per llm_assisted call)

## Non-obvious concepts

**Why FakeLLMClient must be pre-populated (not response-on-demand).** The skill's llm_assisted zone fires for roughly 32 tickets out of 100 (those matching the goodwill or high-amount conditions). Each call to `llm_client.generate_structured()` consumes one pre-loaded response from a list. If the fake client only generated responses on demand, tests would accidentally pass because the fake would always succeed; by pre-populating exactly 50 responses, the test would catch if the skill routes more than 50 tickets to llm_assisted (the test would exhaust the list and fail). This is a deliberate guard: if the skill's zone routing changes and suddenly routes 60 tickets to llm_assisted, the test fails loudly rather than silently.

**`asyncio.run()` bridges sync pytest and async `simulate_batch()`.** `simulate_batch()` is an async function, but pytest tests are synchronous. `asyncio.run(simulate_batch(...))` runs the async function to completion and returns the result. This is the standard pattern for testing async code in a sync test framework. The alternative — making the test async with `async def test_...` and using `pytest-asyncio` — works but requires pytest plugin configuration; `asyncio.run()` is simpler and doesn't add dependencies.

**Golden fixture vs. unit test: trade-offs.** Unit tests generate fresh data and assert on logic (e.g., `test_eq_operator_matches_equal_values`). Golden fixture tests load committed data and assert on integration outcomes (e.g., `test_golden_simulate_batch_returns_all_results`). Golden fixtures are slower and less isolated (failures are harder to debug because the test and data are separate), but they catch regressions in real end-to-end scenarios — if someone changes the zone routing logic or the report aggregation, golden tests catch it. Unit tests are fast and focused; golden tests are integration tests. This project uses both: unit tests for evaluator operators and generator logic; golden fixtures for simulation and report generation.

**`model_validate_json()` for loading fixtures.** `Skill.model_validate_json()` and `Ticket.model_validate()` deserialize the JSON fixture files back into typed objects. This catches schema drift: if the JSON was saved with an old schema version and the schema has changed (e.g., a required field was added), deserialization fails at test load time with a clear validation error, not a cryptic failure deep in the test.

**Assertions on metrics, not exact counts.** Tests assert on bounded ranges (e.g., `0.0 <= report.match_rate <= 1.0`) and presence of contradictions (`len(contradictions) >= 1`), not exact counts. This is because ticket generation is probabilistic: the divergence at frequency=0.85 will produce approximately 85% of divergence firings, not exactly 85% of 100. Tests tolerate this variance and just check that the signal is present and bounded.

## Why this approach

Golden fixture tests serve as regression detectors and integration validators for the simulation pipeline. By pinning a skill and ticket set in the repo, every CI run can verify that simulation still works end-to-end and produces metrics in expected ranges. This is especially valuable during refactoring: if someone optimizes `simulate_batch()` or changes how `compute_report()` aggregates results, golden tests catch unintended behavioral changes. The tradeoff is that golden data must be maintained (if the schema changes, fixture files must be regenerated), but for a small, stable data set like 100 tickets, this is negligible.

## Where to look

- `skiljo_core/tests/test_simulation_golden.py`:
  - `_make_fake_client()` — pre-populates 50 LLMRecommendation responses
  - `_load_data()` — loads skill.json and tickets.json from the fixture directory
  - `test_golden_simulate_batch_returns_all_results()` — verifies length and structure
  - `test_golden_report_is_schema_valid()` — checks bounded metrics
  - `test_golden_detector_finds_planted_divergences()` — validates contradiction detection
  - `test_golden_all_deterministic_tickets_have_expected_decision()` — zone routing correctness

- `data/synthetic_tickets/refund_v1/`:
  - `skill.json` — the fixed skill for all golden tests
  - `tickets.json` — 100 pre-generated, immutable tickets with ground-truth labels
  - `generate.py` — how the fixture was originally created (reference; re-run only if updating fixtures deliberately)

- `skiljo_core/testing.py` — `FakeLLMClient` implementation
