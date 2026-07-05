# Week 3, Task 3: Rule evaluator for deterministic zone

## What was built

The pure-Python predicate DSL evaluator: three functions that check whether a ticket matches a rule's condition. `evaluate_predicate()` tests a single comparison (e.g., "refund_amount < 100"); `evaluate_condition()` combines predicates into `all` (AND) or `any` (OR) compositions, supporting arbitrary nesting; `evaluate_condition_or_predicate()` dispatches between the two based on the input type. No LLM, no external runtime — just deterministic logic on dictionaries.

## Key concepts

**Why a constrained DSL instead of `eval()`.** The policy rules must be inspectable, auditable, and safe to execute on arbitrary data without risk of code injection. A Python `eval()` on an untrusted string is a security nightmare (and not reproducible across languages if we ship this to TypeScript). Instead, `Operator` is an enum of 11 comparison operations (`eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `in`, `not_in`, `contains`, `empty`, `not_empty`), and a `Predicate` is `{field: str, op: Operator, value: Any}`. The evaluator is a table-driven dispatch: for each operator, apply the specific logic. This is the standard pattern for rules engines — e.g., Drools, Jess, Shopify's Flow logic. The DSL is limited on purpose: no arithmetic, no string interpolation, no function calls. It's expressive enough for refund/credit policy conditions (amount thresholds, customer segment membership, time windows, flag presence) without the surface area of a general programming language.

**`ConditionOrPredicate` as a discriminated union — recursive structure through type delegation.** A `Condition` can have an `all` or `any` field, each holding a list of `ConditionOrPredicate`. The `ConditionOrPredicate` is a Pydantic `RootModel[Predicate | Condition]` — either a leaf predicate or a nested condition. When `evaluate_condition_or_predicate()` receives one, it checks `isinstance(cop.root, Predicate)` to dispatch: if it's a predicate, evaluate it directly; if it's a condition, recurse. This pattern lets you build arbitrarily nested trees — `all: [amount < 500, any: [vip, premium]]` — without separate AST classes. The cost is one extra `.root` accessor on every element, but the payoff is simplicity and composability.

**`Condition.model_rebuild()` — fixing forward references.** In the generated schema, `Condition` refers to `ConditionOrPredicate`, which refers back to `Condition` (recursive). Pydantic v2 requires `model_rebuild()` to be called at the module level after both models are defined, so the later model's forward reference resolves. This is a one-liner in the codegen'd file and must not be removed.

**Vacuous truth / falsehood of empty compositions.** `all([])` returns `True` in Python (vacuous truth: all zero elements satisfy any predicate). `any([])` returns `False` (no elements exist to satisfy a predicate, so "at least one" is false). The tests explicitly verify this: `Condition(all=[])` should evaluate to `True` and `Condition(any=[])` to `False`. This is mathematically sound and important for corner cases: an empty condition set in a rule should probably allow the action, not deny it (conservative default).

**Handling missing fields and `None` values.** `ticket.get(field)` returns `None` if the field doesn't exist. Comparisons (`lt`, `lte`, `gt`, `gte`) require a value to exist, so we short-circuit to `False` if `fv is None`. `eq` and `neq` allow `None` (a missing field is not equal to any non-None value). `empty` / `not_empty` explicitly check for `None` or empty string/list. This makes the evaluator robust to sparse tickets and missing optional fields.

**`contains` over strings and lists.** The `contains` operator needs to handle two cases: (1) substring search on a string field ("reason" contains "defect"), and (2) membership in a list field ("fraud_flags" contains "suspicious_ip"). The implementation checks `isinstance(fv, str)` first and does substring search, then checks `isinstance(fv, list)` for membership. If the field is neither, it returns `False` (safe default — can't contain something if you're not a container).

## Why this way

The evaluator is deterministic and table-driven by design. Every operator is self-contained — no cross-operator logic or state. Tests are parametrized to cover all 11 operators × multiple values, plus boundary cases (missing fields, None values, nested conditions). The recursive structure (`Condition` holding a list of `ConditionOrPredicate`, where each can be a `Condition` again) matches the grammar users write: nested logical compositions are natural.

The separation of concerns is intentional: extraction (week 2) *produces* rules with conditions; the evaluator (this task) *executes* those conditions. The LLM never runs during simulation — extraction is a one-time offline step, then tickets are evaluated in hot loops. This makes simulation fast and reproducible.

## Where to look

- [packages/core/src/skiljo_core/simulation/evaluator.py](packages/core/src/skiljo_core/simulation/evaluator.py) — `evaluate_predicate()`, `evaluate_condition_or_predicate()`, `evaluate_condition()`.
- [packages/core/tests/test_evaluator.py](packages/core/tests/test_evaluator.py) — 30 parametrized and nested tests covering all operators and compositions.
- [packages/core/src/skiljo_core/schemas/rule_schema.py](packages/core/src/skiljo_core/schemas/rule_schema.py) — `Operator`, `Predicate`, `Condition`, `ConditionOrPredicate` definitions (codegen'd from `schemas/rule.schema.json`).
