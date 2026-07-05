# Glossary

Running list of concepts introduced across learning debriefs, alphabetical by term. Each entry links to the debrief where it's explained in full.

## Cluster (contradiction detection)

A grouping of tickets by (amount_band, customer_segment) dimensions, used by the contradiction detector to identify systematic divergences. For example, all tickets with refund amounts in the $101–200 range and customer_segment="vip" form one cluster. The detector measures divergence rate per cluster (mismatches / cluster size) and flags clusters exceeding a threshold. See [Week 3 Task 5](week3-task5-contradiction-detection.md).

## Contradiction (planted divergence detection)

A record of systematic divergence between the skill's decision and ground-truth outcomes, identified by the contradiction detector. Each contradiction captures: the cluster it occurred in, the divergence rate, the most common (written, observed) decision pair, ticket count, and affected ticket IDs. Contradictions are measurable against planted divergences in the shadow policy — a good detector recovers planted patterns with high recall. See [Week 3 Task 5](week3-task5-contradiction-detection.md).

## Cache key (LLM response cache)

A `sha256` hex digest over the string `"{provider}|{model}|{prompt_version}|{prompt_text}"`. Changing any of the four components produces a completely different key, so a prompt edit automatically busts the cache for that prompt while leaving all other cached entries intact. Temperature-0 calls only — non-deterministic calls are never keyed or stored. See [Week 3 Task 1](week3-task1-llm-cache.md).

## `session.merge()` (SQLAlchemy upsert)

`Session.merge(instance)` issues a SELECT on the primary key, then INSERT if absent or UPDATE if present. Unlike `session.add()`, it doesn't raise `IntegrityError` on a duplicate primary key, making it the right tool for idempotent writes where the primary key is a content-addressed hash. See [Week 3 Task 1](week3-task1-llm-cache.md).

## `cast()` (mypy type narrowing, runtime no-op)

`typing.cast(T, x)` tells mypy to treat `x` as type `T` without any runtime check — it's a static-analysis directive only and compiles away to just `x`. Useful for narrowing union types in tests where the test's own structure guarantees the type is correct. For cases where you want a useful failure message if the assumption is wrong at runtime, prefer `assert x is not None` instead. See [Task 5](week2-task5-rule-extraction.md).

## FastAPI `HTTPException`

FastAPI's idiomatic way to abort a request with an HTTP error. `raise HTTPException(status_code=404, detail="...")` is caught by FastAPI's exception handler and converted to the appropriate HTTP response with a JSON body `{"detail": "..."}`. See [Task 9](week2-task9-jobs-endpoint.md).

## FastAPI `BackgroundTasks`

FastAPI's mechanism for running work after the HTTP response is sent. The endpoint registers a function via `background_tasks.add_task(fn, *args)` and returns immediately; the function runs afterward. Note: Starlette's `TestClient` runs background tasks *synchronously* before returning the simulated response, so tests can assert on DB state immediately without polling. See [Task 8](week2-task8-extract-endpoint.md).

## FastAPI `dependency_overrides`

A dict on the FastAPI `app` object that replaces dependency functions for tests. `app.dependency_overrides[get_llm_client] = lambda: fake_client` makes every request in that test use the fake instead of the real singleton. Must be cleared in `finally` to prevent leaking into other tests. See [Task 8](week2-task8-extract-endpoint.md).

## `model_dump(mode="json")`

A Pydantic v2 method that serializes a model to a plain Python dict, converting all nested models and enums to JSON-compatible primitives. `mode="json"` is important when passing data to another `model_validate(dict)` call — passing live model instances can skip nested re-validation. See [Task 7](week2-task7-assembly-pipeline.md).

## Divergence spec (planted contradiction)

A `DivergenceSpec` is an authored override that specifies how reality diverges from the written policy. It has a `condition` (predicates on ticket fields), a `shadow_decision` (what actually happens), and a `frequency` (0.0–1.0, how often). Used to generate synthetic tickets with planted contradictions: the base skill says one thing, but the ground truth (following the shadow policy) says another. This makes the contradiction detector's job measurable — it must recover the planted divergence pattern from simulation outcomes. See [Week 3 Task 4](week3-task4-shadow-policy-generator.md).

## Decision zones (deterministic / llm_assisted / human_only)

Three categories that classify how much autonomy the system can safely exercise on a policy rule at runtime. `deterministic` = mechanical execution from structured data; `llm_assisted` = LLM judgment needed but low-stakes enough to not require a human; `human_only` = too high-stakes or legally sensitive to automate. Zone assignment is extraction pass 3. See [Task 6](week2-task6-zone-classification.md).

## `ConditionOrPredicate` / `RootModel`

A Pydantic v2 `RootModel[T]` is a model whose entire value *is* the root value `T` (no named fields). `ConditionOrPredicate = RootModel[Predicate | Condition]` lets `Condition.all` hold either predicates or nested conditions in one list. Construction: `ConditionOrPredicate(root=Predicate(...))`. Access: `.root` returns the inner value. See [Task 5](week2-task5-rule-extraction.md).

## Dependency injection (constructor-based)

Passing a collaborator object (e.g. an SDK client) into a class's constructor instead of having the class construct it internally. Lets tests substitute a fake/mock without touching the class's code. See [Task 1](week2-task1-llm-client-protocol.md).

## Pydantic `Generic[T]` / `TypeVar`

A way to write one dataclass or model that's parameterized by another type, the same way `list[str]` is a list parameterized by `str`. `StructuredResponse[T]` means "a StructuredResponse whose `.data` field is exactly type `T`," checked statically by mypy. See [Task 1](week2-task1-llm-client-protocol.md).

## Pydantic `ValidationError`

The exception Pydantic raises when data doesn't match a model's schema (wrong type, missing required field, failed constraint). Catching it is how the retry loop detects a bad LLM response. See [Task 2](week2-task2-structured-output-retry.md).

## Planted contradiction

A deliberately introduced divergence between the written policy and reality, used to make contradiction detection measurable. During synthetic ticket generation, a `DivergenceSpec` is applied at a specified frequency (e.g. "VIP customers get approved 80% of the time even when over the $500 threshold"). The ground-truth labels on tickets reflect the planted divergence. When the extracted skill is simulated, it will report decisions that don't match the ground truth, surfacing the planted contradiction. A good contradiction detector should recover these planted patterns with high recall. See [Week 3 Task 4](week3-task4-shadow-policy-generator.md).

## Predicate DSL (Domain-Specific Language for conditions)

A constrained, table-driven language for expressing ticket-matching rules: `Predicate(field, op, value)` where `op` is one of 11 operators (`eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `in`, `not_in`, `contains`, `empty`, `not_empty`). Predicates are composed into `Condition` objects with `all` (AND) and `any` (OR) operators, supporting arbitrary nesting. Evaluated deterministically by `evaluate_predicate()` and `evaluate_condition()` — no LLM, no `eval()`, safe to run on untrusted data. See [Week 3 Task 3](week3-task3-rule-evaluator.md).

## `Protocol` (structural typing)

A `typing.Protocol` defines an interface by the methods/attributes a class must have, without that class needing to inherit from anything. Any class with a matching `generate_structured` method satisfies `LLMClient`, including a fake built purely for tests. See [Task 1](week2-task1-llm-client-protocol.md).

## SQLAlchemy `sessionmaker` / engine

An `engine` represents a connection pool to a specific database URL; a `sessionmaker` (commonly bound as `SessionLocal`) is a factory that produces new `Session` objects against that engine on demand. Code calls `SessionLocal()` to get a session scoped to one unit of work, rather than sharing one global session. See [Task 3](week2-task3-llm-call-logging.md).

## Test double (fake vs. mock)

A "fake" is a lightweight, hand-written stand-in that implements the real interface with simplified behavior (e.g. `FakeLLMClient` returns pre-programmed responses). A "mock" (e.g. `unittest.mock.Mock`) is a generic stand-in that records calls and can assert on them, with no real implementation behind it. This project uses mocks for the Anthropic SDK boundary (Task 1) and a fake for the higher-level `LLMClient` Protocol (Task 4) — see [Task 4](week2-task4-policy-segmentation.md) for why the boundary matters.

## Shadow policy

The *actual* decision-making logic that the synthetic ticket generator follows, as opposed to the *written* policy (what the extracted skill represents). A shadow policy is the written policy plus authored divergences: "the written policy says deny all $500+ refunds, but in practice VIP customers get approved 80% of the time." During ticket generation, ground truth follows the shadow policy, not the written policy. This prevents circular simulation (where the skill always matches its own source) and makes contradiction detection measurable — the detector must infer the divergences by observing that extracted rules don't predict the ground-truth outcomes. See [Week 3 Task 4](week3-task4-shadow-policy-generator.md).

## Tool-use (Anthropic API)

A mode where the API is given a JSON Schema "tool" definition and forced to respond by calling it with arguments matching that schema, instead of free-form text. This is how the LLM client gets back data that's guaranteed to (attempt to) match a Pydantic model's shape. See [Task 1](week2-task1-llm-client-protocol.md).

## `mypy` type narrowing via `assert`

A runtime `assert x is not None` also tells mypy's static analysis "treat `x` as non-`None` for the rest of this scope." Used when a value is typed `T | None` (because it's read from environment/config) but a particular code path can only run correctly when it's actually set. See [Task 3](week2-task3-llm-call-logging.md).
