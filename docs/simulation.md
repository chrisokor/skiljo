# Simulation Engine

Operator and maintainer reference for the simulation engine: how a ticket is routed through a skill, how the predicate DSL is evaluated, how synthetic ground truth is generated, and how contradiction detection works. For the architectural summary see [ARCHITECTURE.md Section 6](../ARCHITECTURE.md#6-simulation-engine); for design rationale see [DESIGN_DOCUMENT.md Section 5.4](DESIGN_DOCUMENT.md).

Module: `packages/core/src/skiljo_core/simulation/` — `executor.py` (single-ticket routing), `evaluator.py` (predicate DSL), `engine.py` (batch orchestration + report aggregation), `generator.py` (synthetic ticket / shadow-policy generation), `contradictions.py` (divergence clustering).

## Three-zone routing (`executor.py`)

`simulate_ticket(skill, ticket, llm_client)` is the single-ticket entry point. It checks the three [decision zones](learning/GLOSSARY.md#decision-zones-deterministic--llm_assisted--human_only) **in a fixed priority order — deterministic, then llm_assisted, then human_only** — and within each zone, rules are checked in list order with **first match wins**:

1. **Deterministic zone.** For each `DeterministicRule` in `skill.decision_zones.deterministic`, evaluate its `condition` against the ticket (as a plain dict via `ticket.model_dump(mode="json")`). First rule whose condition is `True` returns a `Result` immediately — no LLM call.
2. **LLM-assisted zone.** Only reached if no deterministic rule matched. Same first-match-wins scan, but on match the engine makes one `generate_structured()` call (prompt `llm_assisted_zone_v1`) asking the model for an `LLMRecommendation{action, reasoning}` given the rule's action text, the matched condition, and the full ticket. The returned `action` becomes the `Result.decision`, and `reasoning` is carried through on the `Result` for the report's evidence appendix.
3. **Human-only zone.** Only reached if no deterministic or llm_assisted rule matched. First match returns the rule's `action` directly as the decision — no LLM call, no human interaction actually happens in simulation; this zone exists to test whether the skill's escalation criteria (which tickets should be flagged) are correct, not to synthesize a human's answer.
4. **No rule matched anywhere.** Falls through to a hardcoded default: `decision="escalate_to_human"`, zone `human_only`. This is a safety default, not a rule from the skill — a ticket that matches nothing gets escalated rather than silently dropped.

Every branch computes `matched_human_decision = (decision == ticket.ground_truth_decision)` before returning — this one boolean per ticket is what `compute_report()` aggregates into `match_rate`.

## Predicate DSL evaluator (`evaluator.py`)

Pure, side-effect-free, no `eval()` — table-driven dispatch on `Operator` (see [Predicate DSL](learning/GLOSSARY.md#predicate-dsl-domain-specific-language-for-conditions) in the glossary for the full operator list and design rationale). Two functions:

- `evaluate_predicate(predicate, ticket) -> bool` — looks up `ticket.get(predicate.field)`, dispatches on `predicate.op`. Notable non-obvious behaviors worth knowing when authoring or debugging rules:
  - `lt`/`lte`/`gt`/`gte` return `False` (not an exception) if the ticket's field value is `None` — a missing field never satisfies a numeric comparison, it just silently doesn't match.
  - `contains` behaves differently depending on the *ticket* value's type, not the predicate's declared type: if the field value is a `str`, it does a substring check (`str(value) in field_value`); if it's a `list`, it does membership (`value in field_value`); anything else returns `False`. This lets one operator serve both "does this text mention X" and "is X in this list" conditions.
  - `empty`/`not_empty` treat `None`, `[]`, and `""` as the empty cases — no other falsy values (e.g. `0`, `False`) count as empty.
  - `in`/`not_in` treat a `None` predicate value as an empty list, so `in` with no value never matches and `not_in` with no value always matches.
- `evaluate_condition(condition, ticket) -> bool` — a `Condition` has either `all` or `any` (schema-enforced `minProperties: 1, maxProperties: 1`, so never both). `evaluate_condition_or_predicate()` recurses through `ConditionOrPredicate.root`, which is either a `Predicate` (leaf) or a nested `Condition` — this is what gives the DSL arbitrary nesting depth for compound rules like `(A and B) or (C and D)`.

This module is deliberately dependency-free and synchronous — it's what makes deterministic-zone evaluation safe to run inline with no LLM call and no `asyncio` overhead.

## Async batch processing (`engine.py`)

`simulate_batch(skill, tickets, llm_client, max_concurrency=5)` runs `simulate_ticket()` over every ticket concurrently: `asyncio.gather` over one coroutine per ticket, each wrapped in `asyncio.to_thread(simulate_ticket, ...)` (because `simulate_ticket` and the underlying Anthropic client are synchronous) and bounded by an `asyncio.Semaphore(max_concurrency)` (default 5). See [Batch simulation](learning/GLOSSARY.md#batch-simulation) and [Simulation semaphore](learning/GLOSSARY.md#simulation-semaphore) in the glossary — the semaphore exists specifically so a 100-ticket batch doesn't fire 100 concurrent LLM calls at once; only tickets that hit the llm_assisted zone actually consume a semaphore slot for an API call, but every ticket (including pure-deterministic ones) goes through the same `to_thread` wrapper for uniformity.

`compute_report(skill_version_id, results, tickets)` aggregates the per-ticket `Result` list into a `SimulationReport`:
- `match_rate` = fraction of results where `matched_human_decision` is true.
- `escalation_accuracy` = of the results routed to the human_only zone, the fraction where the ticket's `ground_truth_decision` was itself one of `{"escalate_to_human", "human_only", "requires_human_review"}` — i.e., "when the skill escalated, was escalating actually correct?" Vacuously `1.0` if nothing was escalated.
- `automation_candidate_count` = count of results resolved in the deterministic zone — tickets that needed zero LLM judgment and zero human involvement.
- Empty result list returns a report with `match_rate=0.0`, `escalation_accuracy=1.0`, `results=[]` rather than raising or dividing by zero.

## Shadow policy design (`generator.py`)

See the [Shadow policy](learning/GLOSSARY.md#shadow-policy) and [Divergence spec](learning/GLOSSARY.md#divergence-spec-planted-contradiction) glossary entries for the concept; this section covers the mechanics.

`generate_ticket_batch(base_skill, divergences, count, seed, ranges)` produces `count` synthetic `Ticket`s with a seeded `random.Random(seed)` (default seed `42`, so a fixed seed reproduces an identical batch — this is why the committed `refund_v1` golden fixtures are stable across runs). Ticket fields (`refund_amount`, `purchase_days_ago`, `customer_segment`, `fraud_flags`, `refund_reason`) are drawn from a `TicketFieldRanges` config (uniform for amount/days, weighted-choice for segment, Bernoulli for the fraud flag).

The critical design point: **ground truth is not "whatever the base skill says."** `_shadow_ground_truth()` computes each ticket's `ground_truth_decision` in this priority order:

1. **Divergences first.** For each `DivergenceSpec{rule_id, condition, base_decision, shadow_decision, frequency}` in the authored list, if the ticket matches `condition` *and* an `rng.random() < frequency` roll succeeds, the ground truth is `shadow_decision` — not what the written policy says. This is the plant: e.g. "VIP customers over the $500 threshold get approved 80% of the time" is one `DivergenceSpec` with `frequency=0.8`.
2. **Base skill deterministic rules**, evaluated the same way `executor.py` would, if no divergence fired.
3. **Base skill llm_assisted rules** — ground truth here is hardcoded to `"requires_human_review"` rather than actually invoking an LLM (the generator is a pure, offline, seeded function; it doesn't call out to Claude to decide what a human "would" do).
4. **Final fallback** — `"escalate_to_human"` if nothing matched.

This ordering is why the technique is not circular: if ground truth were generated by running the same skill you're about to simulate, the skill would trivially match 100% of the time and there would be nothing to detect. Because divergences are checked *before* the base skill's own rules, some fraction of tickets have ground truth that contradicts what the skill itself would decide — and that gap is exactly what contradiction detection (below) has to recover.

## Contradiction detection (`contradictions.py`)

`detect_contradictions(results, tickets, threshold=0.05, min_cluster_size=3)`:

1. **Cluster** every `(Result, Ticket)` pair by a `(amount_band, customer_segment)` key. `_amount_band()` buckets `refund_amount` into `"0-50"`, `"51-100"`, `"101-200"`, `"201-500"`, `"500+"`; `customer_segment` defaults to `"unknown"` if unset. See [Cluster](learning/GLOSSARY.md#cluster-contradiction-detection) in the glossary.
2. **Skip small clusters.** Any cluster with fewer than `min_cluster_size` tickets is dropped before computing a rate — this avoids flagging a "100% divergence" that's actually just one unlucky ticket (`test_no_contradiction_below_min_cluster_size` covers this directly).
3. **Compute divergence rate** = `count(result.decision != ticket.ground_truth_decision) / cluster size`. Clusters at or below `threshold` are dropped.
4. **Summarize the dominant divergence.** Among the diverged pairs in a flagged cluster, `Counter` finds the most common `(written_decision, observed_decision)` pair — this becomes `Contradiction.written_decision` / `.observed_decision`. A cluster can have multiple divergent decision pairs in practice; only the plurality pair is reported per cluster (a known simplification — see below).
5. **Estimate financial impact.** `FinancialImpact{divergent_ticket_count, average_refund_amount, estimated_impact_usd}` is computed only over the diverged tickets in the cluster (`average_refund_amount` is their mean `refund_amount`; `estimated_impact_usd` is that mean times the diverged count — a simple "dollars at stake if every diverged ticket kept diverging" estimate, not a modeled projection).

See [Contradiction](learning/GLOSSARY.md#contradiction-planted-divergence-detection) in the glossary. Acceptance target from CLAUDE.md / DESIGN_DOCUMENT.md Section 9: ≥0.8 recall on planted divergences, ≤1 false positive per run — measured by checking that flagged clusters actually correspond to authored `DivergenceSpec`s (see `data/synthetic_tickets/` and the golden fixture tests in `packages/core/tests/`, e.g. `test_contradictions.py`'s VIP-cluster scenario, which is a hand-built version of exactly this check).

**Known gaps** (worth knowing before assuming a bug):
- `Contradiction.citation` and the analogous `simulation_report_schema.Citation` model exist as schema fields but are **always `None`** from `detect_contradictions()` — nothing currently links a flagged cluster back to the specific extracted rule and its (not-yet-implemented, see [`docs/extraction.md`](extraction.md)) source citation. `test_citation_defaults_to_none` documents this as expected current behavior, not a test gap.
- Clustering is two-dimensional (amount band × segment) only. CLAUDE.md's roadmap for week 5 scope addition A6 calls for completing the clustering dimensions (adding reason and time window) and adding a binomial-test significance check against the base error rate, in place of the current bare frequency threshold. As of this writing that expansion has not landed — `threshold`/`min_cluster_size` are the only statistical guardrails.

## Cross-document contradiction detection (`cross_document.py`, scope A3)

Distinct module, distinct problem from the `contradictions.py` detector above — worth not conflating the two. `detect_contradictions()` clusters *simulated ticket outcomes* against a single written policy to find where practice diverges from that one document. `detect_cross_document_contradictions()` in `packages/core/src/skiljo_core/simulation/cross_document.py` takes **no ticket data at all** — it operates purely on rules extracted from two or more policy *documents* belonging to the same company (e.g. a Terms of Service and a help-center page) and flags pairs of rules that govern the same real-world decision but prescribe different actions. The canonical acceptance case (see DESIGN_DOCUMENT.md Section 5.11 and `docs/POLICY_CORPUS.md`) is Shopify's ToS ("no refunds") vs. its help center (case-by-case review windows) — exercised directly in `test_detects_refund_policy_conflict` in `packages/core/tests/test_cross_document_contradictions.py`.

`detect_cross_document_contradictions(policies: list[PolicyDocument], llm_client, model=...)` works in two stages, both gated so an LLM hallucination alone can never produce a reported contradiction:

1. **Alignment (LLM-assisted).** Every rule from every document is classified onto a `decision_surface` label (a short snake_case tag like `refund_eligibility` or `sla_credit`, prompt `decision_surface_v1`) — this is what lets rules with differently-worded conditions from different documents be grouped as "about the same underlying question." Rules are then grouped by that label.
2. **Conflict verification (mechanical gate, then LLM confirmation).** Within each decision-surface group, every cross-document pair of rules is considered — pairs from the *same* document are skipped outright (that's what `contradictions.py` is for), and pairs whose `action` strings are already identical are skipped without spending an LLM call (identical actions can never be a conflict, so this is checked mechanically first — see `test_mechanical_check_skips_identical_actions_without_llm_call`). Only a surviving pair triggers a second LLM call (prompt `cross_document_conflict_v1`) asking whether the two rules truly disagree on a case that could fall under both, versus just covering non-overlapping situations. Only pairs the model marks `is_conflict=True` are reported.

Each `CrossDocumentContradiction` carries the decision surface, both policy IDs, both actions, the model's rationale, and a `CrossDocumentCitation` for each side (policy ID, zone, rule index, action) — this is provenance sufficient to point a reviewer at exactly which rule in which document, though it's index-based rather than the character-offset-into-source-text citation described in `docs/extraction.md`'s citation gap (that citation type doesn't exist on `Rule` yet, so this detector can't cite source text either — only its own position within the extracted `Skill`).

## Testing

`packages/core/tests/test_evaluator.py` is table-driven over every `Operator`. `packages/core/tests/test_contradictions.py` covers clustering, threshold, min-cluster-size, and financial-impact math directly with hand-built `Result`/`Ticket` fixtures — no LLM, no async, fully deterministic. Golden fixture tests (`packages/core/tests/` — see [Golden fixture test](learning/GLOSSARY.md#golden-fixture-test)) run the full `refund_v1` skill against the committed 100-ticket synthetic batch with planted divergences and assert on the resulting `SimulationReport` shape and metrics. See [`docs/evals.md`](evals.md) for how simulation quality will be measured against labeled ground truth at the eval-harness level (not yet built as of this doc — only the extraction eval suite exists today).
