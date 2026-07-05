# Week 3 Task 1 — LLM Response Cache (A1)

## What was built

A Postgres-backed LLM response cache keyed on `sha256(provider|model|prompt_version|prompt_text)`. Temperature-0 calls check the cache before hitting the Anthropic API; hits are logged with `cached=True` to the `llm_calls` table. Cache misses that succeed are written to the `llm_cache` table for future reuse.

**Files changed:**
- `packages/core/src/skiljo_core/llm/cache.py` — new `LLMCacheStore` class
- `packages/core/src/skiljo_core/llm/anthropic_client.py` — cache-aware `generate_structured`
- `packages/core/src/skiljo_core/llm/logging.py` — `cached: bool = False` kwarg on `log()`
- `packages/core/src/skiljo_core/db/models.py` — `cached` column on `LLMCall`, new `LLMCache` model
- `packages/api/src/skiljo_api/dependencies.py` — `LLMCacheStore` wired into `AnthropicClient`
- `packages/core/alembic/versions/df49c1c3cda5_llm_cache.py` — migration for new table and column
- `packages/core/tests/test_anthropic_client.py` — cache-hit test

## Why

Eval iteration over 60+ labeled examples without a cache costs ~$5–10 per run. With the cache, re-runs of unchanged prompts are free — the prompt, model, and version are the key, so changing a prompt invalidates the cache only for that prompt.

## Non-obvious concepts

**`session.merge()` for upserts.** `LLMCacheStore.set()` uses `session.merge(row)` rather than `session.add(row)`. SQLAlchemy's `merge()` issues a SELECT then INSERT-or-UPDATE based on whether the primary key already exists — this is safe because cache entries are idempotent: writing the same key twice with the same text is harmless, and writing with a different text (practically impossible given the sha256 key) should replace. `add()` would raise an `IntegrityError` on duplicate primary key.

**`attempts=0` sentinel.** `StructuredResponse` has an `attempts` field that normally counts API call attempts (1–3). A cache hit sets `attempts=0`, giving callers a reliable signal that no API round-trip occurred. Callers that don't care about this can ignore the field.

**`cached=True` in `llm_calls`.** Even cache hits write a row to `llm_calls` (with `latency_ms=0`). This preserves the invariant that every `generate_structured` call is logged — the `cached` column distinguishes real API calls from replays. The aggregate token cost dashboard stays accurate because cached rows carry 0 tokens.

**Only temperature-0 calls are cached.** The cache guard checks `temperature == 0.0` before attempting a lookup. Non-deterministic calls (temperature > 0) are never cached because the same prompt can legitimately produce different valid outputs, and caching one would mask that variance.

## Where to look

- `skiljo_core/llm/cache.py` — `LLMCacheStore.get/set/compute_key`
- `skiljo_core/llm/anthropic_client.py` — the opening block of `generate_structured` (cache check + cache-miss store-on-success)
- `packages/core/alembic/versions/df49c1c3cda5_llm_cache.py` — the Alembic migration for `llm_cache` table and `llm_calls.cached` column
- `packages/core/tests/test_anthropic_client.py` — `test_cache_hit_skips_api_call_and_logs_cached_true`
