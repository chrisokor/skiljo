# Week 2, Task 3: LLM call logging to Postgres

## What was built

Every call `AnthropicClient` makes to the Anthropic API — successful or not, including each failed retry attempt from Task 2 — is now written as its own row to the `llm_calls` table (created back in Week 1's database schema). A new `LLMCallLogger` class owns the writing; a new `db/session.py` module provides the SQLAlchemy session factory it needs.

## Key concepts

**[`sessionmaker`/engine](GLOSSARY.md#sqlalchemy-sessionmaker--engine) as a factory, not a shared connection.** `db/session.py` builds one module-level `engine` (a connection pool bound to `DATABASE_URL`) and one `SessionLocal = sessionmaker(bind=engine)`. Code elsewhere calls `SessionLocal()` to get a *new* `Session` each time, used as a context manager (`with SessionLocal() as session: ...`). `LLMCallLogger.log()` does exactly this once per call, so each logged row is its own independent transaction — a failure logging attempt 2 can't roll back the row already committed for attempt 1.

**Logging every attempt, not just the winner.** Inside `generate_structured`'s retry loop, the logging call sits *before* the `try: schema.model_validate(...)` block — so a `ValidationError` on attempt 1 still gets logged (with whatever invalid JSON the model returned), and then the loop continues to attempt 2, which gets logged separately. This is deliberate: the whole point of the `llm_calls` table (per `docs/DESIGN_DOCUMENT.md`'s "every LLM call is logged" invariant) is cost/latency observability, and a retried-and-discarded call still cost real tokens and time.

**[`mypy` type narrowing via `assert`](GLOSSARY.md#mypy-type-narrowing-via-assert) — a deviation from the plan's literal code.** `config.DATABASE_URL` is typed `str | None` (it's read from an environment variable that might not be set). `create_engine()` wants a `str`. The plan's original code passed `config.DATABASE_URL` straight through, which fails `mypy` (a CI-blocking check). The fix actually committed adds `assert config.DATABASE_URL is not None` immediately before `create_engine(...)`: at runtime this only ever fails if `DATABASE_URL` is genuinely unset (which doesn't happen in normal dev/CI, since `.env`/Docker Compose always set it), and it gives mypy the narrowing it needs to treat the value as `str` from that line on.

## Why this way

Putting the logger behind its own small class (`LLMCallLogger`, constructed with a `session_factory` callable) rather than having `AnthropicClient` import `SessionLocal` and write rows directly keeps the LLM-calling code decoupled from *how* persistence works — `AnthropicClient` only knows "I have an optional object with a `.log(...)` method," matching the same dependency-injection pattern Task 1 used for the SDK client itself.

## Where to look

- `packages/core/src/skiljo_core/db/session.py` — `engine`/`SessionLocal`, plus the `assert` deviation noted above.
- `packages/core/src/skiljo_core/llm/logging.py` — `LLMCallLogger.log()`.
- `packages/core/src/skiljo_core/llm/anthropic_client.py` — where logging is called inside the retry loop, before validation.
- `packages/core/tests/test_anthropic_client.py::test_logs_every_attempt_to_llm_calls_table` and `::test_logs_one_row_per_attempt_on_retry` — both run against the real local Postgres, not a mocked DB layer.
