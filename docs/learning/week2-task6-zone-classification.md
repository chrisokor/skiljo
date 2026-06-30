# Week 2, Task 6: Extraction pass 3 — decision zone classification

## What was built

The third LLM pass: for each `DeterministicRule` candidate extracted in pass 2, one LLM call classifies it into one of three *decision zones* (`deterministic`, `llm_assisted`, `human_only`). A second function (`classify_rules`) loops over a list of rules, calls `classify_zone` on each, and assembles the results into a `DecisionZones` struct — the typed container that groups rules by zone before assembly in pass 4.

## Key concepts

**Decision zones — what they mean and why they matter.**
The three zones reflect how much autonomy the system can safely exercise on a given rule:

- **`deterministic`** — the rule's condition is mechanically evaluable from structured ticket data (numeric thresholds, exact field matches). No interpretation needed; a rule engine can execute it without LLM involvement at runtime.
- **`llm_assisted`** — the condition requires interpreting ambiguous or subjective language ("goodwill", "reasonable", "anomalous"), so a model is needed at runtime to judge the case. But the stake is low enough that the outcome can be proposed without a human in the loop.
- **`human_only`** — too high-stakes, legally sensitive, or judgment-heavy to automate even with LLM assistance. The system surfaces the case to a human agent and stops.

Classification is a *labeling* step, not a structural one. The `DeterministicRule` type (which all candidates start as) carries the condition/action structure regardless of zone; `classify_rules` upcasts to `LLMAssistedRule` or `HumanOnlyRule` only when the zone is known, setting `requires_human_approval=True` on `LLMAssistedRule` as part of that construction.

**`Literal` type as a validation fence.**
`ZoneClassification.zone` is typed `Literal["deterministic", "llm_assisted", "human_only"]`. When the model's response is parsed via `generate_structured`, Pydantic rejects any value not in that set during validation — meaning `classify_zone` can only ever return one of those three strings. This is what makes the `else` branch in `classify_rules` technically safe (the reviewer flagged it as Minor): by the time the code reaches `else:`, Pydantic has already rejected anything that isn't one of the three Literal values. A future-proof version would use `elif zone == "human_only": ...` and raise on the `else` to catch drift when new zones are added to the schema — but that's a quality call, not a correctness issue.

**One LLM call per rule, not per batch.**
`classify_rules` loops and calls `classify_zone` once per rule rather than sending all rules to the model in a single prompt. This adds more LLM calls (one per rule vs. one total) but keeps each call's schema simple (`ZoneClassification` — a single `zone` field) and makes the retry/validation loop from Task 2 more effective (a bad output on rule 3 only retries rule 3, not the whole batch). The design doc (`docs/DESIGN_DOCUMENT.md` §5.3) describes this as "per-rule classification."

## Why this way

The prompt includes both the rule's `condition` (as JSON via `model_dump_json()`) and its `action` text. Serializing the condition to JSON is the most compact way to give the model a machine-readable view of the predicate structure — the model can read `{"all": [{"field": "refund_amount", "op": "lt", "value": 100}]}` and recognize that it's a simple threshold comparison, which directly informs the `deterministic` classification.

`classify_zone` returns a plain `str` (not a `ZoneClassification`) because callers only need the string label for the `if/elif/else` branching in `classify_rules`. Returning the full `ZoneClassification` object would force callers to access `.zone` everywhere for no gain.

## Where to look

- [packages/core/src/skiljo_core/extraction/zones.py](packages/core/src/skiljo_core/extraction/zones.py) — `ZoneClassification`, `ZONE_CLASSIFICATION_PROMPT_V1`, `classify_zone()`, `classify_rules()`.
- [packages/core/tests/test_zones.py](packages/core/tests/test_zones.py) — two tests: one for `classify_zone` (single rule, single zone response), one for `classify_rules` (three rules, one response per zone).
- [packages/core/src/skiljo_core/schemas/rule_schema.py](packages/core/src/skiljo_core/schemas/rule_schema.py) — `LLMAssistedRule` (has `requires_human_approval: bool`), `HumanOnlyRule`.
- [packages/core/src/skiljo_core/schemas/skill_schema.py](packages/core/src/skiljo_core/schemas/skill_schema.py) — `DecisionZones` (the output type of `classify_rules`).
