# Extraction Pipeline

Operator and maintainer reference for the extraction pipeline: what each pass does, what it produces, where it can fail, and how to debug it. For the one-page architectural summary see [ARCHITECTURE.md Section 5](../ARCHITECTURE.md#5-extraction-pipeline); for the original design rationale see [DESIGN_DOCUMENT.md Section 5.3](DESIGN_DOCUMENT.md) and [Section 4](DESIGN_DOCUMENT.md) ("Core abstractions and data model").

Entry point: `run_extraction_pipeline()` in `packages/core/src/skiljo_core/extraction/pipeline.py`. It takes an `LLMClient`, raw policy text, a skill name, and a trigger, and returns a validated `Skill`.

```python
def run_extraction_pipeline(llm_client, policy_text, skill_name, trigger, model=...) -> Skill:
    segments = segment_policy(llm_client, policy_text, model=model)
    candidate_rules = [r for segment in segments for r in extract_rules(llm_client, segment, model=model)]
    decision_zones = classify_rules(llm_client, candidate_rules, model=model)
    return assemble_skill(llm_client, skill_name=skill_name, trigger=trigger, decision_zones=decision_zones, model=model)
```

Four sequential LLM-backed passes, each a separate module. Every LLM call goes through `LLMClient.generate_structured()` (`packages/core/src/skiljo_core/llm/base.py`), which forces the response into a Pydantic schema via Anthropic tool-use, retries up to 3 attempts on `ValidationError` (feeding the validation error back into the prompt), and — for temperature-0 calls — checks/writes the LLM response cache (`packages/core/src/skiljo_core/llm/cache.py`, see the [Cache key](learning/GLOSSARY.md#cache-key-llm-response-cache) glossary entry). Every call is logged to `llm_calls` regardless of cache hit or miss.

## Pass 1 — Segmentation

`packages/core/src/skiljo_core/extraction/segmentation.py`, prompt `segmentation_v1`.

Splits the raw policy text into typed sections (`eligibility`, `thresholds`, `approvals`, `exceptions`, `refund_methods`, `audit_requirements`, or `other`) via a single structured-output call that returns a `SegmentationResult` (a list of `Segment{segment_type, text}`). The prompt explicitly instructs the model not to paraphrase — `text` must be the exact source text for that section, because Pass 2's prompts and any future citation-resolution step depend on segment text being a faithful excerpt, not a summary.

**Edge cases:** a policy with no headings or an unusual structure still gets a segment list — the model falls back to `other` for anything that doesn't fit the six named types. A very short policy (e.g. a one-paragraph excerpt from the corpus) typically comes back as a single segment.

## Pass 2 — Rule Extraction

`packages/core/src/skiljo_core/extraction/rules.py`, prompt `rule_extraction_v1`.

Runs once per segment (not once per document), with a segment-type-specific prompt — the `{segment_type}` from Pass 1 is interpolated directly into the prompt so the model knows it's extracting, say, threshold rules vs. exception rules from that particular block of text. Each call returns a `CandidateRuleList` (a list of `DeterministicRule{condition, action, citation}`), where `condition` is built from the [Predicate DSL](learning/GLOSSARY.md#predicate-dsl-domain-specific-language-for-conditions). The citation is section-relative and must contain a half-open character span plus exact `quoted_text` from the segment. The pipeline concatenates the rule lists across all segments before Pass 3 — see `test_pipeline_accumulates_rules_across_multiple_segments` in `packages/core/tests/test_pipeline.py` for the exact accumulation behavior (N segments → N `generate_structured` calls, rules concatenated in segment order).

At this stage every rule is provisionally a `DeterministicRule` — the condition/action shape is identical across zones; only Pass 3 decides which zone a rule ultimately belongs to.

## Pass 3 — Zone Classification

`packages/core/src/skiljo_core/extraction/zones.py`, prompt `zone_classification_v1`.

Classifies each candidate rule (one LLM call per rule) into exactly one of the three [decision zones](learning/GLOSSARY.md#decision-zones-deterministic--llm_assisted--human_only): `deterministic`, `llm_assisted`, or `human_only`. The prompt gives the model the rule's condition (as JSON) and action text, plus one example of each zone (mechanical numeric threshold → deterministic; "goodwill exception requiring manager judgment" → llm_assisted; "refund above $10K" → human_only).

`classify_rules()` fans a `DeterministicRule` list out into a `DecisionZones{deterministic, llm_assisted, human_only}` object: rules classified `deterministic` pass through unchanged; rules classified `llm_assisted` are rewrapped as `LLMAssistedRule` with `requires_human_approval=True` hardcoded (this is a `Literal[True]` in the schema — the field only exists to be true); rules classified `human_only` are rewrapped as `HumanOnlyRule`.

**Cost note (CLAUDE.md Section "Environment"):** Passes 1 and 3 are the cited candidates for a cheaper model (Haiku), since segmentation and per-rule zone classification are comparatively low-reasoning-load calls one-per-segment or one-per-rule; Pass 2 (rule extraction) is the pass most likely to need a stronger model. This isn't wired up as separate config yet — `model` is a single parameter threaded through the whole pipeline — but it's the intended lever if per-pass model selection is added.

## Pass 4 — Assembly and Validation

`packages/core/src/skiljo_core/extraction/assembly.py`.

`assemble_skill()` does three things: (1) walks every rule's `Condition` tree (`_collect_condition_fields`, handling arbitrary `all`/`any` nesting via `ConditionOrPredicate`) to collect the set of ticket fields referenced anywhere in the skill; (2) infers an input type per field from its name via a simple substring heuristic (`_guess_input_type` — fields containing `amount|price|fee|rate|percent` → `number`, `days|count|version|tokens` → `integer`, `flags|tags|items` → `array`, else `string`); (3) builds a candidate `Skill` dict and validates it against the Pydantic-generated `Skill` model.

**The repair loop:** if `Skill.model_validate(candidate)` raises `ValidationError`, the pipeline does *not* retry the whole extraction — it sends the invalid draft plus the exact validation error to a repair prompt (`assembly_repair_v1`) and asks the model to return a corrected `Skill` that fixes *only* that violation. This is a single repair attempt at the assembly level (distinct from the 3-attempt retry loop inside `generate_structured()`, which handles the LLM producing invalid JSON/schema on a single call — assembly's repair loop handles the LLM's structurally-valid-but-semantically-wrong output, e.g. an uppercase `skill_name` that violates the `^[a-z_][a-z0-9_]*$` pattern). See `test_assemble_skill_repairs_invalid_skill_name_via_llm` in `packages/core/tests/test_assembly.py` for the canonical example — the happy path (`test_assemble_skill_succeeds_without_llm_call_when_valid`) makes zero LLM calls.

## Citations

Every extracted rule has a schema-required singular `citation` with a half-open character span and exact `quoted_text`. Pass 2 requests section-relative citations. The pipeline validates each citation against its source segment, resolves the segment uniquely within the policy text, converts the span to document-relative offsets, and validates it again against the full policy before assembly. Invalid candidate citations are dropped; extraction fails when no valid candidate rule remains. `assemble_skill()` also validates every final rule citation against the source policy, including repaired output.

The eval harness's `citation_resolution()` scorer (see [`docs/evals.md`](evals.md)) evaluates the current singular schema shape (`citation.span.start`, `citation.span.end`, `citation.quoted_text`) and retains legacy plural-fixture support only for scorer-test compatibility. Citation resolution remains a hard invariant for real extraction output.

## Failure modes and debugging

- **Pass 2 or 3 raises after 3 attempts.** `AnthropicClient.generate_structured()` re-raises the last `ValidationError` if all 3 attempts fail schema validation — this bubbles straight out of `run_extraction_pipeline()`. Check the logged `llm_calls` row (via `LLMCallLogger`) for the actual model output that failed validation; the validation error text is fed back into the prompt on retries, so 3 consecutive failures usually means the schema itself is confusing the model (e.g. an operator name it doesn't recognize), not a transient issue.
- **Pass 4 assembly repair also fails validation.** `assemble_skill()`'s repair path calls `generate_structured()` once more with schema `Skill` directly; if that also fails validation it raises the same way (there's no second repair attempt — CLAUDE.md's "repair loop max 2 attempts" describes the target design; the current code makes exactly one repair call).
- **Unexpected input types in the assembled `Skill`.** `_guess_input_type()` is a substring heuristic on field *names*, not on any type information the model provides — a field like `discount_percent_flags` would incorrectly get typed `array` (matches `flags` before `percent`... actually the checks run `amount/price/fee/rate/percent` first, so this specific example resolves to `number`; but any field name that collides with two categories is decided by check order in `_guess_input_type`). If a skill's inputs look wrong, check the field name against that function directly rather than assuming an LLM error.
- **Empty or malformed policy text.** Segmentation always returns at least a fallback segment set from the model; there's no explicit empty-input guard in `segment_policy()` — an empty string will still produce an LLM call and whatever `SegmentationResult` the model chooses to return for empty input (typically an empty `segments` list, which then produces zero rules and an empty `DecisionZones`).
- **Debugging a specific extraction run.** Every pass's LLM call carries a distinct `prompt_version` (`segmentation_v1`, `rule_extraction_v1`, `zone_classification_v1`, `assembly_repair_v1`) — filter `llm_calls` by `prompt_version` to isolate which pass produced a bad result, and cross-reference `cached=true/false` to rule out "stale cache" as the cause before assuming a prompt regression.

## Testing

Unit tests per pass, all using `FakeLLMClient` (`packages/core/src/skiljo_core/testing`) so no real Anthropic calls happen: `test_segmentation.py`, `test_rules.py`, `test_zones.py`, `test_assembly.py`, and an end-to-end `test_pipeline.py` that stubs all four passes' responses and asserts exact LLM-call counts (a useful regression check — if a pass starts making 2 calls instead of 1, or 0, the call-count assertion catches it immediately). See [`docs/evals.md`](evals.md) for how extraction quality is measured against labeled ground truth beyond these unit tests.
