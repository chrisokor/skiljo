# Week 3, Task 7: Synthetic Ticket Generation

## What was built

A synthetic ticket batch generator that creates ground-truth-labeled tickets from a *shadow policy* — a Skill combined with a list of authored divergence specifications. The `generate_ticket_batch()` function produces tickets with randomized fields (amount, purchase_days_ago, customer_segment, fraud flags, refund_reason) and assigns each ticket a ground_truth_decision by: checking divergences first (highest priority), falling back to base skill rules, then falling back to "escalate_to_human".

**Files created:**
- `packages/core/src/skiljo_core/simulation/generator.py` — `DivergenceSpec`, `TicketFieldRanges`, `generate_ticket_batch()`, `_shadow_ground_truth()`
- `packages/core/tests/test_generator.py` — 6 parametrized tests for count, reproducibility, and divergence frequencies
- `data/synthetic_tickets/refund_v1/` — pre-generated skill.json and tickets.json for golden fixture tests

## Non-obvious concepts

**Shadow policy vs. written policy: why tickets don't come from the extracted skill.** A naive generator that creates tickets matching the *written* policy (the extracted skill's rules) would make simulation circular: the skill would always match its own source document, hiding real contradictions. Instead, tickets follow the *shadow policy*: apply base skill rules first, then override with *planted divergences* at specified frequencies. For example: the written policy says "deny all $500+ refunds," but the company actually approves VIP customers at 85% rate even when over $500. The divergence spec encodes this exception; when tickets are generated, 85% of high-amount VIP tickets get ground_truth_decision="approve_refund" while the base skill still says "deny" — surfacing a contradiction that the detector must find.

**`DivergenceSpec` as a planted test fixture, not an extraction artifact.** A `DivergenceSpec` is authored by hand, not extracted from the policy text. It specifies: `rule_id` (for tracking), `condition` (same predicate DSL as base rules), `base_decision` (semantic: what the written policy says, unused in code), `shadow_decision` (what actually happens), `frequency` (0.0–1.0, how often the divergence overrides the base decision). At generation time, divergences are checked in order; if one matches and `random() < frequency`, that divergence's shadow_decision is used. This makes planted contradictions *mechanically verifiable*: the detector must recover patterns from simulation outcomes alone, without seeing the planted specs.

**`TicketFieldRanges` for parameterized ticket distribution.** The ticket field ranges (e.g., `refund_amount_max=600`) control the distribution of tickets. If the extracted skill has a rule "deny if amount > $500," but `refund_amount_max` is only 500, very few tickets will trigger that rule. By setting `refund_amount_max=600`, the generator ensures enough high-amount tickets are created to test the rule and plant divergences around it. This is why the ranges are configurable — different skills and divergence patterns need different distributions.

**`random.Random(seed)` for reproducible generation.** The generator creates a seeded RNG instance (e.g., `rng = random.Random(42)`) rather than using the global random state. This decouples ticket generation from other code's random usage and makes reproducibility explicit: calling `generate_ticket_batch(..., seed=42)` twice produces identical tickets. The seed also flows to UUID generation: `uuid.UUID(int=rng.getrandbits(128))` produces deterministic ticket IDs. This is crucial for debugging and cross-run consistency in tests.

**Ground truth from deterministic condition evaluation, not LLM.** The `_shadow_ground_truth()` function calls `evaluate_condition()` from the evaluator module — a pure, table-driven predicate engine. Tickets are decided structurally: "does this ticket's amount match the condition?" No LLM is involved in ticket generation. This keeps generation fast, deterministic, and independent of API costs.

## Why this approach

Contradiction detection only works if contradictions are planted and known in advance. The shadow policy design makes planted contradictions *first-class data* (the divergence specs), and the detector's job is mechanically well-defined: "recover the planted patterns from simulation outcomes." This is measurable: a good detector should achieve ≥0.8 recall on planted divergences with ≤1 false positive per run. Without this design, detecting real contradictions would be a noisy heuristic; with it, we can validate the detector's accuracy before deploying to extract real policies.

## Where to look

- `skiljo_core/simulation/generator.py`:
  - `DivergenceSpec` — the planted override specification
  - `TicketFieldRanges` — customizable distribution parameters (why `refund_amount_max=600` matters)
  - `_shadow_ground_truth()` — decision logic: divergences first, then base skill rules, then fallback
  - `generate_ticket_batch()` — orchestration: build ticket dicts, evaluate ground truth, construct Ticket objects

- `skiljo_core/tests/test_generator.py`:
  - `test_divergence_overrides_base_decision_at_expected_frequency()` — VIP exception example with binomial variance tolerance
  - `test_planted_divergences_present_at_expected_rate()` — frequency statistical validation
  - `test_base_policy_applied_when_no_divergence_matches()` — fallback to base skill when no divergence fires

- `data/synthetic_tickets/refund_v1/`:
  - `generate.py` — script that creates the skill.json and tickets.json fixtures
  - `tickets.json` — 100 pre-generated tickets with planted divergences for golden tests
  - `skill.json` — the base skill (extracted or hand-authored) that ground truth is anchored to
