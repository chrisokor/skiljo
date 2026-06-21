# Week 2, Task 2: Structured output via tool-use with validation retry

## What was built

`AnthropicClient.generate_structured` now retries up to 3 times if the model's response doesn't validate against the requested Pydantic schema, feeding the validation error back into the prompt on each retry, instead of raising on the very first bad response.

## Key concepts

**[`pydantic.ValidationError`](GLOSSARY.md#pydantic-validationerror) as the retry trigger.** `schema.model_validate(tool_use_block.input)` raises `ValidationError` (not, say, a generic `ValueError`) whenever the model's JSON doesn't match the schema — wrong type, missing required field, failed constraint. Catching specifically that exception type (not a bare `except Exception`) means a genuinely unexpected error (e.g. a bug in this code) still propagates immediately instead of being silently retried.

**Why the retry prompt is rebuilt from the original, not the previous attempt's.** Each retry's prompt is `f"{prompt}\n\n...{exc}..."` — built from the original `prompt` variable, not from `current_prompt` (which already has a previous error message appended). If it accumulated, attempt 3's prompt would contain both attempt 1's and attempt 2's error messages stacked on top of each other, getting longer and more confusing each time. Rebuilding from the original keeps every retry's prompt the same length: original instructions plus exactly one error message.

**Attempt counting as the loop's exit condition.** The loop is `for attempt in range(1, max_attempts + 1)`, and a successful validation `return`s immediately with that attempt number. If all `max_attempts` iterations fail, the loop body never executes a `return` — control falls through to `raise last_error` after the loop. This is why `assert last_error is not None` sits right before the raise: if every attempt failed, `last_error` is guaranteed to have been set at least once, but mypy can't infer that purely from the loop structure.

## Why this way

The design doc (`docs/DESIGN_DOCUMENT.md` §5.2) specifies "retries on schema validation failure up to N times with feedback" without pinning down exactly how the feedback should be delivered. Re-sending the full original prompt with one error message appended (rather than maintaining a growing multi-turn conversation with the model) keeps the implementation simple and keeps token usage from growing with each retry — at the cost of the model not literally "seeing" its own previous wrong answer, just a description of what was wrong with it.

## Where to look

- `packages/core/src/skiljo_core/llm/anthropic_client.py` — the `for attempt in range(...)` loop inside `generate_structured`.
- `packages/core/tests/test_anthropic_client.py::test_retries_once_on_invalid_output_then_succeeds` and `::test_raises_after_three_failed_attempts` — the two tests added this task, both asserting on the mocked SDK's exact call count.
