# Week 3 Task 4 — Shadow-Policy Ticket Generator

## What was built

A synthetic ticket batch generator that produces ground-truth decisions from a *shadow policy* — the written policy plus authored divergences (e.g. VIP exceptions, near-threshold leniency). This makes contradiction detection measurable: the detector must recover planted divergences from outcomes alone.

**Files created:**
- `packages/core/src/skiljo_core/simulation/generator.py` — `DivergenceSpec`, `TicketFieldRanges`, `generate_ticket_batch()`
- `packages/core/tests/test_generator.py` — 6 tests covering count, reproducibility, divergence frequencies, and base-policy fallback
- `packages/core/src/skiljo_core/simulation/__init__.py` — exports for new classes and function

## Why

A naive generator that creates tickets from the *written* policy would make simulation circular: the extracted skill would always match its own policy, hiding real contradictions. Instead, tickets follow the *shadow policy*: apply the base skill's rules first, then override with divergences at specified frequencies.

Example: if the written policy says "deny refunds over $500," but the company actually approves VIP refunds over $500 at 80% rate, the shadow policy specifies that divergence. When the skill is simulated against tickets, it reports "deny" but the ground truth says "approve" (with 80% frequency), surfacing the contradiction.

This makes contradiction detection *mechanically verifiable*: we plant divergences, generate tickets, simulate, then check if the detector recovers the planted patterns.

## Non-obvious concepts

**Shadow policy vs. written policy.** The generator doesn't read the written policy text — it consumes a `Skill` object (extracted rules + zones) and a list of `DivergenceSpec` objects (authored overrides). The skill itself is the *base policy*. Divergences are authored mutations: rules that fire under different conditions or return different decisions than the base skill would. The generator blends them: divergences are checked first (highest priority), then base skill zones in order.

**Divergence as planted ground truth.** A `DivergenceSpec` is not a rule to extract; it's a test fixture. It specifies:
- `condition`: a predicate on the ticket (same DSL as base rules)
- `base_decision` (unused in the code, but semantic: "what the written policy says")
- `shadow_decision`: what actually happens in reality
- `frequency`: how often (0.0–1.0) the divergence overrides the base decision when `condition` matches

At generation time, for each ticket: (1) check every divergence in order; if one matches and `random() < frequency`, return its `shadow_decision`; (2) fall back to base skill zones; (3) final fallback to "escalate_to_human".

**`random.Random(seed)` for reproducibility.** The generator creates a separate RNG keyed on the seed, not the global random state. This lets test code and simulations reproducibly generate the same batch with the same seed — crucial for debugging and cross-run consistency. The seed flows through to UUID generation: `uuid.UUID(int=rng.getrandbits(128))` produces deterministic IDs.

**Frequency as probabilistic override.** A 100% frequency divergence always fires when the condition matches. A 50% frequency divergence fires roughly half the time. This is sampled *per ticket* (not "generate 10 tickets, diverge 5"), so with count=500 and frequency=0.5, you expect ~250 tickets to take the divergence path (with binomial variance). Tests use generous tolerance (±20%) to account for variance.

**Ground truth from condition evaluation, not LLM.** `_shadow_ground_truth()` calls `evaluate_condition()` from the simulation evaluator — the deterministic predicate engine, not an LLM. Tickets are evaluated purely structurally: "does this ticket's amount field match the condition?" This keeps ticket generation fast and deterministic.

## Where to look

- `skiljo_core/simulation/generator.py`:
  - `DivergenceSpec` — the data model for planted divergences
  - `TicketFieldRanges` — customizable distribution ranges (amounts, days, segments)
  - `_shadow_ground_truth()` — the decision-making logic: divergences first, then base skill, then fallback
  - `generate_ticket_batch()` — orchestration: build ticket dicts, evaluate ground truth, construct `Ticket` objects

- `skiljo_core/tests/test_generator.py`:
  - `test_divergence_overrides_base_decision_at_expected_frequency()` — VIP exception example
  - `test_planted_divergences_present_at_expected_rate()` — frequency statistical test
  - `test_base_policy_applied_when_no_divergence_matches()` — base skill fallback

- `skiljo_core/simulation/__init__.py` — public exports
