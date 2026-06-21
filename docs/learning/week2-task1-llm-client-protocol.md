# Week 2, Task 1: LLM client protocol and Anthropic implementation

## What was built

A small abstraction layer between Skiljo's extraction code and the Anthropic API: an `LLMClient` interface (`generate_structured`) that any LLM provider could implement, and a first concrete implementation, `AnthropicClient`, that uses Anthropic's tool-use mode to get back data validated against a Pydantic schema.

## Key concepts

**[`Protocol`](GLOSSARY.md#protocol-structural-typing) instead of an abstract base class.** `LLMClient` is a `typing.Protocol`, not a class extraction code inherits from. `AnthropicClient` never writes `class AnthropicClient(LLMClient)` — it just happens to have a matching `generate_structured` method, and that's enough for mypy to accept it anywhere an `LLMClient` is expected. This matters because Task 4 later introduces `FakeLLMClient`, a test double that also satisfies the Protocol with zero coupling to `AnthropicClient`.

**Tool-use as a structured-output mechanism.** Anthropic's chat API normally returns free text. Passing a `tools=[...]` definition with `tool_choice` forcing that specific tool makes the model instead respond with a JSON object matching the tool's `input_schema` — which is generated directly from the Pydantic model via `schema.model_json_schema()`. The response comes back as a `tool_use` content block; `tool_use_block.input` is the raw dict, and `schema.model_validate(...)` is what actually proves it matches.

**[Dependency injection](GLOSSARY.md#dependency-injection-constructor-based) for testability.** `AnthropicClient.__init__` accepts an optional `client: anthropic.Anthropic | None`. In production code, nothing is passed and a real SDK client is constructed from `config.ANTHROPIC_API_KEY`. In tests, a `unittest.mock.Mock()` is passed instead, so `generate_structured` never touches the network — it just calls whatever `.messages.create()` the test wired up.

**[`StructuredResponse[T]`](GLOSSARY.md#pydantic-generict--typevar) as a generic dataclass.** `T = TypeVar("T", bound=BaseModel)` plus `class StructuredResponse(Generic[T])` lets the return type of `generate_structured(schema=Greeting, ...)` be inferred as `StructuredResponse[Greeting]`, so `result.data` is statically known to be a `Greeting`, not just "some BaseModel."

## Why this way

The design doc (`docs/DESIGN_DOCUMENT.md` §5.2) specifies this exact `LLMClient` Protocol shape and notes "the provider abstraction is implemented but only Anthropic is implemented for now" — i.e., the Protocol exists so a second provider (OpenAI, etc.) could be added later as "a one-file change," without touching any extraction code. Constructor-injected dependencies were chosen over patching the SDK module globally (`unittest.mock.patch`) because it's more explicit and doesn't require tests to know the SDK's internal import paths.

This task deliberately stops short of retry logic or call logging — those are Tasks 2 and 3, added incrementally on top of this same method.

## Where to look

- `packages/core/src/skiljo_core/llm/base.py` — the `LLMClient` Protocol and `StructuredResponse` dataclass.
- `packages/core/src/skiljo_core/llm/anthropic_client.py` — `AnthropicClient`, as it stood after Task 1 (before Tasks 2–3 added retry and logging on top).
- `packages/core/tests/test_anthropic_client.py::test_generate_structured_returns_validated_output` — the test exercising the mocked-SDK path.
