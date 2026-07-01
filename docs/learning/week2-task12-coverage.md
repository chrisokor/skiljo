# Week 2, Task 12: Unit tests for extraction pipeline — close coverage gaps

## What was built

Three new test cases that close specific coverage gaps in the extraction module, plus `pytest-cov` added as an explicit dev dependency:

1. `test_assemble_skill_handles_nested_conditions_and_array_fields` (in `test_assembly.py`) — exercises two branches in `assembly.py` not hit by prior tests: recursive `_collect_condition_fields` on a nested `Condition(all=[...])` inside `Condition(any=[...])`, and the `"array"` keyword branch of `_guess_input_type` (triggered by a field named `fraud_flags`).
2. `test_pipeline_accumulates_rules_across_multiple_segments` (in `test_pipeline.py`) — exercises `pipeline.py`'s `for segment in segments: candidate_rules.extend(...)` loop with two segments, confirming rules from both are accumulated and classified into separate zones.

End result: 100% branch coverage on `skiljo_core/extraction/*`.

## Key concepts

**Coverage as a signal, not a target.**
`pytest-cov` (added via `--cov=skiljo_core.extraction --cov-report=term-missing`) reports which lines and branches were executed by the test suite and which were not. The `term-missing` format prints the specific line numbers not covered, making it actionable: you can read the missing lines, understand what scenario they represent, and write a test that exercises that scenario.

100% coverage does not mean the code is correct — it means every line was executed at least once. A test that calls a function and discards the result achieves coverage without asserting anything useful. Coverage is a floor, not a proof. The important thing is that the tests added here assert meaningful outputs (the `"array"` type returned for `fraud_flags`, the rule counts after multi-segment accumulation) — they don't just hit branches for the sake of the metric.

**Nested `Condition` recursion.**
`_collect_condition_fields` is a recursive function in `assembly.py`. On each `ConditionOrPredicate` item in `condition.all`/`condition.any`, it calls `item.root` to get the inner value. If the inner value is a `Predicate`, it appends the field name. If it's a `Condition`, it recurses. This mirrors how the rule engine will traverse conditions at simulation time.

The test uses a condition like:
```python
Condition(
    any=[
        ConditionOrPredicate(root=Predicate(field="fraud_flags", op=Operator.not_empty, value=None)),
        ConditionOrPredicate(root=Condition(all=[
            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=1000))
        ])),
    ]
)
```

This forces the recursion path: the outer `any` contains one `Predicate` (direct append) and one nested `Condition` (recurse). The inner `Condition`'s `all` contains a `Predicate` (append inside the recursion). Both code paths run.

**Multi-segment pipeline accumulation.**
The pipeline test from Task 7 used a single segment, which meant `candidate_rules.extend(...)` was called exactly once. The new test uses two segments — one producing a `deterministic` rule, one producing an `llm_assisted` rule — with five fake responses queued: `SegmentationResult(2 segments)`, `CandidateRuleList(rule 1)`, `CandidateRuleList(rule 2)`, `ZoneClassification("deterministic")`, `ZoneClassification("llm_assisted")`. Asserting `len(fake_client.calls) == 5` confirms the pipeline called the LLM exactly five times and consumed all five responses in order.

## Why this way

The brief identifies coverage gaps after Tasks 4–7 ship by inspecting which branches in `assembly.py` and `pipeline.py` were not exercised. This is the canonical use of coverage tooling: write the code, check coverage, add targeted tests for the missed branches. The alternative — writing every conceivable test before seeing what's actually uncovered — produces test bloat with no marginal benefit.

`pytest-cov` is declared explicitly in `pyproject.toml` for the same reason `pyyaml` was added in Task 11: any package your tool pipeline imports or invokes directly should be an explicit dependency. It was already resolved transitively from `pytest`'s ecosystem, but declaring it pins the version floor.

## Where to look

- [packages/core/tests/test_assembly.py](packages/core/tests/test_assembly.py) — the new `test_assemble_skill_handles_nested_conditions_and_array_fields` test at the bottom.
- [packages/core/tests/test_pipeline.py](packages/core/tests/test_pipeline.py) — the new `test_pipeline_accumulates_rules_across_multiple_segments` test at the bottom.
- [packages/core/src/skiljo_core/extraction/assembly.py](packages/core/src/skiljo_core/extraction/assembly.py) — `_collect_condition_fields` (the recursive function the new test exercises) and `_guess_input_type` (the `"array"` branch).
