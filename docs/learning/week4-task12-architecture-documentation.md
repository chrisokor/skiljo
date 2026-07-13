# Week 4, Task 12: ARCHITECTURE.md documentation [plan #47]

## What was built

A comprehensive `ARCHITECTURE.md` at the repo root that serves as the code-reader's companion to `docs/DESIGN_DOCUMENT.md`. Where the design document answers "what is this and why," ARCHITECTURE.md answers "where is it in the code, how does the mechanism work, and why this implementation specifically."

The document covers:
- A component map with an ASCII diagram and full directory tree
- Data model — all tables, their purpose, and the four system invariants the code enforces
- Key abstractions: Predicate DSL, Decision Zones, Shadow Policy, Contradiction Detection
- Extraction pipeline (four passes with file references per pass)
- Simulation engine (including the `asyncio.to_thread` pattern explained)
- LLM client and cache mechanics
- API layer with route table, auth details, async job pattern, and error envelope
- TypeScript SDK structure
- Streamlit demo (three pages, what each does)
- Testing strategy — unit tests, schema tests, CI-blocking eval harness
- Performance characteristics (latencies, cache hit rates, concurrency math)
- Security model (auth, LLM isolation, audit trail, known limitations)
- Future roadmap (v1.05 through v1.5 with concrete scope per version)
- Developer setup commands

## Non-obvious concepts involved

### Architecture documentation as developer onboarding

The goal of ARCHITECTURE.md is not exhaustiveness — `DESIGN_DOCUMENT.md` is exhaustive. The goal is enabling a developer who just cloned the repo to find the code that implements a concept within 10 minutes. That shapes every choice: reference file paths (`packages/core/src/skiljo_core/simulation/engine.py`) rather than abstract descriptions, include the actual function signature or snippet when it explains a mechanism, answer "why this, not that" at the implementation level.

### Explaining `asyncio.to_thread` correctly

The simulation engine uses `asyncio.to_thread(simulate_ticket, ...)` to wrap the synchronous `AnthropicClient.generate_structured()` call inside an async batch executor. The ARCHITECTURE.md explains why this is necessary: the Anthropic Python SDK's `messages.create` is synchronous and blocking. The batch executor is `async`. You can't `await` a sync call. `asyncio.to_thread` runs the sync call in a thread pool, releasing the event loop to handle the other `asyncio.gather` coroutines. Without this, the semaphore would bound Python thread context switches but not actual concurrent API calls.

This explanation is in `packages/core/src/skiljo_core/simulation/engine.py` — reading the code alone doesn't tell you why `to_thread` is there versus just `await simulate_ticket(...)`.

### `hmac.compare_digest` and timing attacks

The auth dependency (`packages/api/src/skiljo_api/dependencies.py`) uses `hmac.compare_digest(credentials.credentials, config.API_KEY)` rather than `credentials.credentials == config.API_KEY`. A naive string comparison in Python short-circuits — it returns `False` as soon as a character doesn't match. An attacker can measure response time to deduce how many leading characters of the correct key they've guessed. `hmac.compare_digest` compares all bytes unconditionally, taking constant time regardless of where the mismatch is. ARCHITECTURE.md surfaces this choice in the Security section so it's not confused for boilerplate.

### Schema-first codegen and its discipline

The `schemas/*.schema.json` files are canonical. `make codegen` produces `packages/core/src/skiljo_core/schemas/` (Pydantic) and `packages/sdk-ts/src/types.ts` (Zod) from them. The constraint — never hand-edit generated files — is documented prominently because developers will be tempted to fix a small thing in the Pydantic model without going through the schema. The codegen approach is explained as intentional: the schemas used by the LLM for structured output are the same schemas the application enforces, which is only true if the JSON Schema is canonical.

### Why "off limits" for `data/eval/test/`

The ARCHITECTURE.md re-states the test set prohibition in the developer setup section and in the testing section. This is social hygiene, not technical enforcement. The explanation — "never read, print, summarize, or tune against the test set, it runs only in CI" — appears twice so a developer who skips to setup instructions still sees it.

## Why this approach was chosen

The document was written bottom-up: gather the actual implementation (read `engine.py`, `anthropic_client.py`, `dependencies.py`, `contradictions.py`, `evaluator.py`, `pipeline.py`), then write explanations that reference the real code. This avoids architecture documents that drift from the implementation — every claim in ARCHITECTURE.md is grounded in a file that was read before writing the section.

Structure follows the reader's mental model: start with purpose and component map (orientation), then data model (what persists), then abstractions (the vocabulary), then the two core pipelines (extraction and simulation), then the surrounding layers (LLM client, API, SDK, demo), then cross-cutting concerns (testing, performance, security), then future work.

The document deliberately avoids re-explaining concepts in the glossary (e.g., the Predicate DSL, shadow policy, contradiction detection) — those entries link to existing week-3 debriefs. ARCHITECTURE.md summarizes the mechanism and points at the code, the debrief covers the concept.

## Where to look in the code

- `ARCHITECTURE.md` — the artifact itself
- `packages/core/src/skiljo_core/simulation/engine.py` — `simulate_batch()` (asyncio.to_thread + semaphore), `compute_report()`
- `packages/core/src/skiljo_core/simulation/executor.py` — three-zone cascade in `simulate_ticket()`
- `packages/core/src/skiljo_core/simulation/evaluator.py` — DSL evaluator (52 lines, pure Python)
- `packages/core/src/skiljo_core/simulation/contradictions.py` — detector with clustering and financial impact
- `packages/core/src/skiljo_core/llm/anthropic_client.py` — tool-use structured output, retry loop, cache integration
- `packages/core/src/skiljo_core/llm/base.py` — `LLMClient` Protocol and `StructuredResponse`
- `packages/core/src/skiljo_core/llm/cache.py` — `sha256` cache key, `session.merge()` upsert
- `packages/core/src/skiljo_core/extraction/pipeline.py` — `run_extraction_pipeline()` four-pass entry point
- `packages/api/src/skiljo_api/dependencies.py` — `verify_api_key()` with `hmac.compare_digest`
- `packages/api/src/skiljo_api/main.py` — FastAPI app setup and route registration
- `docs/DESIGN_DOCUMENT.md` — companion document, source of truth for design decisions and rationale
