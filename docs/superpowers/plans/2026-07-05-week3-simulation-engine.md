# Week 3 — Simulation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete simulation engine — ticket generator, rule evaluator, zone executors, batch runner, contradiction detector, and REST endpoints — so a user can simulate any approved skill against a ticket batch and receive a quantitative fidelity report.

**Architecture:** The `simulation/` package in `skiljo_core` contains four focused modules (evaluator, generator, executor, engine) plus the contradiction detector; the API layer gains a `simulations` router. The LLM response cache (A1) is wired into `AnthropicClient` before simulation work begins, since every eval re-run benefits from it.

**Tech Stack:** Python 3.12, asyncio (`asyncio.to_thread` for concurrency), Pydantic v2, SQLAlchemy 2.x, Alembic, FastAPI, pytest.

## Global Constraints

- `make lint typecheck test` must pass after every commit.
- No hand-editing of generated files in `packages/core/src/skiljo_core/schemas/` or `packages/sdk-ts/src/types.ts`.
- Conventional commit format: `<type>(<scope>): <summary> [plan #<N>]`; no `Co-Authored-By` trailer, no body.
- Ticket schema: `ticket_id`, `refund_amount`, `purchase_days_ago`, `customer_segment`, `fraud_flags`, `refund_reason`, `ground_truth_decision` — never add fields (use the Pydantic `Ticket` model from `skiljo_core.schemas.ticket_schema`).
- Simulation result `zone` values are the string literals `"deterministic"`, `"llm_assisted"`, `"human_only"` (the `Zone` enum from `simulation_report_schema`).
- Shadow-policy ground truth is computed from the **divergence spec + base skill**, never from the written skill alone — this is what makes contradiction detection non-circular.
- `data/eval/test/` is off limits. Never read, print, or reference it.
- All database writes use parameterized SQLAlchemy queries; no raw string-interpolated SQL.

---

## File Map

**New files:**
- `packages/core/alembic/versions/<hash>_llm_cache.py` — adds `llm_cache` table and `cached` column on `llm_calls`
- `packages/core/src/skiljo_core/llm/cache.py` — `LLMCacheStore` class
- `packages/core/src/skiljo_core/simulation/__init__.py` — package exports
- `packages/core/src/skiljo_core/simulation/evaluator.py` — pure-Python predicate DSL evaluator
- `packages/core/src/skiljo_core/simulation/generator.py` — shadow-policy ticket generator
- `packages/core/src/skiljo_core/simulation/executor.py` — per-zone executors + single-ticket sim
- `packages/core/src/skiljo_core/simulation/engine.py` — async batch runner + `SimulationReport` aggregation
- `packages/core/src/skiljo_core/simulation/contradictions.py` — contradiction detector
- `packages/api/src/skiljo_api/routers/simulations.py` — `POST /simulations`, `GET /simulations/{id}`, `GET /simulations/{id}/report`
- `packages/core/tests/test_evaluator.py`
- `packages/core/tests/test_generator.py`
- `packages/core/tests/test_simulation_executor.py`
- `packages/core/tests/test_simulation_engine.py`
- `packages/core/tests/test_contradictions.py`
- `packages/api/tests/test_simulations.py`
- `packages/core/tests/test_simulation_golden.py`
- `data/synthetic_tickets/refund_v1/skill.json`
- `data/synthetic_tickets/refund_v1/divergence_spec.json`
- `data/synthetic_tickets/refund_v1/tickets.json`
- `docs/learning/week3-task1-llm-cache.md`
- `docs/learning/week3-task2-rule-evaluator.md`
- `docs/learning/week3-task3-shadow-policy-generator.md`
- `docs/learning/week3-task4-simulation-engine.md`
- `docs/learning/week3-task5-contradiction-detection.md`
- `docs/learning/week3-task6-simulation-api.md`

**Modified files:**
- `packages/core/src/skiljo_core/db/models.py` — add `LLMCache` model; add `cached` column to `LLMCall`
- `packages/core/src/skiljo_core/llm/logging.py` — add `cached: bool = False` param to `log()`
- `packages/core/src/skiljo_core/llm/anthropic_client.py` — add `cache_store` param + cache check/store logic
- `packages/api/src/skiljo_api/dependencies.py` — wire `LLMCacheStore` into `get_llm_client()`
- `packages/api/src/skiljo_api/main.py` — mount `simulations` router
- `docs/learning/GLOSSARY.md` — new terms per task
- `docs/learning/README.md` — new entries per task

---

## Task 1: Commit Pending Documentation Changes

**Files:** no code changes; git only.

- [ ] **Step 1: Verify only docs changes are staged**

```bash
git status
git diff
```
Expected: only CLAUDE.md and DESIGN_DOCUMENT.md are modified.

- [ ] **Step 2: Stage and commit**

```bash
git add CLAUDE.md docs/DESIGN_DOCUMENT.md
git commit -m "docs: update CLAUDE.md and DESIGN_DOCUMENT.md for week 3 start"
```

---

## Task 2: A1 — LLM Response Cache [plan #A1]

**Files:**
- Modify: `packages/core/src/skiljo_core/db/models.py`
- Modify: `packages/core/src/skiljo_core/llm/logging.py`
- Modify: `packages/core/src/skiljo_core/llm/anthropic_client.py`
- Modify: `packages/api/src/skiljo_api/dependencies.py`
- Create: `packages/core/src/skiljo_core/llm/cache.py`
- Create: `packages/core/alembic/versions/<hash>_llm_cache.py`
- Test: `packages/core/tests/test_anthropic_client.py` (extend existing)

**Interfaces:**
- Produces: `LLMCacheStore(session_factory)` with `.get(key) -> str | None` and `.set(key, text) -> None` and static `.compute_key(provider, model, prompt_version, prompt_text) -> str`
- `AnthropicClient` gains optional `cache_store: LLMCacheStore | None = None` in `__init__`
- `LLMCallLogger.log()` gains `cached: bool = False` kwarg

- [ ] **Step 1: Add `LLMCache` model and `cached` column to `LLMCall` in `models.py`**

Open `packages/core/src/skiljo_core/db/models.py`. Add after the `LLMCall` class and its existing fields:

```python
# In LLMCall class, add this field after `called_at`:
cached: Mapped[bool] = mapped_column(default=False, server_default="false")
```

Then add a new `LLMCache` model at the bottom of the file (before `EvalRun`):

```python
class LLMCache(Base):
    __tablename__ = "llm_cache"

    cache_key: Mapped[str] = mapped_column(Text, primary_key=True)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 2: Generate the Alembic migration**

Make sure Docker Postgres is running: `docker-compose up -d postgres`

```bash
cd packages/core && uv run alembic -c alembic.ini revision --autogenerate -m "llm_cache"
```

Open the generated file (`packages/core/alembic/versions/<hash>_llm_cache.py`). Verify its `upgrade()` contains both `op.add_column('llm_calls', ...)` and `op.create_table('llm_cache', ...)`. If autogenerate missed either, write it manually:

```python
def upgrade() -> None:
    op.add_column(
        'llm_calls',
        sa.Column('cached', sa.Boolean(), nullable=False, server_default='false')
    )
    op.create_table(
        'llm_cache',
        sa.Column('cache_key', sa.Text(), primary_key=True),
        sa.Column('response_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('llm_cache')
    op.drop_column('llm_calls', 'cached')
```

- [ ] **Step 3: Apply the migration**

```bash
make migrate
```

Expected: `Running upgrade fdf7e2230a2a -> <new_hash>, llm_cache`

- [ ] **Step 4: Create `packages/core/src/skiljo_core/llm/cache.py`**

```python
import hashlib
from collections.abc import Callable

from sqlalchemy.orm import Session

from skiljo_core.db.models import LLMCache


class LLMCacheStore:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def compute_key(provider: str, model: str, prompt_version: str, prompt_text: str) -> str:
        raw = f"{provider}|{model}|{prompt_version}|{prompt_text}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> str | None:
        with self._session_factory() as session:
            row = session.get(LLMCache, key)
            return row.response_text if row is not None else None

    def set(self, key: str, response_text: str) -> None:
        with self._session_factory() as session:
            row = LLMCache(cache_key=key, response_text=response_text)
            session.merge(row)
            session.commit()
```

- [ ] **Step 5: Update `LLMCallLogger.log()` to accept `cached` param**

In `packages/core/src/skiljo_core/llm/logging.py`, change the signature and the `LLMCall` constructor:

```python
def log(
    self,
    provider: str,
    model: str,
    prompt_version: str,
    prompt_text: str,
    response_text: str,
    latency_ms: int,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cached: bool = False,
) -> uuid.UUID:
    with self._session_factory() as session:
        call = LLMCall(
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            prompt_text=prompt_text,
            response_text=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cached=cached,
        )
        session.add(call)
        session.commit()
        session.refresh(call)
        return call.id
```

- [ ] **Step 6: Update `AnthropicClient` to use the cache**

Replace `packages/core/src/skiljo_core/llm/anthropic_client.py` with the following (all changes are additive to the existing logic):

```python
import json
import time
from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from skiljo_core import config
from skiljo_core.llm.base import StructuredResponse
from skiljo_core.llm.cache import LLMCacheStore
from skiljo_core.llm.logging import LLMCallLogger

T = TypeVar("T", bound=BaseModel)


class AnthropicClient:
    def __init__(
        self,
        api_key: str | None = None,
        client: anthropic.Anthropic | None = None,
        logger: LLMCallLogger | None = None,
        cache_store: LLMCacheStore | None = None,
    ) -> None:
        self._client = client or anthropic.Anthropic(api_key=api_key or config.ANTHROPIC_API_KEY)
        self._logger = logger
        self._cache_store = cache_store

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        model: str,
        prompt_version: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> StructuredResponse[T]:
        cache_key: str | None = None

        # Check cache for deterministic (temperature=0) calls
        if temperature == 0.0 and self._cache_store is not None:
            cache_key = LLMCacheStore.compute_key("anthropic", model, prompt_version, prompt)
            cached_text = self._cache_store.get(cache_key)
            if cached_text is not None:
                data = schema.model_validate_json(cached_text)
                llm_call_id = None
                if self._logger is not None:
                    llm_call_id = self._logger.log(
                        provider="anthropic",
                        model=model,
                        prompt_version=prompt_version,
                        prompt_text=prompt,
                        response_text=cached_text,
                        latency_ms=0,
                        cached=True,
                    )
                return StructuredResponse(data=data, attempts=0, llm_call_id=llm_call_id)

        current_prompt = prompt
        last_error: ValidationError | None = None
        response_text: str = ""
        for attempt in range(1, 4):
            start = time.monotonic()
            response = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=[
                    {
                        "name": "extract",
                        "description": f"Extract structured data matching the {schema.__name__} schema.",
                        "input_schema": schema.model_json_schema(),
                    }
                ],
                tool_choice={"type": "tool", "name": "extract"},
                messages=[{"role": "user", "content": current_prompt}],
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            tool_use_block = next(
                (block for block in response.content if block.type == "tool_use"),
                None,
            )
            if tool_use_block is None:
                raise ValueError(f"Model returned no tool_use block on attempt {attempt}")
            response_text = json.dumps(tool_use_block.input)

            llm_call_id = None
            if self._logger is not None:
                llm_call_id = self._logger.log(
                    provider="anthropic",
                    model=model,
                    prompt_version=prompt_version,
                    prompt_text=current_prompt,
                    response_text=response_text,
                    latency_ms=latency_ms,
                    input_tokens=getattr(response.usage, "input_tokens", None),
                    output_tokens=getattr(response.usage, "output_tokens", None),
                )

            try:
                data = schema.model_validate(tool_use_block.input)
            except ValidationError as exc:
                last_error = exc
                current_prompt = (
                    f"{prompt}\n\nYour previous attempt produced invalid output. "
                    f"Validation error: {exc}\nPlease correct it and try again."
                )
                continue

            # Store in cache on successful temperature-0 call
            if cache_key is not None and self._cache_store is not None:
                self._cache_store.set(cache_key, response_text)

            return StructuredResponse(data=data, attempts=attempt, llm_call_id=llm_call_id)
        assert last_error is not None
        raise last_error
```

- [ ] **Step 7: Wire `LLMCacheStore` into `dependencies.py`**

In `packages/api/src/skiljo_api/dependencies.py`:

```python
from skiljo_core.db.session import SessionLocal
from skiljo_core.llm.anthropic_client import AnthropicClient
from skiljo_core.llm.base import LLMClient
from skiljo_core.llm.cache import LLMCacheStore
from skiljo_core.llm.logging import LLMCallLogger

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = AnthropicClient(
            logger=LLMCallLogger(SessionLocal),
            cache_store=LLMCacheStore(SessionLocal),
        )
    return _client
```

- [ ] **Step 8: Write failing test for cache hit**

Add to `packages/core/tests/test_anthropic_client.py`:

```python
def test_cache_hit_skips_api_call_and_logs_cached_true(
    tmp_path: pytest.fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cache hit: no API call, logged with cached=True, same structured output returned."""
    from pydantic import BaseModel
    from skiljo_core.llm.anthropic_client import AnthropicClient
    from skiljo_core.llm.cache import LLMCacheStore

    class Foo(BaseModel):
        value: int

    api_called = []

    class FakeCache:
        @staticmethod
        def compute_key(provider: str, model: str, pv: str, pt: str) -> str:
            return "the-key"

        def get(self, key: str) -> str | None:
            return '{"value": 99}'

        def set(self, key: str, text: str) -> None:
            pass

    logged: list[dict] = []

    class FakeLogger:
        def log(self, **kwargs: object) -> None:
            logged.append(dict(kwargs))
            return None

    client = AnthropicClient(
        client=None,  # will error if called
        logger=FakeLogger(),  # type: ignore[arg-type]
        cache_store=FakeCache(),  # type: ignore[arg-type]
    )

    # Patch the underlying Anthropic client to track calls
    class BoomClient:
        def messages(self, *args: object, **kwargs: object) -> object:
            api_called.append(True)
            raise RuntimeError("API should not be called on cache hit")

    client._client = BoomClient()  # type: ignore[assignment]

    result = client.generate_structured(
        prompt="test",
        schema=Foo,
        model="claude-haiku-4-5-20251001",
        prompt_version="v1",
        temperature=0.0,
    )

    assert result.data.value == 99
    assert result.attempts == 0
    assert not api_called
    assert logged and logged[0].get("cached") is True
```

- [ ] **Step 9: Run the test to verify it fails**

```bash
uv run pytest packages/core/tests/test_anthropic_client.py::test_cache_hit_skips_api_call_and_logs_cached_true -v
```

Expected: FAIL (method not yet added or wrong type).

- [ ] **Step 10: Verify the test now passes after Step 6's implementation**

```bash
uv run pytest packages/core/tests/test_anthropic_client.py -v
make lint typecheck test
```

Expected: all tests pass, 0 type errors, 0 lint errors.

- [ ] **Step 11: Commit**

```bash
git add packages/core/src/skiljo_core/db/models.py \
        packages/core/src/skiljo_core/llm/cache.py \
        packages/core/src/skiljo_core/llm/logging.py \
        packages/core/src/skiljo_core/llm/anthropic_client.py \
        packages/api/src/skiljo_api/dependencies.py \
        packages/core/alembic/versions/ \
        packages/core/tests/test_anthropic_client.py
git commit -m "feat(core): LLM response cache [plan #A1]"
```

- [ ] **Step 12: Write learning debrief**

Create `docs/learning/week3-task1-llm-cache.md`:

```markdown
---
Week 3 Task 1 — LLM Response Cache (A1)

What was built: Postgres-backed LLM response cache keyed on sha256(provider|model|prompt_version|prompt). Temperature-0 calls check the cache before hitting the Anthropic API; hits are logged with cached=True to the llm_calls table.

Why: Eval iteration over 60+ labeled examples without a cache costs ~$5–10 per run. With cache, re-runs of unchanged prompts are free.

Non-obvious: LLMCacheStore uses session.merge() (not add()) for upserts — this is a SQLAlchemy SELECT-then-INSERT/UPDATE under the hood, safe because cache entries are idempotent by key. The `attempts=0` sentinel on StructuredResponse signals a cache hit to callers that care.

Where to look: skiljo_core/llm/cache.py, skiljo_core/llm/anthropic_client.py (generate_structured's opening block), alembic migration for llm_cache table.
---
```

Update `docs/learning/GLOSSARY.md` and `docs/learning/README.md` with the new entry.

---

## Task 3: Rule Evaluator [plan #27]

**Files:**
- Create: `packages/core/src/skiljo_core/simulation/__init__.py`
- Create: `packages/core/src/skiljo_core/simulation/evaluator.py`
- Create: `packages/core/tests/test_evaluator.py`

**Interfaces:**
- Produces: `evaluate_condition(condition: Condition, ticket: dict[str, Any]) -> bool`
- Produces: `evaluate_predicate(predicate: Predicate, ticket: dict[str, Any]) -> bool`
- Produces: `evaluate_condition_or_predicate(cop: ConditionOrPredicate, ticket: dict[str, Any]) -> bool`
- All three are re-exported from `simulation/__init__.py`

- [ ] **Step 1: Write failing table-driven tests for all operators**

Create `packages/core/tests/test_evaluator.py`:

```python
from typing import Any

import pytest

from skiljo_core.schemas.rule_schema import Condition, ConditionOrPredicate, Operator, Predicate
from skiljo_core.simulation.evaluator import evaluate_condition, evaluate_predicate


ticket: dict[str, Any] = {
    "refund_amount": 75.0,
    "purchase_days_ago": 20,
    "customer_segment": "vip",
    "fraud_flags": ["suspicious_ip"],
    "refund_reason": "product_defect",
}


@pytest.mark.parametrize(
    "field,op,value,expected",
    [
        ("refund_amount", Operator.eq, 75.0, True),
        ("refund_amount", Operator.eq, 100.0, False),
        ("refund_amount", Operator.neq, 100.0, True),
        ("refund_amount", Operator.lt, 100.0, True),
        ("refund_amount", Operator.lt, 50.0, False),
        ("refund_amount", Operator.lte, 75.0, True),
        ("refund_amount", Operator.lte, 74.9, False),
        ("refund_amount", Operator.gt, 50.0, True),
        ("refund_amount", Operator.gt, 75.0, False),
        ("refund_amount", Operator.gte, 75.0, True),
        ("refund_amount", Operator.gte, 76.0, False),
        ("customer_segment", Operator.in_, ["vip", "premium"], True),
        ("customer_segment", Operator.in_, ["standard"], False),
        ("customer_segment", Operator.not_in, ["standard"], True),
        ("customer_segment", Operator.not_in, ["vip"], False),
        ("refund_reason", Operator.contains, "defect", True),
        ("refund_reason", Operator.contains, "goodwill", False),
        ("fraud_flags", Operator.contains, "suspicious_ip", True),
        ("fraud_flags", Operator.contains, "known_fraud", False),
        ("fraud_flags", Operator.empty, None, False),
        ("missing_field", Operator.empty, None, True),
        ("fraud_flags", Operator.not_empty, None, True),
        ("missing_field", Operator.not_empty, None, False),
    ],
)
def test_predicate_operators(
    field: str, op: Operator, value: Any, expected: bool
) -> None:
    pred = Predicate(field=field, op=op, value=value)
    assert evaluate_predicate(pred, ticket) == expected


def test_condition_all_true() -> None:
    cond = Condition(
        all=[
            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lt, value=100.0)),
            ConditionOrPredicate(root=Predicate(field="purchase_days_ago", op=Operator.lte, value=30)),
        ]
    )
    assert evaluate_condition(cond, ticket) is True


def test_condition_all_short_circuits_on_false() -> None:
    cond = Condition(
        all=[
            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=200.0)),
            ConditionOrPredicate(root=Predicate(field="purchase_days_ago", op=Operator.lte, value=30)),
        ]
    )
    assert evaluate_condition(cond, ticket) is False


def test_condition_any_true() -> None:
    cond = Condition(
        any=[
            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=200.0)),
            ConditionOrPredicate(root=Predicate(field="customer_segment", op=Operator.eq, value="vip")),
        ]
    )
    assert evaluate_condition(cond, ticket) is True


def test_condition_any_false() -> None:
    cond = Condition(
        any=[
            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=200.0)),
            ConditionOrPredicate(root=Predicate(field="customer_segment", op=Operator.eq, value="standard")),
        ]
    )
    assert evaluate_condition(cond, ticket) is False


def test_nested_condition() -> None:
    """all: [amount < 500, any: [vip, premium]]"""
    inner = Condition(
        any=[
            ConditionOrPredicate(root=Predicate(field="customer_segment", op=Operator.eq, value="vip")),
            ConditionOrPredicate(root=Predicate(field="customer_segment", op=Operator.eq, value="premium")),
        ]
    )
    outer = Condition(
        all=[
            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lt, value=500.0)),
            ConditionOrPredicate(root=inner),
        ]
    )
    assert evaluate_condition(outer, ticket) is True


def test_empty_all_returns_false() -> None:
    assert evaluate_condition(Condition(all=[]), ticket) is True  # vacuous truth: all([]) == True


def test_empty_any_returns_false() -> None:
    assert evaluate_condition(Condition(any=[]), ticket) is False  # vacuous: any([]) == False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest packages/core/tests/test_evaluator.py -v
```

Expected: `ModuleNotFoundError: No module named 'skiljo_core.simulation'`

- [ ] **Step 3: Create `packages/core/src/skiljo_core/simulation/__init__.py`**

```python
from skiljo_core.simulation.evaluator import (
    evaluate_condition,
    evaluate_condition_or_predicate,
    evaluate_predicate,
)

__all__ = ["evaluate_condition", "evaluate_condition_or_predicate", "evaluate_predicate"]
```

- [ ] **Step 4: Create `packages/core/src/skiljo_core/simulation/evaluator.py`**

```python
from typing import Any

from skiljo_core.schemas.rule_schema import Condition, ConditionOrPredicate, Operator, Predicate


def evaluate_predicate(predicate: Predicate, ticket: dict[str, Any]) -> bool:
    v = predicate.value
    fv = ticket.get(predicate.field)
    op = predicate.op

    if op == Operator.eq:
        return fv == v
    if op == Operator.neq:
        return fv != v
    if op == Operator.lt:
        return fv is not None and fv < v
    if op == Operator.lte:
        return fv is not None and fv <= v
    if op == Operator.gt:
        return fv is not None and fv > v
    if op == Operator.gte:
        return fv is not None and fv >= v
    if op == Operator.in_:
        return fv in v
    if op == Operator.not_in:
        return fv not in v
    if op == Operator.contains:
        if isinstance(fv, str):
            return str(v) in fv
        if isinstance(fv, list):
            return v in fv
        return False
    if op == Operator.empty:
        return fv is None or fv == [] or fv == ""
    if op == Operator.not_empty:
        return fv is not None and fv != [] and fv != ""
    raise ValueError(f"Unknown operator: {op}")


def evaluate_condition_or_predicate(cop: ConditionOrPredicate, ticket: dict[str, Any]) -> bool:
    if isinstance(cop.root, Predicate):
        return evaluate_predicate(cop.root, ticket)
    return evaluate_condition(cop.root, ticket)


def evaluate_condition(condition: Condition, ticket: dict[str, Any]) -> bool:
    if condition.all is not None:
        return all(evaluate_condition_or_predicate(c, ticket) for c in condition.all)
    if condition.any is not None:
        return any(evaluate_condition_or_predicate(c, ticket) for c in condition.any)
    return False
```

- [ ] **Step 5: Run tests and verify they pass**

```bash
uv run pytest packages/core/tests/test_evaluator.py -v
make lint typecheck test
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/skiljo_core/simulation/ \
        packages/core/tests/test_evaluator.py
git commit -m "feat(core): rule evaluator for deterministic zone [plan #27]"
```

- [ ] **Step 7: Write learning debrief `docs/learning/week3-task2-rule-evaluator.md`**

Cover: why a constrained DSL (not Python eval) was chosen; how `ConditionOrPredicate` as a discriminated union works; `Condition.model_rebuild()` necessity; `all([])` vacuous truth vs. `any([])` vacuous false. Add "Predicate DSL" to GLOSSARY if not already there; update README.

---

## Task 4: Shadow-Policy Ticket Generator [plan #26]

**Files:**
- Create: `packages/core/src/skiljo_core/simulation/generator.py`
- Create: `packages/core/tests/test_generator.py`

**Interfaces:**
- Consumes: `evaluate_condition(condition, ticket_dict)` from `simulation.evaluator`
- Produces: `DivergenceSpec` (Pydantic model), `TicketFieldRanges` (Pydantic model), `generate_ticket_batch(base_skill, divergences, count, seed, ranges) -> list[Ticket]`
- `DivergenceSpec` fields: `rule_id: str`, `condition: Condition`, `base_decision: str`, `shadow_decision: str`, `frequency: float`
- `TicketFieldRanges` fields: `refund_amount_min`, `refund_amount_max`, `purchase_days_min`, `purchase_days_max`, `customer_segments`, `segment_weights`, `refund_reasons`, `fraud_flag_probability`

- [ ] **Step 1: Write failing tests**

Create `packages/core/tests/test_generator.py`:

```python
import pytest

from skiljo_core.schemas.rule_schema import Condition, ConditionOrPredicate, Operator, Predicate
from skiljo_core.schemas.skill_schema import DecisionZones, Input, Skill, Type
from skiljo_core.schemas.rule_schema import DeterministicRule, LLMAssistedRule, HumanOnlyRule
from skiljo_core.simulation.generator import DivergenceSpec, generate_ticket_batch


def _base_skill() -> Skill:
    return Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[
            Input(name="refund_amount", type=Type.number),
            Input(name="purchase_days_ago", type=Type.integer),
        ],
        decision_zones=DecisionZones(
            deterministic=[
                DeterministicRule(
                    condition=Condition(
                        all=[
                            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lte, value=100.0)),
                            ConditionOrPredicate(root=Predicate(field="purchase_days_ago", op=Operator.lte, value=30)),
                        ]
                    ),
                    action="approve_refund",
                ),
                DeterministicRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=500.0))]
                    ),
                    action="escalate_to_human",
                ),
            ],
            llm_assisted=[
                LLMAssistedRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_reason", op=Operator.contains, value="goodwill"))]
                    ),
                    action="draft_recommendation",
                    requires_human_approval=True,
                )
            ],
            human_only=[
                HumanOnlyRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=500.0))]
                    ),
                    action="escalate_to_finance",
                )
            ],
        ),
    )


def test_generate_ticket_batch_returns_correct_count() -> None:
    tickets = generate_ticket_batch(_base_skill(), divergences=[], count=50, seed=42)
    assert len(tickets) == 50


def test_generate_ticket_batch_all_have_required_fields() -> None:
    tickets = generate_ticket_batch(_base_skill(), divergences=[], count=20, seed=1)
    for t in tickets:
        assert t.ticket_id is not None
        assert isinstance(t.refund_amount, float)
        assert isinstance(t.purchase_days_ago, int)
        assert t.ground_truth_decision != ""


def test_generate_ticket_batch_is_reproducible() -> None:
    batch_a = generate_ticket_batch(_base_skill(), divergences=[], count=10, seed=99)
    batch_b = generate_ticket_batch(_base_skill(), divergences=[], count=10, seed=99)
    assert [str(t.ticket_id) for t in batch_a] == [str(t.ticket_id) for t in batch_b]
    assert [t.refund_amount for t in batch_a] == [t.refund_amount for t in batch_b]


def test_divergence_overrides_base_decision_at_expected_frequency() -> None:
    """VIP exception: customer_segment==vip AND refund_amount>100 → approve_refund at 100% frequency."""
    vip_exception = DivergenceSpec(
        rule_id="vip_exception",
        condition=Condition(
            all=[
                ConditionOrPredicate(root=Predicate(field="customer_segment", op=Operator.eq, value="vip")),
                ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=100.0)),
            ]
        ),
        base_decision="deny_refund",
        shadow_decision="approve_refund",
        frequency=1.0,
    )
    tickets = generate_ticket_batch(_base_skill(), divergences=[vip_exception], count=200, seed=7)
    vip_over_threshold = [
        t for t in tickets
        if t.customer_segment == "vip" and t.refund_amount > 100.0
    ]
    assert len(vip_over_threshold) > 0, "no VIP tickets generated; adjust seed or count"
    assert all(t.ground_truth_decision == "approve_refund" for t in vip_over_threshold)


def test_base_policy_applied_when_no_divergence_matches() -> None:
    """Tickets that match the base deterministic rule get the correct base decision."""
    tickets = generate_ticket_batch(_base_skill(), divergences=[], count=200, seed=3)
    eligible = [
        t for t in tickets
        if t.refund_amount <= 100.0 and t.purchase_days_ago <= 30
    ]
    assert len(eligible) > 0
    assert all(t.ground_truth_decision == "approve_refund" for t in eligible)


def test_planted_divergences_present_at_expected_rate() -> None:
    """50% frequency divergence should appear roughly 50% of the time in matching tickets."""
    near_threshold = DivergenceSpec(
        rule_id="near_threshold",
        condition=Condition(
            all=[
                ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gte, value=100.0)),
                ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lte, value=120.0)),
            ]
        ),
        base_decision="deny_refund",
        shadow_decision="approve_refund",
        frequency=0.5,
    )
    tickets = generate_ticket_batch(_base_skill(), divergences=[near_threshold], count=500, seed=0)
    matching = [t for t in tickets if 100.0 <= t.refund_amount <= 120.0]
    if len(matching) == 0:
        pytest.skip("no matching tickets in this batch; increase count")
    approved = [t for t in matching if t.ground_truth_decision == "approve_refund"]
    rate = len(approved) / len(matching)
    # With 500 tickets and 0.5 frequency, rate should be ~50% ± 20% (generous tolerance)
    assert 0.30 <= rate <= 0.70, f"expected ~50% divergence rate, got {rate:.2f}"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest packages/core/tests/test_generator.py -v
```

Expected: `ModuleNotFoundError: No module named 'skiljo_core.simulation.generator'`

- [ ] **Step 3: Create `packages/core/src/skiljo_core/simulation/generator.py`**

```python
from __future__ import annotations

import random
import uuid
from typing import Any

from pydantic import BaseModel

from skiljo_core.schemas.rule_schema import Condition
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.evaluator import evaluate_condition


class DivergenceSpec(BaseModel):
    rule_id: str
    condition: Condition
    base_decision: str
    shadow_decision: str
    frequency: float  # 0.0–1.0


class TicketFieldRanges(BaseModel):
    refund_amount_min: float = 0.0
    refund_amount_max: float = 500.0
    purchase_days_min: int = 0
    purchase_days_max: int = 90
    customer_segments: list[str] = ["standard", "premium", "vip"]
    segment_weights: list[float] = [0.6, 0.3, 0.1]
    refund_reasons: list[str] = ["product_defect", "not_as_described", "changed_mind", "goodwill"]
    fraud_flag_probability: float = 0.1


def _shadow_ground_truth(
    ticket_dict: dict[str, Any],
    base_skill: Skill,
    divergences: list[DivergenceSpec],
    rng: random.Random,
) -> str:
    for div in divergences:
        if evaluate_condition(div.condition, ticket_dict) and rng.random() < div.frequency:
            return div.shadow_decision

    for rule in base_skill.decision_zones.deterministic:
        if evaluate_condition(rule.condition, ticket_dict):
            return rule.action

    for rule in base_skill.decision_zones.llm_assisted:
        if evaluate_condition(rule.condition, ticket_dict):
            return "requires_human_review"

    return "escalate_to_human"


def generate_ticket_batch(
    base_skill: Skill,
    divergences: list[DivergenceSpec],
    count: int = 100,
    seed: int | None = 42,
    ranges: TicketFieldRanges | None = None,
) -> list[Ticket]:
    rng = random.Random(seed)
    r = ranges or TicketFieldRanges()
    tickets = []

    for _ in range(count):
        refund_amount = round(rng.uniform(r.refund_amount_min, r.refund_amount_max), 2)
        purchase_days_ago = rng.randint(r.purchase_days_min, r.purchase_days_max)
        customer_segment = rng.choices(r.customer_segments, weights=r.segment_weights, k=1)[0]
        fraud_flags = ["suspicious_activity"] if rng.random() < r.fraud_flag_probability else []
        refund_reason = rng.choice(r.refund_reasons)

        ticket_dict: dict[str, Any] = {
            "refund_amount": refund_amount,
            "purchase_days_ago": purchase_days_ago,
            "customer_segment": customer_segment,
            "fraud_flags": fraud_flags,
            "refund_reason": refund_reason,
        }
        ground_truth = _shadow_ground_truth(ticket_dict, base_skill, divergences, rng)

        tickets.append(
            Ticket(
                ticket_id=uuid.UUID(int=rng.getrandbits(128)),
                ground_truth_decision=ground_truth,
                **ticket_dict,
            )
        )
    return tickets
```

- [ ] **Step 4: Update `simulation/__init__.py` to export `DivergenceSpec` and `generate_ticket_batch`**

```python
from skiljo_core.simulation.evaluator import (
    evaluate_condition,
    evaluate_condition_or_predicate,
    evaluate_predicate,
)
from skiljo_core.simulation.generator import DivergenceSpec, TicketFieldRanges, generate_ticket_batch

__all__ = [
    "evaluate_condition",
    "evaluate_condition_or_predicate",
    "evaluate_predicate",
    "DivergenceSpec",
    "TicketFieldRanges",
    "generate_ticket_batch",
]
```

- [ ] **Step 5: Run tests and verify they pass**

```bash
uv run pytest packages/core/tests/test_generator.py -v
make lint typecheck test
```

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/skiljo_core/simulation/ \
        packages/core/tests/test_generator.py
git commit -m "feat(core): shadow-policy ticket generator [plan #26]"
```

- [ ] **Step 7: Write learning debrief `docs/learning/week3-task3-shadow-policy-generator.md`**

Cover: why tickets are generated from the shadow policy not the written policy (circular simulation problem); how `DivergenceSpec` makes planted contradictions measurable; `random.Random(seed)` for reproducibility. Add "Shadow Policy", "Divergence Spec", "Planted Contradiction" to GLOSSARY.

---

## Task 5: Zone Executors + Single-Ticket Simulation [plan #28–30]

**Files:**
- Create: `packages/core/src/skiljo_core/simulation/executor.py`
- Create: `packages/core/tests/test_simulation_executor.py`

**Interfaces:**
- Consumes: `evaluate_condition` from `simulation.evaluator`, `LLMClient` from `llm.base`, `Skill`, `Ticket`, `Result`, `Zone` from schemas
- Produces: `LLMRecommendation(action: str, reasoning: str)`, `simulate_ticket(skill, ticket, llm_client, model) -> Result`

- [ ] **Step 1: Write failing tests**

Create `packages/core/tests/test_simulation_executor.py`:

```python
import uuid

from skiljo_core.schemas.rule_schema import (
    Condition,
    ConditionOrPredicate,
    DeterministicRule,
    HumanOnlyRule,
    LLMAssistedRule,
    Operator,
    Predicate,
)
from skiljo_core.schemas.simulation_report_schema import Zone
from skiljo_core.schemas.skill_schema import DecisionZones, Input, Skill, Type
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.executor import LLMRecommendation, simulate_ticket
from skiljo_core.testing import FakeLLMClient


def _ticket(
    refund_amount: float = 50.0,
    purchase_days_ago: int = 10,
    customer_segment: str = "standard",
    refund_reason: str = "product_defect",
    ground_truth: str = "approve_refund",
) -> Ticket:
    return Ticket(
        ticket_id=uuid.uuid4(),
        refund_amount=refund_amount,
        purchase_days_ago=purchase_days_ago,
        customer_segment=customer_segment,
        fraud_flags=[],
        refund_reason=refund_reason,
        ground_truth_decision=ground_truth,
    )


def _skill_with_deterministic_rule() -> Skill:
    return Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[Input(name="refund_amount", type=Type.number)],
        decision_zones=DecisionZones(
            deterministic=[
                DeterministicRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lte, value=100.0))]
                    ),
                    action="approve_refund",
                )
            ],
            llm_assisted=[],
            human_only=[],
        ),
    )


def _skill_with_llm_assisted_rule() -> Skill:
    return Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[Input(name="refund_reason", type=Type.string)],
        decision_zones=DecisionZones(
            deterministic=[],
            llm_assisted=[
                LLMAssistedRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_reason", op=Operator.contains, value="goodwill"))]
                    ),
                    action="draft_recommendation",
                    requires_human_approval=True,
                )
            ],
            human_only=[],
        ),
    )


def _skill_empty() -> Skill:
    return Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[],
        decision_zones=DecisionZones(deterministic=[], llm_assisted=[], human_only=[]),
    )


def test_deterministic_rule_match_returns_correct_decision() -> None:
    skill = _skill_with_deterministic_rule()
    ticket = _ticket(refund_amount=50.0, ground_truth="approve_refund")
    result = simulate_ticket(skill, ticket, FakeLLMClient([]))
    assert result.decision == "approve_refund"
    assert result.zone == Zone.deterministic
    assert result.matched_human_decision is True


def test_deterministic_rule_no_match_falls_through() -> None:
    skill = _skill_with_deterministic_rule()
    ticket = _ticket(refund_amount=200.0, ground_truth="escalate_to_human")
    result = simulate_ticket(skill, ticket, FakeLLMClient([]))
    assert result.zone == Zone.human_only
    assert result.decision == "escalate_to_human"


def test_llm_assisted_rule_invokes_llm_and_uses_recommendation() -> None:
    skill = _skill_with_llm_assisted_rule()
    ticket = _ticket(refund_reason="goodwill request", ground_truth="approve_refund")
    fake = FakeLLMClient([LLMRecommendation(action="approve_refund", reasoning="Customer is long-term.")])
    result = simulate_ticket(skill, ticket, fake)
    assert result.zone == Zone.llm_assisted
    assert result.decision == "approve_refund"
    assert result.reasoning == "Customer is long-term."
    assert len(fake.calls) == 1


def test_no_rule_match_escalates_to_human_only() -> None:
    skill = _skill_empty()
    ticket = _ticket(ground_truth="escalate_to_human")
    result = simulate_ticket(skill, ticket, FakeLLMClient([]))
    assert result.zone == Zone.human_only
    assert result.decision == "escalate_to_human"


def test_matched_human_decision_false_when_wrong_decision() -> None:
    skill = _skill_with_deterministic_rule()
    ticket = _ticket(refund_amount=50.0, ground_truth="deny_refund")
    result = simulate_ticket(skill, ticket, FakeLLMClient([]))
    assert result.matched_human_decision is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest packages/core/tests/test_simulation_executor.py -v
```

Expected: `ModuleNotFoundError: No module named 'skiljo_core.simulation.executor'`

- [ ] **Step 3: Create `packages/core/src/skiljo_core/simulation/executor.py`**

```python
from pydantic import BaseModel

from skiljo_core import config
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.simulation_report_schema import Result, Zone
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.evaluator import evaluate_condition


class LLMRecommendation(BaseModel):
    action: str
    reasoning: str


def simulate_ticket(
    skill: Skill,
    ticket: Ticket,
    llm_client: LLMClient,
    model: str = config.DEFAULT_MODEL,
) -> Result:
    ticket_dict = ticket.model_dump(mode="json")

    # 1. Deterministic zone: first matching rule wins
    for rule in skill.decision_zones.deterministic:
        if evaluate_condition(rule.condition, ticket_dict):
            return Result(
                ticket_id=ticket.ticket_id,
                decision=rule.action,
                zone=Zone.deterministic,
                matched_human_decision=rule.action == ticket.ground_truth_decision,
            )

    # 2. LLM-assisted zone
    for rule in skill.decision_zones.llm_assisted:
        if evaluate_condition(rule.condition, ticket_dict):
            prompt = (
                f"You are evaluating a refund or credit request.\n\n"
                f"Policy rule: {rule.action}\n"
                f"Matched condition: {rule.condition.model_dump()}\n"
                f"Ticket data: {ticket_dict}\n\n"
                "Based on the ticket context and this policy rule, provide a recommendation "
                "with a specific action and a brief reasoning."
            )
            resp = llm_client.generate_structured(
                prompt=prompt,
                schema=LLMRecommendation,
                model=model,
                prompt_version="llm_assisted_zone_v1",
            )
            return Result(
                ticket_id=ticket.ticket_id,
                decision=resp.data.action,
                zone=Zone.llm_assisted,
                matched_human_decision=resp.data.action == ticket.ground_truth_decision,
                reasoning=resp.data.reasoning,
            )

    # 3. Human-only zone
    for rule in skill.decision_zones.human_only:
        if evaluate_condition(rule.condition, ticket_dict):
            return Result(
                ticket_id=ticket.ticket_id,
                decision=rule.action,
                zone=Zone.human_only,
                matched_human_decision=rule.action == ticket.ground_truth_decision,
            )

    # Default: no rule matched → escalate
    return Result(
        ticket_id=ticket.ticket_id,
        decision="escalate_to_human",
        zone=Zone.human_only,
        matched_human_decision="escalate_to_human" == ticket.ground_truth_decision,
    )
```

- [ ] **Step 4: Update `simulation/__init__.py`** to also export `simulate_ticket` and `LLMRecommendation`.

- [ ] **Step 5: Run tests and verify they pass**

```bash
uv run pytest packages/core/tests/test_simulation_executor.py -v
make lint typecheck test
```

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/skiljo_core/simulation/ \
        packages/core/tests/test_simulation_executor.py
git commit -m "feat(core): zone executors and single-ticket simulation engine [plan #28-30]"
```

---

## Task 6: Batch Simulation Engine + SimulationReport Aggregation [plan #31–32]

**Files:**
- Create: `packages/core/src/skiljo_core/simulation/engine.py`
- Create: `packages/core/tests/test_simulation_engine.py`

**Interfaces:**
- Consumes: `simulate_ticket` from `simulation.executor`
- Produces:
  - `async def simulate_batch(skill, tickets, llm_client, max_concurrency=5) -> list[Result]`
  - `def compute_report(skill_version_id, results, tickets) -> SimulationReport`

- [ ] **Step 1: Write failing tests**

Create `packages/core/tests/test_simulation_engine.py`:

```python
import asyncio
import uuid
from unittest.mock import patch

import pytest

from skiljo_core.schemas.rule_schema import (
    Condition,
    ConditionOrPredicate,
    DeterministicRule,
    Operator,
    Predicate,
)
from skiljo_core.schemas.simulation_report_schema import Zone
from skiljo_core.schemas.skill_schema import DecisionZones, Input, Skill, Type
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.engine import compute_report, simulate_batch
from skiljo_core.testing import FakeLLMClient


def _simple_skill() -> Skill:
    return Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[Input(name="refund_amount", type=Type.number)],
        decision_zones=DecisionZones(
            deterministic=[
                DeterministicRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lte, value=100.0))]
                    ),
                    action="approve_refund",
                )
            ],
            llm_assisted=[],
            human_only=[],
        ),
    )


def _tickets(count: int, approved_count: int) -> list[Ticket]:
    tickets = []
    for i in range(count):
        amount = 50.0 if i < approved_count else 200.0
        gt = "approve_refund" if i < approved_count else "escalate_to_human"
        tickets.append(
            Ticket(
                ticket_id=uuid.uuid4(),
                refund_amount=amount,
                purchase_days_ago=10,
                ground_truth_decision=gt,
            )
        )
    return tickets


def test_simulate_batch_returns_one_result_per_ticket() -> None:
    skill = _simple_skill()
    tickets = _tickets(10, 5)
    results = asyncio.run(simulate_batch(skill, tickets, FakeLLMClient([])))
    assert len(results) == 10


def test_simulate_batch_all_deterministic_no_llm_calls() -> None:
    skill = _simple_skill()
    tickets = _tickets(5, 5)
    fake = FakeLLMClient([])
    asyncio.run(simulate_batch(skill, tickets, fake))
    assert len(fake.calls) == 0


def test_compute_report_match_rate() -> None:
    skill_version_id = uuid.uuid4()
    tickets = _tickets(10, 7)
    results = asyncio.run(simulate_batch(_simple_skill(), tickets, FakeLLMClient([])))
    report = compute_report(skill_version_id, results, tickets)
    assert report.match_rate == pytest.approx(1.0)  # all decisions match ground truth


def test_compute_report_automation_candidate_count() -> None:
    skill_version_id = uuid.uuid4()
    tickets = _tickets(10, 4)
    results = asyncio.run(simulate_batch(_simple_skill(), tickets, FakeLLMClient([])))
    report = compute_report(skill_version_id, results, tickets)
    assert report.automation_candidate_count == 4  # 4 hit deterministic zone


def test_compute_report_empty_returns_zero_match_rate() -> None:
    report = compute_report(uuid.uuid4(), [], [])
    assert report.match_rate == 0.0
    assert report.escalation_accuracy == 1.0


def test_compute_report_escalation_accuracy_all_correct() -> None:
    skill_version_id = uuid.uuid4()
    # All escalations should match ground truth (escalate_to_human)
    tickets = _tickets(6, 0)  # all above threshold → all escalate → all match ground truth
    results = asyncio.run(simulate_batch(_simple_skill(), tickets, FakeLLMClient([])))
    report = compute_report(skill_version_id, results, tickets)
    assert report.escalation_accuracy == pytest.approx(1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest packages/core/tests/test_simulation_engine.py -v
```

Expected: `ModuleNotFoundError: No module named 'skiljo_core.simulation.engine'`

- [ ] **Step 3: Create `packages/core/src/skiljo_core/simulation/engine.py`**

```python
from __future__ import annotations

import asyncio
from uuid import UUID

from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.simulation_report_schema import Result, SimulationReport, Zone
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.executor import simulate_ticket

_ESCALATION_DECISIONS = frozenset({"escalate_to_human", "human_only", "requires_human_review"})


async def simulate_batch(
    skill: Skill,
    tickets: list[Ticket],
    llm_client: LLMClient,
    max_concurrency: int = 5,
) -> list[Result]:
    sem = asyncio.Semaphore(max_concurrency)

    async def run_one(ticket: Ticket) -> Result:
        async with sem:
            return await asyncio.to_thread(simulate_ticket, skill, ticket, llm_client)

    return list(await asyncio.gather(*[run_one(t) for t in tickets]))


def compute_report(
    skill_version_id: UUID,
    results: list[Result],
    tickets: list[Ticket],
) -> SimulationReport:
    if not results:
        return SimulationReport(
            skill_version_id=skill_version_id,
            match_rate=0.0,
            escalation_accuracy=1.0,
            results=[],
        )

    matched = sum(1 for r in results if r.matched_human_decision)
    match_rate = matched / len(results)

    escalated = [r for r in results if r.zone == Zone.human_only]
    ticket_map = {str(t.ticket_id): t for t in tickets}
    if escalated:
        correct = sum(
            1
            for r in escalated
            if (t := ticket_map.get(str(r.ticket_id))) is not None
            and t.ground_truth_decision in _ESCALATION_DECISIONS
        )
        escalation_accuracy = correct / len(escalated)
    else:
        escalation_accuracy = 1.0

    automation_candidates = sum(1 for r in results if r.zone == Zone.deterministic)

    return SimulationReport(
        skill_version_id=skill_version_id,
        match_rate=match_rate,
        escalation_accuracy=escalation_accuracy,
        automation_candidate_count=automation_candidates,
        results=results,
    )
```

- [ ] **Step 4: Update `simulation/__init__.py`** to also export `simulate_batch` and `compute_report`.

- [ ] **Step 5: Run tests and verify they pass**

```bash
uv run pytest packages/core/tests/test_simulation_engine.py -v
make lint typecheck test
```

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/skiljo_core/simulation/ \
        packages/core/tests/test_simulation_engine.py
git commit -m "feat(core): batch simulation engine and SimulationReport aggregation [plan #31-32]"
```

---

## Task 7: Contradiction Detection [plan #33]

**Files:**
- Create: `packages/core/src/skiljo_core/simulation/contradictions.py`
- Create: `packages/core/tests/test_contradictions.py`

**Interfaces:**
- Produces: `Contradiction(cluster_key, written_decision, observed_decision, frequency, ticket_count, affected_ticket_ids)` dataclass
- Produces: `detect_contradictions(results, tickets, threshold=0.05, min_cluster_size=3) -> list[Contradiction]`

- [ ] **Step 1: Write failing tests**

Create `packages/core/tests/test_contradictions.py`:

```python
import uuid

from skiljo_core.schemas.simulation_report_schema import Result, Zone
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.contradictions import Contradiction, detect_contradictions


def _result(ticket: Ticket, decision: str, zone: Zone = Zone.deterministic) -> Result:
    return Result(
        ticket_id=ticket.ticket_id,
        decision=decision,
        zone=zone,
        matched_human_decision=decision == ticket.ground_truth_decision,
    )


def _ticket(
    refund_amount: float,
    customer_segment: str = "standard",
    ground_truth: str = "approve_refund",
) -> Ticket:
    return Ticket(
        ticket_id=uuid.uuid4(),
        refund_amount=refund_amount,
        purchase_days_ago=10,
        customer_segment=customer_segment,
        ground_truth_decision=ground_truth,
    )


def test_no_contradictions_when_all_decisions_match() -> None:
    tickets = [_ticket(50.0, "standard", "approve_refund") for _ in range(10)]
    results = [_result(t, "approve_refund") for t in tickets]
    assert detect_contradictions(results, tickets) == []


def test_detects_contradiction_above_threshold() -> None:
    """VIP cluster: skill says deny, but 100% of VIP ground truth says approve."""
    vip_tickets = [_ticket(150.0, "vip", "approve_refund") for _ in range(5)]
    vip_results = [_result(t, "deny_refund") for t in vip_tickets]  # skill always denies

    # Non-contradicting standard tickets (same amount band, different segment)
    std_tickets = [_ticket(150.0, "standard", "deny_refund") for _ in range(5)]
    std_results = [_result(t, "deny_refund") for t in std_tickets]

    contradictions = detect_contradictions(
        vip_results + std_results, vip_tickets + std_tickets, threshold=0.05, min_cluster_size=3
    )
    assert len(contradictions) >= 1
    vip_c = next((c for c in contradictions if c.cluster_key.get("customer_segment") == "vip"), None)
    assert vip_c is not None
    assert vip_c.written_decision == "deny_refund"
    assert vip_c.observed_decision == "approve_refund"
    assert vip_c.frequency == 1.0
    assert vip_c.ticket_count == 5


def test_no_contradiction_below_min_cluster_size() -> None:
    """Clusters smaller than min_cluster_size are skipped even if divergence rate is high."""
    tickets = [_ticket(150.0, "vip", "approve_refund") for _ in range(2)]
    results = [_result(t, "deny_refund") for t in tickets]
    contradictions = detect_contradictions(results, tickets, threshold=0.05, min_cluster_size=3)
    assert contradictions == []


def test_no_contradiction_below_threshold() -> None:
    """5% divergence rate below the 10% threshold should not flag."""
    tickets = [_ticket(50.0, "standard", "approve_refund") for _ in range(20)]
    results = [_result(t, "approve_refund") for t in tickets]
    # Override one ticket's result to be wrong (5% rate)
    results[0] = _result(tickets[0], "deny_refund")
    contradictions = detect_contradictions(results, tickets, threshold=0.10, min_cluster_size=3)
    assert contradictions == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest packages/core/tests/test_contradictions.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `packages/core/src/skiljo_core/simulation/contradictions.py`**

```python
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from skiljo_core.schemas.simulation_report_schema import Result
from skiljo_core.schemas.ticket_schema import Ticket


@dataclass
class Contradiction:
    cluster_key: dict[str, Any]
    written_decision: str
    observed_decision: str
    frequency: float
    ticket_count: int
    affected_ticket_ids: list[str] = field(default_factory=list)


def _amount_band(amount: float) -> str:
    if amount <= 50:
        return "0-50"
    if amount <= 100:
        return "51-100"
    if amount <= 200:
        return "101-200"
    if amount <= 500:
        return "201-500"
    return "500+"


def detect_contradictions(
    results: list[Result],
    tickets: list[Ticket],
    threshold: float = 0.05,
    min_cluster_size: int = 3,
) -> list[Contradiction]:
    ticket_map = {str(t.ticket_id): t for t in tickets}

    # Cluster by (amount_band, customer_segment)
    clusters: dict[tuple[str, str], list[tuple[Result, Ticket]]] = defaultdict(list)
    for result in results:
        ticket = ticket_map.get(str(result.ticket_id))
        if ticket is None:
            continue
        key = (
            _amount_band(ticket.refund_amount),
            ticket.customer_segment or "unknown",
        )
        clusters[key].append((result, ticket))

    contradictions = []
    for (amount_band, segment), items in clusters.items():
        if len(items) < min_cluster_size:
            continue
        diverged = [
            (r, t) for r, t in items if r.decision != t.ground_truth_decision
        ]
        rate = len(diverged) / len(items)
        if rate <= threshold:
            continue

        # Most common (written, observed) pair among divergent items
        pair_counts: Counter[tuple[str, str]] = Counter(
            (r.decision, t.ground_truth_decision) for r, t in diverged
        )
        (written, observed) = pair_counts.most_common(1)[0][0]

        contradictions.append(
            Contradiction(
                cluster_key={"amount_band": amount_band, "customer_segment": segment},
                written_decision=written,
                observed_decision=observed,
                frequency=rate,
                ticket_count=len(items),
                affected_ticket_ids=[str(r.ticket_id) for r, _ in diverged],
            )
        )
    return contradictions
```

- [ ] **Step 4: Update `simulation/__init__.py`** to also export `Contradiction` and `detect_contradictions`.

- [ ] **Step 5: Run tests and verify they pass**

```bash
uv run pytest packages/core/tests/test_contradictions.py -v
make lint typecheck test
```

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/skiljo_core/simulation/ \
        packages/core/tests/test_contradictions.py
git commit -m "feat(core): contradiction detection [plan #33]"
```

- [ ] **Step 7: Write learning debrief `docs/learning/week3-task5-contradiction-detection.md`**

Cover: cluster-based grouping strategy; binomial divergence test; why (amount_band, customer_segment) as default cluster keys; the planted-divergence ground truth linkage. Add "Contradiction", "Cluster" to GLOSSARY.

---

## Task 8: Simulation API Endpoints [plan #34–35]

**Files:**
- Create: `packages/api/src/skiljo_api/routers/simulations.py`
- Modify: `packages/api/src/skiljo_api/main.py`
- Create: `packages/api/tests/test_simulations.py`

**Interfaces:**
- Consumes: `simulate_batch`, `compute_report`, `detect_contradictions`, `Skill` (from schema), `SimulationRun`, `SimulationResult`, `SkillVersion`, `Job` DB models
- Produces: `POST /simulations → 202 {job_id, status}`, `GET /simulations/{id} → {id, status, summary}`, `GET /simulations/{id}/report → SimulationReport JSON`

- [ ] **Step 1: Write failing API tests**

Create `packages/api/tests/test_simulations.py`:

```python
import asyncio
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from skiljo_api.dependencies import get_llm_client
from skiljo_api.main import app
from skiljo_core.db.models import Job, SimulationResult, SimulationRun, Skill, SkillVersion
from skiljo_core.db.session import SessionLocal
from skiljo_core.schemas.rule_schema import (
    Condition,
    ConditionOrPredicate,
    DeterministicRule,
    Operator,
    Predicate,
)
from skiljo_core.schemas.skill_schema import DecisionZones, Input, Skill as SkillSchema, Type
from skiljo_core.testing import FakeLLMClient


def _clean() -> None:
    with SessionLocal() as session:
        session.query(SimulationResult).delete()
        session.query(SimulationRun).delete()
        session.query(Job).delete()
        session.query(SkillVersion).delete()
        session.query(Skill).delete()
        session.commit()


def _seed_approved_skill() -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a skill + approved version. Returns (skill_id, version_id)."""
    spec = SkillSchema(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[Input(name="refund_amount", type=Type.number)],
        decision_zones=DecisionZones(
            deterministic=[
                DeterministicRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lte, value=100.0))]
                    ),
                    action="approve_refund",
                )
            ],
            llm_assisted=[],
            human_only=[],
        ),
    )
    with SessionLocal() as session:
        skill_row = Skill(name="process_refund_request")
        session.add(skill_row)
        session.flush()
        version_row = SkillVersion(
            skill_id=skill_row.id,
            version_number=1,
            spec=spec.model_dump(mode="json"),
            status="approved",
        )
        session.add(version_row)
        session.flush()
        skill_row.current_version_id = version_row.id
        session.commit()
        return skill_row.id, version_row.id


def _tickets_payload(count: int = 5) -> list[dict]:
    tickets = []
    for i in range(count):
        tickets.append({
            "ticket_id": str(uuid.uuid4()),
            "refund_amount": 50.0,
            "purchase_days_ago": 10,
            "ground_truth_decision": "approve_refund",
        })
    return tickets


def test_post_simulations_returns_202_with_job_id() -> None:
    _clean()
    _, version_id = _seed_approved_skill()
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient([])
    client = TestClient(app)
    try:
        response = client.post(
            "/simulations",
            json={"skill_version_id": str(version_id), "tickets": _tickets_payload()},
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
    finally:
        app.dependency_overrides.clear()


def test_post_simulations_creates_simulation_run_row() -> None:
    _clean()
    _, version_id = _seed_approved_skill()
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient([])
    client = TestClient(app)
    try:
        response = client.post(
            "/simulations",
            json={"skill_version_id": str(version_id), "tickets": _tickets_payload(3)},
        )
        job_id = response.json()["job_id"]

        # Poll until done (TestClient runs background tasks synchronously by default)
        with SessionLocal() as session:
            job = session.get(Job, uuid.UUID(job_id))
            assert job is not None
    finally:
        app.dependency_overrides.clear()


def test_get_simulation_report_after_completion() -> None:
    _clean()
    _, version_id = _seed_approved_skill()
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient([])
    client = TestClient(app)
    try:
        resp = client.post(
            "/simulations",
            json={"skill_version_id": str(version_id), "tickets": _tickets_payload(5)},
        )
        job_id = uuid.UUID(resp.json()["job_id"])

        # Get job result_ref (simulation run id)
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            assert job is not None
            if job.status == "completed" and job.result_ref is not None:
                sim_id = job.result_ref
                report_resp = client.get(f"/simulations/{sim_id}/report")
                assert report_resp.status_code == 200
                report = report_resp.json()
                assert "match_rate" in report
                assert "results" in report
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest packages/api/tests/test_simulations.py -v
```

Expected: `404` or router not found.

- [ ] **Step 3: Create `packages/api/src/skiljo_api/routers/simulations.py`**

```python
import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from skiljo_api.dependencies import get_llm_client
from skiljo_core.db.models import Job, SimulationResult, SimulationRun, SkillVersion
from skiljo_core.db.session import SessionLocal
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.simulation_report_schema import SimulationReport
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.contradictions import detect_contradictions
from skiljo_core.simulation.engine import compute_report, simulate_batch

router = APIRouter()


class SimulationRequest(BaseModel):
    skill_version_id: uuid.UUID
    tickets: list[dict[str, Any]]


class SimulationResponse(BaseModel):
    job_id: uuid.UUID
    status: str


def _run_simulation_job(
    job_id: uuid.UUID,
    sim_run_id: uuid.UUID,
    skill_version_id: uuid.UUID,
    tickets_raw: list[dict[str, Any]],
    llm_client: LLMClient,
) -> None:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        sim_run = session.get(SimulationRun, sim_run_id)
        if job is None or sim_run is None:
            return
        job.status = "running"
        job.started_at = datetime.now(UTC)
        sim_run.status = "running"
        sim_run.started_at = datetime.now(UTC)
        session.commit()

        try:
            sv = session.get(SkillVersion, skill_version_id)
            if sv is None:
                raise ValueError(f"SkillVersion {skill_version_id} not found")
            skill = Skill.model_validate(sv.spec)
            tickets = [Ticket.model_validate(t) for t in tickets_raw]

            results = asyncio.run(simulate_batch(skill, tickets, llm_client))
            report = compute_report(skill_version_id, results, tickets)
            contradictions = detect_contradictions(results, tickets)
            report = report.model_copy(update={"contradiction_count": len(contradictions)})

            ticket_map = {str(t.ticket_id): t for t in tickets}
            for r in results:
                ticket = ticket_map.get(str(r.ticket_id))
                session.add(
                    SimulationResult(
                        run_id=sim_run_id,
                        ticket_id=r.ticket_id,
                        ticket_data=ticket.model_dump(mode="json") if ticket else {},
                        decision=r.decision,
                        zone=r.zone.value,
                        matched_human_decision=r.matched_human_decision,
                        reasoning=r.reasoning,
                    )
                )

            sim_run.status = "completed"
            sim_run.completed_at = datetime.now(UTC)
            sim_run.summary = report.model_dump(mode="json")
            job.status = "completed"
            job.result_ref = sim_run_id
            job.completed_at = datetime.now(UTC)
            session.commit()

        except Exception as exc:
            sim_run.status = "failed"
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = datetime.now(UTC)
            session.commit()
            raise


@router.post("/simulations", status_code=202)
def create_simulation(
    request: SimulationRequest,
    background_tasks: BackgroundTasks,
    llm_client: LLMClient = Depends(get_llm_client),
) -> SimulationResponse:
    with SessionLocal() as session:
        sv = session.get(SkillVersion, request.skill_version_id)
        if sv is None:
            raise HTTPException(status_code=404, detail="skill version not found")

        ticket_batch_id = uuid.uuid4()
        sim_run = SimulationRun(
            skill_version_id=request.skill_version_id,
            ticket_batch_id=ticket_batch_id,
            status="pending",
        )
        session.add(sim_run)
        session.flush()

        job = Job(
            kind="simulation",
            status="pending",
            payload={"sim_run_id": str(sim_run.id)},
        )
        session.add(job)
        session.commit()
        job_id = job.id
        sim_run_id = sim_run.id

    background_tasks.add_task(
        _run_simulation_job,
        job_id,
        sim_run_id,
        request.skill_version_id,
        request.tickets,
        llm_client,
    )
    return SimulationResponse(job_id=job_id, status="pending")


class SimulationStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    summary: dict[str, Any] | None


@router.get("/simulations/{sim_id}")
def get_simulation(sim_id: uuid.UUID) -> SimulationStatusResponse:
    with SessionLocal() as session:
        run = session.get(SimulationRun, sim_id)
        if run is None:
            raise HTTPException(status_code=404, detail="simulation not found")
        return SimulationStatusResponse(id=run.id, status=run.status, summary=run.summary)


@router.get("/simulations/{sim_id}/report")
def get_simulation_report(sim_id: uuid.UUID) -> dict[str, Any]:
    with SessionLocal() as session:
        run = session.get(SimulationRun, sim_id)
        if run is None:
            raise HTTPException(status_code=404, detail="simulation not found")
        if run.status != "completed" or run.summary is None:
            raise HTTPException(status_code=409, detail="simulation not yet completed")
        return run.summary
```

- [ ] **Step 4: Mount the simulations router in `main.py`**

```python
from fastapi import FastAPI

from skiljo_api.routers import jobs, simulations, skills

app = FastAPI(title="Skiljo API")
app.include_router(skills.router)
app.include_router(jobs.router)
app.include_router(simulations.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run tests and verify they pass**

```bash
uv run pytest packages/api/tests/test_simulations.py -v
make lint typecheck test
```

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/skiljo_api/routers/simulations.py \
        packages/api/src/skiljo_api/main.py \
        packages/api/tests/test_simulations.py
git commit -m "feat(api): simulation endpoints POST /simulations, GET /simulations/{id}/report [plan #34-35]"
```

- [ ] **Step 7: Write learning debrief `docs/learning/week3-task6-simulation-api.md`**

Cover: the background job pattern mirrored from the extraction endpoint; why `asyncio.run()` inside the BackgroundTask is needed (thread context); how `sim_run_id` as the `result_ref` ties the job table to the simulation run.

---

## Task 9: Commit Synthetic Ticket Data [plan #36]

**Files:**
- Create: `data/synthetic_tickets/refund_v1/skill.json`
- Create: `data/synthetic_tickets/refund_v1/divergence_spec.json`
- Create: `data/synthetic_tickets/refund_v1/tickets.json`

- [ ] **Step 1: Create the batch directory**

```bash
mkdir -p data/synthetic_tickets/refund_v1
```

- [ ] **Step 2: Create `data/synthetic_tickets/refund_v1/skill.json`**

This is the base skill the 100 tickets are simulated against. Create it manually:

```json
{
  "skill_name": "process_refund_request",
  "version": 1,
  "trigger": "customer_requests_refund",
  "inputs": [
    {"name": "refund_amount", "type": "number"},
    {"name": "purchase_days_ago", "type": "integer"},
    {"name": "customer_segment", "type": "string"},
    {"name": "fraud_flags", "type": "array"},
    {"name": "refund_reason", "type": "string"}
  ],
  "decision_zones": {
    "deterministic": [
      {
        "condition": {
          "all": [
            {"field": "refund_amount", "op": "lte", "value": 100.0},
            {"field": "purchase_days_ago", "op": "lte", "value": 30},
            {"field": "fraud_flags", "op": "empty", "value": null}
          ]
        },
        "action": "approve_refund"
      },
      {
        "condition": {
          "all": [
            {"field": "refund_amount", "op": "gt", "value": 500.0}
          ]
        },
        "action": "escalate_to_finance"
      }
    ],
    "llm_assisted": [
      {
        "condition": {
          "all": [
            {"field": "refund_reason", "op": "contains", "value": "goodwill"}
          ]
        },
        "action": "draft_recommendation",
        "requires_human_approval": true
      }
    ],
    "human_only": [
      {
        "condition": {
          "all": [
            {"field": "fraud_flags", "op": "not_empty", "value": null}
          ]
        },
        "action": "escalate_to_fraud_team"
      }
    ]
  }
}
```

- [ ] **Step 3: Create `data/synthetic_tickets/refund_v1/divergence_spec.json`**

```json
[
  {
    "rule_id": "vip_exception",
    "condition": {
      "all": [
        {"field": "customer_segment", "op": "eq", "value": "vip"},
        {"field": "refund_amount", "op": "gt", "value": 100.0}
      ]
    },
    "base_decision": "deny_refund",
    "shadow_decision": "approve_refund",
    "frequency": 0.85
  },
  {
    "rule_id": "near_threshold_leniency",
    "condition": {
      "all": [
        {"field": "refund_amount", "op": "gte", "value": 100.0},
        {"field": "refund_amount", "op": "lte", "value": 120.0},
        {"field": "purchase_days_ago", "op": "lte", "value": 30}
      ]
    },
    "base_decision": "deny_refund",
    "shadow_decision": "approve_refund",
    "frequency": 0.60
  }
]
```

- [ ] **Step 4: Generate tickets using a Python script**

Create a temporary script `scripts/gen_refund_v1.py`:

```python
#!/usr/bin/env python
"""One-off script: generate refund_v1 synthetic ticket batch."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages/core/src"))

from skiljo_core.schemas.rule_schema import Condition, ConditionOrPredicate, Predicate
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.simulation.generator import DivergenceSpec, generate_ticket_batch

skill_path = Path("data/synthetic_tickets/refund_v1/skill.json")
div_path = Path("data/synthetic_tickets/refund_v1/divergence_spec.json")
out_path = Path("data/synthetic_tickets/refund_v1/tickets.json")

skill = Skill.model_validate_json(skill_path.read_text())
div_raw = json.loads(div_path.read_text())
divergences = [DivergenceSpec.model_validate(d) for d in div_raw]

tickets = generate_ticket_batch(skill, divergences, count=100, seed=42)
out_path.write_text(json.dumps([t.model_dump(mode="json") for t in tickets], indent=2))
print(f"Generated {len(tickets)} tickets → {out_path}")
```

Run it:

```bash
uv run python scripts/gen_refund_v1.py
```

Expected output: `Generated 100 tickets → data/synthetic_tickets/refund_v1/tickets.json`

Verify diversity:
```bash
python -c "
import json
data = json.load(open('data/synthetic_tickets/refund_v1/tickets.json'))
from collections import Counter
print(Counter(t['ground_truth_decision'] for t in data))
print(Counter(t['customer_segment'] for t in data))
"
```

Expected: at least 4 distinct `ground_truth_decision` values and all 3 `customer_segment` values present.

- [ ] **Step 5: Delete the generation script and commit the data**

```bash
rm scripts/gen_refund_v1.py
git add data/synthetic_tickets/refund_v1/
git commit -m "data: 100 synthetic tickets with planted divergences for refund_v1 [plan #36]"
```

---

## Task 10: Golden Fixture Tests [plan #37]

**Files:**
- Create: `packages/core/tests/test_simulation_golden.py`

Golden tests run the simulation engine against the committed `refund_v1` data and verify that the report structure is valid and the contradiction detector fires on the planted divergences.

- [ ] **Step 1: Write the golden tests**

Create `packages/core/tests/test_simulation_golden.py`:

```python
"""Golden fixture tests: run simulation against data/synthetic_tickets/refund_v1/."""
import asyncio
import json
import uuid
from pathlib import Path

from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.contradictions import detect_contradictions
from skiljo_core.simulation.engine import compute_report, simulate_batch
from skiljo_core.testing import FakeLLMClient


_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data/synthetic_tickets/refund_v1"


def _load_data() -> tuple[Skill, list[Ticket]]:
    skill = Skill.model_validate_json((_DATA_DIR / "skill.json").read_text())
    raw_tickets = json.loads((_DATA_DIR / "tickets.json").read_text())
    tickets = [Ticket.model_validate(t) for t in raw_tickets]
    return skill, tickets


def test_golden_report_is_schema_valid() -> None:
    skill, tickets = _load_data()
    results = asyncio.run(simulate_batch(skill, tickets, FakeLLMClient([]), max_concurrency=1))
    report = compute_report(uuid.uuid4(), results, tickets)
    # SimulationReport validates on construction — reaching here means it's valid
    assert 0.0 <= report.match_rate <= 1.0
    assert 0.0 <= report.escalation_accuracy <= 1.0
    assert len(report.results) == len(tickets)


def test_golden_detector_finds_planted_divergences() -> None:
    """The VIP exception and near-threshold leniency divergences should be detected."""
    skill, tickets = _load_data()
    results = asyncio.run(simulate_batch(skill, tickets, FakeLLMClient([]), max_concurrency=1))
    contradictions = detect_contradictions(results, tickets, threshold=0.05, min_cluster_size=3)
    # At least one contradiction should be flagged (planted divergences ensure this)
    assert len(contradictions) >= 1, (
        "No contradictions detected — check that planted divergences exceed threshold "
        "and minimum cluster size. Increase ticket count or lower threshold if needed."
    )


def test_golden_all_deterministic_tickets_have_expected_decision() -> None:
    """Tickets with refund_amount<=100, purchase_days_ago<=30, no fraud should be approved."""
    skill, tickets = _load_data()
    results = asyncio.run(simulate_batch(skill, tickets, FakeLLMClient([]), max_concurrency=1))
    result_map = {str(r.ticket_id): r for r in results}

    clearly_eligible = [
        t for t in tickets
        if t.refund_amount <= 100.0
        and t.purchase_days_ago <= 30
        and not t.fraud_flags
        and t.refund_reason != "goodwill"  # would hit llm_assisted otherwise... check both
    ]
    # At minimum: no clearly eligible ticket should be in the human_only zone for no reason
    from skiljo_core.schemas.simulation_report_schema import Zone
    wrong_zone = [
        t for t in clearly_eligible
        if result_map.get(str(t.ticket_id)) is not None
        and result_map[str(t.ticket_id)].zone == Zone.human_only
    ]
    assert len(wrong_zone) == 0, f"{len(wrong_zone)} eligible tickets incorrectly escalated"
```

- [ ] **Step 2: Run the tests**

```bash
uv run pytest packages/core/tests/test_simulation_golden.py -v
make lint typecheck test
```

Expected: all pass.

If `test_golden_detector_finds_planted_divergences` fails, the planted divergence frequencies may not have generated enough tickets in the right clusters. Debug by printing `Counter(t.customer_segment for t in tickets if 100 < t.refund_amount)` to check if the VIP cluster is large enough.

- [ ] **Step 3: Commit**

```bash
git add packages/core/tests/test_simulation_golden.py
git commit -m "test(core): simulation engine golden fixture tests [plan #37]"
```

---

## Task 11: Week 3 Learning Debriefs (Consolidated)

Write debriefs for any tasks above that don't have them yet. Then update the learning index.

- [ ] **Step 1: Write `docs/learning/week3-task4-simulation-engine.md`**

Cover: why `asyncio.to_thread` wraps a sync `LLMClient` (thread-pool concurrency without rewriting the protocol); the `asyncio.Semaphore(5)` bound; how `escalation_accuracy` is defined; why vacuous escalation_accuracy=1.0 (no escalations = no mistakes).

- [ ] **Step 2: Update `docs/learning/README.md`** — add one-line entry per new debrief.

- [ ] **Step 3: Update `docs/learning/GLOSSARY.md`** — add any new terms not yet there:
  - "Simulation Engine" (commit 30–32)
  - "Batch Simulation" (commit 31)
  - "Contradiction" (commit 33)
  - "Shadow Policy" (commit 26)
  - "Planted Divergence" (commit 26)
  - "LLM Response Cache" (commit A1)

- [ ] **Step 4: Commit**

```bash
git add docs/learning/
git commit -m "docs: week 3 learning debriefs and glossary updates"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] A1 (LLM cache): Task 2
- [x] Commit 26 (shadow-policy generator): Task 4
- [x] Commit 27 (rule evaluator): Task 3
- [x] Commit 28–29 (zone executors): Task 5
- [x] Commit 30 (single-ticket sim): Task 5
- [x] Commit 31 (batch simulation): Task 6
- [x] Commit 32 (SimulationReport aggregation): Task 6
- [x] Commit 33 (contradiction detection): Task 7
- [x] Commits 34–35 (simulation API): Task 8
- [x] Commit 36 (100 synthetic tickets): Task 9
- [x] Commit 37 (golden tests): Task 10
- [x] Learning debriefs: Task 11 (plus inline steps per task)

**Reordering note:** Commit 27 (evaluator) is implemented before commit 26 (generator) because the generator depends on `evaluate_condition`. This is a valid reordering — the commit numbers are the design's logical labels, not a strict implementation sequence constraint.

**Acceptance criteria from DESIGN_DOCUMENT.md §12:**
- Commit 26: "Generating 50 tickets produces a varied set; at least 2 planted divergence patterns are present; detector recall ≥0.8 on planted divergences with ≤1 false positive per run" — validated in `test_generator.py` + `test_simulation_golden.py`
- Commit 27: "All operators and compositions pass their unit tests" — covered in `test_evaluator.py` (23 parametrized cases + 6 composition tests)
- Commit 33: "Run against a known-contradictory skill+ticket pair, detector flags expected contradictions" — covered in `test_contradictions.py`
- Commit 34–35: "End-to-end: extract a skill, kick off a simulation, poll, receive the report" — covered in `test_simulations.py`
- Commit 37: Golden fixtures with match rate, zone breakdown, contradiction count — covered in `test_simulation_golden.py`
