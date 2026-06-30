# Glossary

Running list of concepts introduced across learning debriefs, alphabetical by term. Each entry links to the debrief where it's explained in full.

## `cast()` (mypy type narrowing, runtime no-op)

`typing.cast(T, x)` tells mypy to treat `x` as type `T` without any runtime check — it's a static-analysis directive only and compiles away to just `x`. Useful for narrowing union types in tests where the test's own structure guarantees the type is correct. For cases where you want a useful failure message if the assumption is wrong at runtime, prefer `assert x is not None` instead. See [Task 5](week2-task5-rule-extraction.md).

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

## `Protocol` (structural typing)

A `typing.Protocol` defines an interface by the methods/attributes a class must have, without that class needing to inherit from anything. Any class with a matching `generate_structured` method satisfies `LLMClient`, including a fake built purely for tests. See [Task 1](week2-task1-llm-client-protocol.md).

## SQLAlchemy `sessionmaker` / engine

An `engine` represents a connection pool to a specific database URL; a `sessionmaker` (commonly bound as `SessionLocal`) is a factory that produces new `Session` objects against that engine on demand. Code calls `SessionLocal()` to get a session scoped to one unit of work, rather than sharing one global session. See [Task 3](week2-task3-llm-call-logging.md).

## Test double (fake vs. mock)

A "fake" is a lightweight, hand-written stand-in that implements the real interface with simplified behavior (e.g. `FakeLLMClient` returns pre-programmed responses). A "mock" (e.g. `unittest.mock.Mock`) is a generic stand-in that records calls and can assert on them, with no real implementation behind it. This project uses mocks for the Anthropic SDK boundary (Task 1) and a fake for the higher-level `LLMClient` Protocol (Task 4) — see [Task 4](week2-task4-policy-segmentation.md) for why the boundary matters.

## Tool-use (Anthropic API)

A mode where the API is given a JSON Schema "tool" definition and forced to respond by calling it with arguments matching that schema, instead of free-form text. This is how the LLM client gets back data that's guaranteed to (attempt to) match a Pydantic model's shape. See [Task 1](week2-task1-llm-client-protocol.md).

## `mypy` type narrowing via `assert`

A runtime `assert x is not None` also tells mypy's static analysis "treat `x` as non-`None` for the rest of this scope." Used when a value is typed `T | None` (because it's read from environment/config) but a particular code path can only run correctly when it's actually set. See [Task 3](week2-task3-llm-call-logging.md).
