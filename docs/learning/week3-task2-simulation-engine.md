# Week 3, Task 2: Simulation Engine

## What was built

The core simulation engine: `simulate_ticket()` runs a single ticket through a skill's three decision zones (deterministic → llm_assisted → human_only) and returns a `Result` with the decision, zone, and a boolean flag indicating whether the decision matched the ground truth. `simulate_batch()` wraps `simulate_ticket` in asyncio with `asyncio.to_thread()` and a semaphore of 5 for concurrent execution. `compute_report()` aggregates results into a `SimulationReport` with match_rate, escalation_accuracy, and automation_candidate_count.

**Files created:**
- `packages/core/src/skiljo_core/simulation/executor.py` — `simulate_ticket()` and `LLMRecommendation` schema
- `packages/core/src/skiljo_core/simulation/engine.py` — `simulate_batch()`, `compute_report()`
- `packages/core/tests/test_simulation_golden.py` — end-to-end simulation tests against golden fixture data

## Non-obvious concepts

**Why `asyncio.to_thread()` wraps a sync LLMClient.** The `LLMClient` protocol expects `generate_structured()` to be synchronous: it returns immediately with a `StructuredResponse`, not a coroutine. But `simulate_batch()` needs to run multiple tickets concurrently via asyncio. The solution is `asyncio.to_thread(simulate_ticket, ...)`: this offloads the entire sync ticket simulation (including the potentially blocking LLM call) to a thread-pool thread, returning an awaitable that asyncio can manage. The thread blocks on the LLM call, but the main event loop stays free to schedule other tickets. This avoids rewriting the LLMClient as async without sacrificing concurrency.

**Why `asyncio.Semaphore(max_concurrency=5)`.** Without a bound, 100 tickets could spawn 100 threads and fire 100 LLM API calls simultaneously, overwhelming the Anthropic API rate limit and causing cascading failures. A semaphore of 5 limits concurrent LLM calls to 5 at a time (one per active thread in the pool), preventing a thundering herd. The value of 5 is conservative — it stays well within typical API tier limits while still parallelizing the work.

**Escalation accuracy definition and the vacuous case.** `escalation_accuracy` measures how many tickets sent to the human-only zone should have actually gone there. It's computed as: correct escalations / total escalations. A ticket escalated by the skill should match one of the escalation decisions (`escalate_to_human`, `human_only`, `requires_human_review`) in its ground truth. If no tickets were escalated (escalated list is empty), `escalation_accuracy` is set to 1.0 (vacuous truth: zero errors implies perfect accuracy). This avoids division-by-zero and reflects the intuition that a skill that doesn't escalate anything but could have can't be blamed for escalation errors it didn't make.

**`model_dump(mode="json")` for LLM prompts.** Before passing ticket data to the LLM, `simulate_ticket()` calls `ticket.model_dump(mode="json")` to convert the Pydantic model to a plain dict with JSON-serializable values. This ensures the prompt string is stable and reproducible (no internal object references that might differ between runs), and it's the safe pattern when the dict will be consumed by an external process (the LLM).

## Why this approach

Three-zone evaluation mirrors real support workflows: (1) mechanical rules (deterministic zone) execute without human input, (2) rules where an LLM can assist but a human could override (llm_assisted zone) get a recommendation, (3) rules too sensitive to automate (human_only zone) go straight to an agent. This staging is measurable: the report tracks how many tickets reached each zone, and the match_rate tells us how often the skill's decisions align with ground truth — the signal for whether the skill is accurate enough to deploy.

Asyncio with a semaphore is the practical concurrency pattern for Python when you have I/O-bound work (API calls) and need to avoid overloading the remote service. The semaphore is the safety mechanism — without it, concurrency becomes a liability.

## Where to look

- `skiljo_core/simulation/executor.py`:
  - `simulate_ticket()` — three-zone traversal with condition evaluation and LLM call for llm_assisted zone
  - `LLMRecommendation` — the schema for LLM recommendation responses

- `skiljo_core/simulation/engine.py`:
  - `simulate_batch()` — asyncio orchestration with `asyncio.to_thread()` and `asyncio.Semaphore`
  - `compute_report()` — aggregation logic: match_rate, escalation_accuracy, automation_candidate_count

- `skiljo_core/tests/test_simulation_golden.py`:
  - `test_golden_simulate_batch_returns_all_results()` — verifies all results are produced
  - `test_golden_report_is_schema_valid()` — validates report metrics are bounded
  - `test_golden_all_deterministic_tickets_have_expected_decision()` — ensures zone routing is correct
