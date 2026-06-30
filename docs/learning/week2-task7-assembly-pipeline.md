# Week 2, Task 7: Extraction pass 4 — assembly, schema validation, and pipeline orchestration

## What was built

Two files that complete the extraction pipeline:

1. **`assembly.py`** — takes a classified `DecisionZones` struct and assembles a `Skill` object: collects all field names referenced in rule conditions, guesses their input types by keyword, builds a candidate dict, and validates it with `Skill.model_validate(candidate)`. If that validation fails (e.g. the `skill_name` argument violates the schema's regex pattern), exactly one LLM repair call is made — using Task 2's `generate_structured` retry mechanism, which already handles up to 3 retry attempts internally.

2. **`pipeline.py`** — the single public entry point for the entire extraction pipeline. `run_extraction_pipeline` calls passes 1→4 in sequence: `segment_policy → extract_rules (per segment) → classify_rules → assemble_skill`. This is what Task 8's API endpoint will call.

## Key concepts

**Assembly-then-repair instead of a separate repair loop.**
The design doc mentions a "repair loop" for assembly, but the implementation deliberately avoids writing a second retry loop. Instead: build deterministically, validate, and fall back to `generate_structured` (which already has its own 3-attempt retry with validation feedback from Task 2) only on `ValidationError`. This reuses the existing mechanism rather than duplicating it. The result is a simple try/except that adds exactly one call on failure, with Task 2's machinery handling the rest.

**Deterministic input inference via keyword matching.**
`_guess_input_type` maps field names to JSON Schema primitive types (`number`, `integer`, `array`, `string`) using token substrings ("amount" → `number`, "days" → `integer`, etc.). This isn't ML — it's a heuristic table. It will be wrong for unusual field names, but that's acceptable at this stage: the LLM repair path can correct it on a per-case basis if the assembled Skill fails validation. The design doc acknowledges that the extraction pipeline's output is a *candidate* that may need human review.

**`model_dump(mode="json")` for cross-model serialization.**
`assemble_skill` does `decision_zones.model_dump(mode="json")` when building the candidate dict. `mode="json"` converts all Pydantic models inside `DecisionZones` to plain JSON-compatible dicts/lists — the same serialization used when sending data over the wire. This is important because `Skill.model_validate(candidate)` expects plain data (not nested Pydantic instances) when called with a dict; passing live model instances directly can cause Pydantic v2 to skip re-validation of nested structures.

**Recursive field collection through `ConditionOrPredicate`.**
`_collect_condition_fields` recurses through `Condition.all`/`.any` lists, accessing `item.root` on each `ConditionOrPredicate` to get the inner `Predicate | Condition`. When it finds a `Predicate`, it appends `inner.field`; when it finds a nested `Condition`, it recurses. This handles arbitrarily deeply nested `all`/`any` conditions — the same structural recursion that the rule engine will use at simulation time.

**Pipeline as a thin coordinator.**
`pipeline.py` has no logic of its own — it's a straight-line sequence of calls to the four pass functions, forwarding the `model` parameter through. The passes are loosely coupled (each takes `llm_client` + their specific input and returns their specific output), which is why the pipeline can be this thin. Testing the pipeline end-to-end with `FakeLLMClient` confirms the stitching — that responses are consumed in the right order and returned to the right pass.

## Why this way

The four-pass design (from `docs/DESIGN_DOCUMENT.md` §5.3) keeps each LLM call's job narrow: segmentation divides the text, rule extraction reads one segment, zone classification labels one rule, assembly constructs the final spec. `pipeline.py` is the place where those four narrow calls are composed into one operation — keeping composition separate from each pass's logic.

The repair call reusing `generate_structured` (rather than a bespoke loop) aligns with the invariant that every LLM call is logged to `llm_calls` (Task 3): since `generate_structured` calls the logger, the repair call is automatically observable without any extra code.

## Where to look

- [packages/core/src/skiljo_core/extraction/assembly.py](packages/core/src/skiljo_core/extraction/assembly.py) — `_collect_condition_fields`, `_collect_fields`, `_guess_input_type`, `_build_inputs`, `assemble_skill`.
- [packages/core/src/skiljo_core/extraction/pipeline.py](packages/core/src/skiljo_core/extraction/pipeline.py) — `run_extraction_pipeline`.
- [packages/core/tests/test_assembly.py](packages/core/tests/test_assembly.py) — tests for the happy path (no LLM call) and the repair path (one LLM call with `prompt_version="assembly_repair_v1"`).
- [packages/core/tests/test_pipeline.py](packages/core/tests/test_pipeline.py) — end-to-end test with 3 fake responses in order (segmentation, rule extraction, zone classification), asserting `len(fake_client.calls) == 3` to confirm assembly needed no repair call.
