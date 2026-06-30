# Week 2, Task 5: Extraction pass 2 — rule extraction per segment

## What was built

The second LLM pass of the extraction pipeline: `extract_rules()`, which takes one `Segment` (output of pass 1) and asks the model to identify every distinct rule in that segment's text — returning a list of `DeterministicRule` objects whose `condition` and `action` fields are populated, but whose decision zone is not yet assigned (that's pass 3's job).

## Key concepts

**`RootModel` and `ConditionOrPredicate` — why the list element isn't a bare `Predicate`.**
The `Condition` model has fields `all: list[ConditionOrPredicate] | None` and `any: list[ConditionOrPredicate] | None`. `ConditionOrPredicate` is defined as `RootModel[Predicate | Condition]` — a Pydantic v2 `RootModel` wrapping a union of two types.

A `RootModel` is a Pydantic model whose entire value *is* the root value (no named fields): `ConditionOrPredicate(root=Predicate(...))` holds the inner `Predicate` at `.root`. This design lets `Condition.all` hold either predicates or nested conditions in the same list — the "or" is modelled as a union inside a RootModel, not as two separate list fields.

In practice, this means:
- **Construction:** `ConditionOrPredicate(root=Predicate(field="x", op=Operator.lt, value=10))` — you must wrap explicitly.
- **Access:** `condition.all[0].root` gives back the inner `Predicate` or `Condition`; you then access `.field`, `.op`, `.value` on the inner object.

The Week 2 plan's test template had a subtle inconsistency here: it used bare `Predicate(...)` in the fixture but accessed `.root` in the assertions. The implementer correctly identified that explicit `ConditionOrPredicate(root=Predicate(...))` wrapping is needed, and wrote the test accordingly. See [Task 4](week2-task4-policy-segmentation.md) for the broader context of how this extraction layer uses structured output.

**`cast()` for mypy type narrowing in tests.**
After retrieving `condition.all` (typed `list[ConditionOrPredicate] | None`), the test uses `cast(list[ConditionOrPredicate], condition.all)` to tell mypy "treat this as the non-None type" without a runtime assertion. `cast()` is a mypy directive — it has zero effect at runtime and doesn't validate anything; it simply suppresses the `None`-union warning so the rest of the test can operate on list subscripts without static errors. For cases where you also want a useful failure message if the value *is* `None`, `assert condition.all is not None` (which narrows the type and raises `AssertionError` on failure) is the stronger choice — see [GLOSSARY.md](GLOSSARY.md#mypy-type-narrowing-via-assert) for the `assert`-based narrowing pattern used elsewhere in this codebase.

**Segment-scoped prompting — why one call per segment.**
`extract_rules` is called once per segment (not once for the whole policy). The prompt template includes `{segment_type}` and `{segment_text}`, so the model sees a small, already-classified slice of text ("you are working on a 'thresholds' section") rather than the full policy. This keeps each extraction call focused: the model isn't asked to identify where rules live *and* extract them *and* classify their zone all at once.

## Why this way

The four-pass design (`docs/DESIGN_DOCUMENT.md` §5.3) deliberately separates *where the rules are* (segmentation) from *what the rules say* (rule extraction) from *what zone they fall into* (classification). Decomposing into passes lets each LLM call operate at its natural scope: a classification call that sees a 3-sentence threshold paragraph and one candidate rule is far more reliable than a monolithic call that sees a 20-page policy and must do all four jobs at once.

`CandidateRuleList` is a thin wrapper (`BaseModel` with `rules: list[DeterministicRule]`) rather than returning a raw list directly, because `generate_structured` requires a Pydantic model type as its schema argument — it needs a named root model, not a bare `list[...]`. Wrapping in `CandidateRuleList` is the minimum struct needed to satisfy that constraint.

## Where to look

- [packages/core/src/skiljo_core/extraction/rules.py](packages/core/src/skiljo_core/extraction/rules.py) — `CandidateRuleList`, `RULE_EXTRACTION_PROMPT_V1`, `extract_rules()`.
- [packages/core/tests/test_rules.py](packages/core/tests/test_rules.py) — the test, showing the correct `ConditionOrPredicate(root=Predicate(...))` construction and `.root.field` access pattern.
- [packages/core/src/skiljo_core/schemas/rule_schema.py](packages/core/src/skiljo_core/schemas/rule_schema.py) — `ConditionOrPredicate`, `Condition`, `Predicate`, `Operator` definitions (codegen'd from `schemas/rule.schema.json`).
