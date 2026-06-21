# Week 2, Task 4: Extraction pass 1 — policy segmentation

## What was built

The first of the extraction pipeline's four LLM passes: `segment_policy()`, which takes raw policy text and asks the model to split it into typed segments (eligibility, thresholds, exceptions, etc.) — the input the next three passes will work from, one segment at a time. Alongside it: `FakeLLMClient`, a test double for the `LLMClient` Protocol that every later extraction-pass test will reuse.

## Key concepts

**[Test double](GLOSSARY.md#test-double-fake-vs-mock): fake vs. mock, and why this task needs a different one than Task 1.** Task 1's tests mock the *Anthropic SDK* directly (`Mock()` standing in for `anthropic.Anthropic`) — appropriate there because the thing under test, `AnthropicClient`, IS the translation layer between the SDK's shape and the `LLMClient` Protocol's shape, so the test has to operate below that translation. Everything from this task onward (`segment_policy` and later passes) is written against the `LLMClient` Protocol itself, one layer up — it never imports `anthropic_client.py` at all. So its tests use `FakeLLMClient`, a hand-written class that satisfies the `LLMClient` Protocol directly: construct it with a list of pre-built Pydantic instances, and each call to `generate_structured` pops and returns the next one, recording what it was called with along the way.

**Why `FakeLLMClient` ships from `skiljo_core.testing`, not a `tests/` file.** A later task (8) needs the exact same fake inside `packages/api/tests/` — a different Python package with its own pytest test directory. Test files in this project's `tests/` directories aren't a real importable package (no `__init__.py`), so a fixture file sitting in `packages/core/tests/` isn't reliably importable from `packages/api/tests/`. Putting `FakeLLMClient` in `packages/core/src/skiljo_core/testing.py` instead means it ships as part of the normal `skiljo_core` package — already installed into the shared `uv` workspace venv — so any test anywhere can just `from skiljo_core.testing import FakeLLMClient`, the same way it would import any other part of the library.

**Pydantic models as the LLM's output contract, one level removed from the canonical schema.** `Segment` and `SegmentationResult` are new Pydantic models defined in `segmentation.py`, not reused from the project's canonical `schemas/*.schema.json`-generated types (`Skill`, `DeterministicRule`, etc.). That's intentional: a "segment" is an internal intermediate value used only while assembling a `Skill` — it's never persisted or exposed through the API — so it has no business living in the schemas that *are* the persisted/API contract.

## Why this way

The design doc (`docs/DESIGN_DOCUMENT.md` §5.3) describes segmentation as "a small Claude call with structured output" whose purpose is narrowing — "this pass keeps the heavy extraction passes focused on the right text." Implementing it as a single `generate_structured` call against a `SegmentationResult` schema (a list of `Segment`s) is the most direct translation of that description; there's no looping or per-segment-type branching at this stage, since classifying *which* segment types matter happens implicitly via the prompt instructions, not in code.

## Where to look

- `packages/core/src/skiljo_core/testing.py` — `FakeLLMClient`.
- `packages/core/src/skiljo_core/extraction/segmentation.py` — `Segment`, `SegmentationResult`, `segment_policy()`, and the segmentation prompt.
- `packages/core/tests/test_segmentation.py` — the test, using `FakeLLMClient` to supply a canned `SegmentationResult`.
