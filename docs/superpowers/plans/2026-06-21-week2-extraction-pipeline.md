# Week 2 Extraction Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the LLM client (Anthropic, tool-use, retry, logging), the 4-pass extraction pipeline (segment → extract rules → classify zones → assemble), the `/skills/extract` + `/jobs/{id}` + read endpoints, and 20 hand-labeled eval examples — turning raw policy text into a schema-valid, persisted `Skill` spec.

**Architecture:** Two mock layers throughout, per the spec: `AnthropicClient`'s own tests patch the `anthropic` SDK's `messages.create` directly (DI via an injected `client` param); everything built on `LLMClient` (extraction passes, API endpoints) is tested against a `FakeLLMClient` test double. No real Anthropic API calls anywhere in this plan.

**Tech Stack:** `anthropic` Python SDK (tool-use mode), Pydantic v2, SQLAlchemy 2.x (existing `db/models.py`), FastAPI `BackgroundTasks`, `python-dotenv`, PyYAML (eval data).

**Spec:** `docs/superpowers/specs/2026-06-21-week2-extraction-pipeline-design.md`.

## Global Constraints

- No Anthropic API key required for any test in this plan — every test must pass via mocking. A real key existing in `.env` is irrelevant to test correctness here.
- Default model for all extraction LLM calls: `claude-sonnet-4-6` (constant: `skiljo_core.config.DEFAULT_MODEL`).
- `generate_structured`'s retry budget is 3 attempts (validation error fed back into the next attempt's prompt).
- Assembly's "repair loop" is implemented by delegating to `generate_structured`'s own retry mechanism (calling it with `schema=Skill` directly), not a separate counter — see Task 7.
- Python `>=3.12,<3.13` (inherited from Week 1; do not change).
- Commit format: `<type>(<scope>): <summary>`, single line, no `Co-Authored-By` trailer (per this repo's CLAUDE.md and established convention this project).
- Eval data (Task 11): exactly the 20 examples per `docs/POLICY_CORPUS.md`'s "How to use this corpus" section — the 8 easy + 8 hard + reserve-4-for-dev split named there. Use only the Steam (#14) and Shopify (#12) **excerpts** called for in that split; the full documents are reserved for the held-out test set later, not for `data/eval/train/`.
- Every new Pydantic model reuses the existing generated schema types (`skiljo_core.schemas.skill_schema`, `skiljo_core.schemas.rule_schema`) wherever the shape matches — do not redefine `Skill`, `DeterministicRule`, `LLMAssistedRule`, `HumanOnlyRule`, `Condition`, `Predicate`, `Operator`.
- `Condition.all`/`Condition.any` items are typed `ConditionOrPredicate` (a `RootModel[Predicate | Condition]`). Pydantic auto-wraps a raw `Predicate`/`Condition` passed into the list, but reading a value back out requires `.root` (e.g. `condition.all[0].root.field`, not `.field` directly) — confirmed by direct testing against the installed schema module.

---

### Task 1: Config loading, LLM client protocol, and Anthropic implementation (no retry/logging yet)

**Files:**
- Create: `packages/core/src/skiljo_core/config.py`
- Create: `packages/core/src/skiljo_core/llm/__init__.py`
- Create: `packages/core/src/skiljo_core/llm/base.py`
- Create: `packages/core/src/skiljo_core/llm/anthropic_client.py`
- Test: `packages/core/tests/test_anthropic_client.py`
- Modify: `packages/core/pyproject.toml` (add `anthropic`, `python-dotenv` dependencies)

**Interfaces:**
- Produces: `skiljo_core.config.DATABASE_URL: str | None`, `skiljo_core.config.ANTHROPIC_API_KEY: str | None`, `skiljo_core.config.DEFAULT_MODEL: str = "claude-sonnet-4-6"`.
- Produces: `skiljo_core.llm.base.StructuredResponse` (generic dataclass: `data: T`, `attempts: int = 1`, `llm_call_id: UUID | None = None`).
- Produces: `skiljo_core.llm.base.LLMClient` (Protocol with `generate_structured(self, prompt: str, schema: type[T], model: str, prompt_version: str, temperature: float = 0.0, max_tokens: int = 4096) -> StructuredResponse[T]`).
- Produces: `skiljo_core.llm.anthropic_client.AnthropicClient(api_key: str | None = None, client: anthropic.Anthropic | None = None)` implementing `LLMClient`.

- [ ] **Step 1: Add dependencies to `packages/core/pyproject.toml`**

Modify the `dependencies` list:

```toml
dependencies = [
    "pydantic>=2.9",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "psycopg[binary]>=3.2",
    "anthropic>=0.40",
    "python-dotenv>=1.0",
]
```

- [ ] **Step 2: Sync dependencies**

```bash
uv sync --all-packages
```

Expected: exit 0; `anthropic` and `python-dotenv` appear in the install list.

- [ ] **Step 3: Create `packages/core/src/skiljo_core/config.py`**

```python
import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
DEFAULT_MODEL = "claude-sonnet-4-6"
```

- [ ] **Step 4: Create `packages/core/src/skiljo_core/llm/__init__.py`** (empty file)

- [ ] **Step 5: Create `packages/core/src/skiljo_core/llm/base.py`**

```python
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class StructuredResponse(Generic[T]):
    data: T
    attempts: int = 1
    llm_call_id: UUID | None = None


class LLMClient(Protocol):
    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        model: str,
        prompt_version: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> StructuredResponse[T]:
        """Generate output constrained to the given Pydantic schema.

        Logs the call to llm_calls before returning. Retries on schema
        validation failure up to 3 times with feedback.
        """
        ...
```

- [ ] **Step 6: Write the failing test — `packages/core/tests/test_anthropic_client.py`**

```python
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import BaseModel

from skiljo_core.llm.anthropic_client import AnthropicClient


class Greeting(BaseModel):
    message: str


def tool_use_response(tool_input: dict, input_tokens: int = 10, output_tokens: int = 10) -> SimpleNamespace:
    """Fake Anthropic SDK response shape: response.content[i].type/.input, response.usage.*."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", input=tool_input)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_generate_structured_returns_validated_output() -> None:
    fake_sdk_client = Mock()
    fake_sdk_client.messages.create.return_value = tool_use_response({"message": "hello"})
    client = AnthropicClient(client=fake_sdk_client)

    result = client.generate_structured(
        prompt="Say hello",
        schema=Greeting,
        model="claude-sonnet-4-6",
        prompt_version="v1",
    )

    assert result.data == Greeting(message="hello")
    assert result.attempts == 1
    fake_sdk_client.messages.create.assert_called_once()
    _, kwargs = fake_sdk_client.messages.create.call_args
    assert kwargs["model"] == "claude-sonnet-4-6"
    assert kwargs["tool_choice"] == {"type": "tool", "name": "extract"}
```

- [ ] **Step 7: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_anthropic_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skiljo_core.llm.anthropic_client'`.

- [ ] **Step 8: Write minimal implementation — `packages/core/src/skiljo_core/llm/anthropic_client.py`**

```python
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from skiljo_core import config
from skiljo_core.llm.base import StructuredResponse

T = TypeVar("T", bound=BaseModel)


class AnthropicClient:
    def __init__(self, api_key: str | None = None, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or anthropic.Anthropic(api_key=api_key or config.ANTHROPIC_API_KEY)

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        model: str,
        prompt_version: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> StructuredResponse[T]:
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
            messages=[{"role": "user", "content": prompt}],
        )
        tool_use_block = next(block for block in response.content if block.type == "tool_use")
        data = schema.model_validate(tool_use_block.input)
        return StructuredResponse(data=data, attempts=1)
```

- [ ] **Step 9: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_anthropic_client.py -v
```

Expected: PASS (1 test).

- [ ] **Step 10: Commit**

```bash
git add packages/core/pyproject.toml packages/core/src/skiljo_core/config.py packages/core/src/skiljo_core/llm packages/core/tests/test_anthropic_client.py uv.lock
git commit -m "feat(core): LLM client protocol and Anthropic implementation"
```

---

### Task 2: Structured output via tool-use with validation retry

**Files:**
- Modify: `packages/core/src/skiljo_core/llm/anthropic_client.py`
- Modify: `packages/core/tests/test_anthropic_client.py`

**Interfaces:**
- Consumes: `AnthropicClient` from Task 1; `tool_use_response()` helper already defined in the test file.
- Produces: same `AnthropicClient.generate_structured` signature, now retrying up to 3 attempts on `pydantic.ValidationError`, feeding the error back into the prompt text for the next attempt.

- [ ] **Step 1: Write the failing test — append to `packages/core/tests/test_anthropic_client.py`**

```python
def test_retries_once_on_invalid_output_then_succeeds() -> None:
    fake_sdk_client = Mock()
    fake_sdk_client.messages.create.side_effect = [
        tool_use_response({"wrong_field": "x"}),  # missing required "message" -> ValidationError
        tool_use_response({"message": "hello"}),  # valid
    ]
    client = AnthropicClient(client=fake_sdk_client)

    result = client.generate_structured(
        prompt="Say hello",
        schema=Greeting,
        model="claude-sonnet-4-6",
        prompt_version="v1",
    )

    assert result.data == Greeting(message="hello")
    assert result.attempts == 2
    assert fake_sdk_client.messages.create.call_count == 2


def test_raises_after_three_failed_attempts() -> None:
    from pydantic import ValidationError

    fake_sdk_client = Mock()
    fake_sdk_client.messages.create.return_value = tool_use_response({"wrong_field": "x"})
    client = AnthropicClient(client=fake_sdk_client)

    try:
        client.generate_structured(
            prompt="Say hello",
            schema=Greeting,
            model="claude-sonnet-4-6",
            prompt_version="v1",
        )
        raise AssertionError("expected ValidationError to be raised")
    except ValidationError:
        pass

    assert fake_sdk_client.messages.create.call_count == 3
```

- [ ] **Step 2: Run tests to verify the new ones fail**

```bash
uv run pytest packages/core/tests/test_anthropic_client.py -v
```

Expected: the two new tests FAIL (current implementation has no retry, so `test_retries_once_on_invalid_output_then_succeeds` raises `ValidationError` on the first attempt instead of retrying, and `test_raises_after_three_failed_attempts` fails on attempt 1 with only 1 call recorded instead of 3). The Task 1 test still passes.

- [ ] **Step 3: Modify `generate_structured` in `packages/core/src/skiljo_core/llm/anthropic_client.py`**

Replace the method body:

```python
from pydantic import BaseModel, ValidationError
```

(add `ValidationError` to the existing `from pydantic import BaseModel` line)

```python
    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        model: str,
        prompt_version: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> StructuredResponse[T]:
        current_prompt = prompt
        last_error: ValidationError | None = None
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
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
            tool_use_block = next(block for block in response.content if block.type == "tool_use")
            try:
                data = schema.model_validate(tool_use_block.input)
            except ValidationError as exc:
                last_error = exc
                current_prompt = (
                    f"{prompt}\n\nYour previous attempt produced invalid output. "
                    f"Validation error: {exc}\nPlease correct it and try again."
                )
                continue
            return StructuredResponse(data=data, attempts=attempt)
        assert last_error is not None
        raise last_error
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest packages/core/tests/test_anthropic_client.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/skiljo_core/llm/anthropic_client.py packages/core/tests/test_anthropic_client.py
git commit -m "feat(core): structured output via tool-use with validation retry"
```

---

### Task 3: LLM call logging to Postgres

**Files:**
- Create: `packages/core/src/skiljo_core/db/session.py`
- Create: `packages/core/src/skiljo_core/llm/logging.py`
- Modify: `packages/core/src/skiljo_core/llm/anthropic_client.py`
- Modify: `packages/core/tests/test_anthropic_client.py`

**Interfaces:**
- Produces: `skiljo_core.db.session.SessionLocal` (a `sessionmaker` bound to an engine built from `config.DATABASE_URL`).
- Produces: `skiljo_core.llm.logging.LLMCallLogger(session_factory: Callable[[], Session])` with `.log(provider, model, prompt_version, prompt_text, response_text, latency_ms, input_tokens=None, output_tokens=None) -> uuid.UUID`.
- Produces: `AnthropicClient(..., logger: LLMCallLogger | None = None)` — every attempt is logged when a logger is provided; `StructuredResponse.llm_call_id` is set to the successful attempt's row id.

This task's test requires the local Postgres from Week 1 running and `DATABASE_URL` resolvable. `config.py`'s `load_dotenv()` (Task 1) finds `.env` automatically when pytest's CWD is the repo root (the standard way these tests are run), so no manual `source .env` is needed — only `docker compose up -d postgres` if it isn't already running.

- [ ] **Step 1: Ensure Postgres is running**

```bash
docker compose up -d postgres
docker compose ps postgres
```

Expected: status `healthy`.

- [ ] **Step 2: Create `packages/core/src/skiljo_core/db/session.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from skiljo_core import config

engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
```

- [ ] **Step 3: Write the failing test — append to `packages/core/tests/test_anthropic_client.py`**

```python
def test_logs_every_attempt_to_llm_calls_table() -> None:
    from skiljo_core.db.models import LLMCall
    from skiljo_core.db.session import SessionLocal
    from skiljo_core.llm.logging import LLMCallLogger

    with SessionLocal() as session:
        session.query(LLMCall).delete()
        session.commit()

    fake_sdk_client = Mock()
    fake_sdk_client.messages.create.return_value = tool_use_response({"message": "hello"}, input_tokens=7, output_tokens=3)
    logger = LLMCallLogger(session_factory=SessionLocal)
    client = AnthropicClient(client=fake_sdk_client, logger=logger)

    result = client.generate_structured(
        prompt="Say hello",
        schema=Greeting,
        model="claude-sonnet-4-6",
        prompt_version="v1",
    )

    with SessionLocal() as session:
        rows = session.query(LLMCall).all()
        assert len(rows) == 1
        assert rows[0].id == result.llm_call_id
        assert rows[0].provider == "anthropic"
        assert rows[0].model == "claude-sonnet-4-6"
        assert rows[0].prompt_version == "v1"
        assert rows[0].input_tokens == 7
        assert rows[0].output_tokens == 3


def test_logs_one_row_per_attempt_on_retry() -> None:
    from skiljo_core.db.models import LLMCall
    from skiljo_core.db.session import SessionLocal
    from skiljo_core.llm.logging import LLMCallLogger

    with SessionLocal() as session:
        session.query(LLMCall).delete()
        session.commit()

    fake_sdk_client = Mock()
    fake_sdk_client.messages.create.side_effect = [
        tool_use_response({"wrong_field": "x"}),
        tool_use_response({"message": "hello"}),
    ]
    logger = LLMCallLogger(session_factory=SessionLocal)
    client = AnthropicClient(client=fake_sdk_client, logger=logger)

    client.generate_structured(
        prompt="Say hello",
        schema=Greeting,
        model="claude-sonnet-4-6",
        prompt_version="v1",
    )

    with SessionLocal() as session:
        assert session.query(LLMCall).count() == 2
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
uv run pytest packages/core/tests/test_anthropic_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skiljo_core.llm.logging'`.

- [ ] **Step 5: Create `packages/core/src/skiljo_core/llm/logging.py`**

```python
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from skiljo_core.db.models import LLMCall


class LLMCallLogger:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

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
            )
            session.add(call)
            session.commit()
            session.refresh(call)
            return call.id
```

- [ ] **Step 6: Wire logging into `packages/core/src/skiljo_core/llm/anthropic_client.py`**

Replace the full file contents:

```python
import json
import time
from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from skiljo_core import config
from skiljo_core.llm.base import StructuredResponse
from skiljo_core.llm.logging import LLMCallLogger

T = TypeVar("T", bound=BaseModel)


class AnthropicClient:
    def __init__(
        self,
        api_key: str | None = None,
        client: anthropic.Anthropic | None = None,
        logger: LLMCallLogger | None = None,
    ) -> None:
        self._client = client or anthropic.Anthropic(api_key=api_key or config.ANTHROPIC_API_KEY)
        self._logger = logger

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        model: str,
        prompt_version: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> StructuredResponse[T]:
        current_prompt = prompt
        last_error: ValidationError | None = None
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
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
            tool_use_block = next(block for block in response.content if block.type == "tool_use")
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
            return StructuredResponse(data=data, attempts=attempt, llm_call_id=llm_call_id)
        assert last_error is not None
        raise last_error
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
uv run pytest packages/core/tests/test_anthropic_client.py -v
```

Expected: PASS (5 tests).

- [ ] **Step 8: Commit**

```bash
git add packages/core/src/skiljo_core/db/session.py packages/core/src/skiljo_core/llm packages/core/tests/test_anthropic_client.py
git commit -m "feat(core): LLM call logging to Postgres"
```

---

### Task 4: Extraction pass 1 — policy segmentation

**Files:**
- Create: `packages/core/tests/fakes.py`
- Create: `packages/core/src/skiljo_core/extraction/__init__.py`
- Create: `packages/core/src/skiljo_core/extraction/segmentation.py`
- Test: `packages/core/tests/test_segmentation.py`

**Interfaces:**
- Consumes: `skiljo_core.llm.base.LLMClient`, `skiljo_core.config.DEFAULT_MODEL`.
- Produces: `skiljo_core.tests.fakes` is not importable that way — `FakeLLMClient` lives in `packages/core/tests/fakes.py` and is imported by sibling test files as `from fakes import FakeLLMClient` (flat `tests/` directory, no `__init__.py`, matching the existing `test_models.py` layout — pytest prepends `packages/core/tests/` to `sys.path` for every file directly in it).
- Produces: `skiljo_core.extraction.segmentation.Segment` (`segment_type: str`, `text: str`), `SegmentationResult` (`segments: list[Segment]`), `segment_policy(llm_client: LLMClient, policy_text: str, model: str = config.DEFAULT_MODEL) -> list[Segment]`.

- [ ] **Step 1: Create `packages/core/tests/fakes.py`**

```python
from typing import Any, TypeVar

from pydantic import BaseModel

from skiljo_core.llm.base import StructuredResponse

T = TypeVar("T", bound=BaseModel)


class FakeLLMClient:
    """Test double for LLMClient. Returns pre-built Pydantic instances in call order."""

    def __init__(self, responses: list[BaseModel]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        model: str,
        prompt_version: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> StructuredResponse[T]:
        self.calls.append(
            {"prompt": prompt, "schema": schema, "model": model, "prompt_version": prompt_version}
        )
        data = self._responses.pop(0)
        return StructuredResponse(data=data, attempts=1)
```

- [ ] **Step 2: Create `packages/core/src/skiljo_core/extraction/__init__.py`** (empty file)

- [ ] **Step 3: Write the failing test — `packages/core/tests/test_segmentation.py`**

```python
from fakes import FakeLLMClient

from skiljo_core.extraction.segmentation import Segment, SegmentationResult, segment_policy


def test_segment_policy_returns_fake_response_segments() -> None:
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[
                    Segment(segment_type="thresholds", text="Refunds under $100 within 30 days are approved."),
                    Segment(segment_type="exceptions", text="Goodwill exceptions may be granted by support leads."),
                ]
            )
        ]
    )

    segments = segment_policy(fake_client, policy_text="(full policy text)")

    assert len(segments) == 2
    assert segments[0].segment_type == "thresholds"
    assert segments[1].segment_type == "exceptions"
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["prompt_version"] == "segmentation_v1"
```

- [ ] **Step 4: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_segmentation.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skiljo_core.extraction.segmentation'`.

- [ ] **Step 5: Create `packages/core/src/skiljo_core/extraction/segmentation.py`**

```python
from pydantic import BaseModel

from skiljo_core import config
from skiljo_core.llm.base import LLMClient

SEGMENTATION_PROMPT_V1 = """You are analyzing a refund/credit/billing policy document to prepare it for rule extraction.

Segment the following policy text into logical sections. Use these segment types where applicable: eligibility, thresholds, approvals, exceptions, refund_methods, audit_requirements. If a section doesn't fit any of these, use "other".

For each segment, include the segment_type and the exact text of that section (do not paraphrase or summarize).

Policy text:
---
{policy_text}
---
"""


class Segment(BaseModel):
    segment_type: str
    text: str


class SegmentationResult(BaseModel):
    segments: list[Segment]


def segment_policy(
    llm_client: LLMClient, policy_text: str, model: str = config.DEFAULT_MODEL
) -> list[Segment]:
    prompt = SEGMENTATION_PROMPT_V1.format(policy_text=policy_text)
    response = llm_client.generate_structured(
        prompt=prompt,
        schema=SegmentationResult,
        model=model,
        prompt_version="segmentation_v1",
    )
    return response.data.segments
```

- [ ] **Step 6: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_segmentation.py -v
```

Expected: PASS (1 test).

- [ ] **Step 7: Commit**

```bash
git add packages/core/tests/fakes.py packages/core/src/skiljo_core/extraction packages/core/tests/test_segmentation.py
git commit -m "feat(core): extraction pass 1 — policy segmentation"
```

---

### Task 5: Extraction pass 2 — rule extraction per segment

**Files:**
- Create: `packages/core/src/skiljo_core/extraction/rules.py`
- Test: `packages/core/tests/test_rules.py`

**Interfaces:**
- Consumes: `skiljo_core.extraction.segmentation.Segment`; `skiljo_core.schemas.rule_schema.DeterministicRule`, `Condition`, `Predicate`, `Operator`.
- Produces: `skiljo_core.extraction.rules.CandidateRuleList` (`rules: list[DeterministicRule]`), `extract_rules(llm_client: LLMClient, segment: Segment, model: str = config.DEFAULT_MODEL) -> list[DeterministicRule]`.

Candidate rules reuse `DeterministicRule`'s shape (`condition` + `action`) as a structural container — zone assignment happens in Task 6, not here.

- [ ] **Step 1: Write the failing test — `packages/core/tests/test_rules.py`**

```python
from fakes import FakeLLMClient

from skiljo_core.extraction.rules import CandidateRuleList, extract_rules
from skiljo_core.extraction.segmentation import Segment
from skiljo_core.schemas.rule_schema import Condition, DeterministicRule, Operator, Predicate


def test_extract_rules_returns_expected_condition_structure() -> None:
    fake_client = FakeLLMClient(
        [
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(
                            all=[
                                Predicate(field="refund_amount", op=Operator.lt, value=100),
                                Predicate(field="purchase_days_ago", op=Operator.lte, value=30),
                            ]
                        ),
                        action="approve_refund",
                    )
                ]
            )
        ]
    )
    segment = Segment(
        segment_type="thresholds",
        text="Refunds under $100 within 30 days of purchase are automatically approved.",
    )

    rules = extract_rules(fake_client, segment)

    assert len(rules) == 1
    condition = rules[0].condition
    assert condition.all[0].root.field == "refund_amount"
    assert condition.all[0].root.op == Operator.lt
    assert condition.all[1].root.field == "purchase_days_ago"
    assert rules[0].action == "approve_refund"
    assert fake_client.calls[0]["prompt_version"] == "rule_extraction_v1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_rules.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skiljo_core.extraction.rules'`.

- [ ] **Step 3: Create `packages/core/src/skiljo_core/extraction/rules.py`**

```python
from pydantic import BaseModel

from skiljo_core import config
from skiljo_core.extraction.segmentation import Segment
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.rule_schema import DeterministicRule

RULE_EXTRACTION_PROMPT_V1 = """You are extracting structured rules from a "{segment_type}" section of a refund/credit/billing policy.

For each distinct rule you find, produce:
- a condition using the predicate language: "all"/"any" composition of {{field, op, value}} predicates, where op is one of eq, neq, lt, lte, gt, gte, in, not_in, contains, empty, not_empty
- an action describing what happens when the condition is met

Segment text:
---
{segment_text}
---
"""


class CandidateRuleList(BaseModel):
    rules: list[DeterministicRule]


def extract_rules(
    llm_client: LLMClient, segment: Segment, model: str = config.DEFAULT_MODEL
) -> list[DeterministicRule]:
    prompt = RULE_EXTRACTION_PROMPT_V1.format(segment_type=segment.segment_type, segment_text=segment.text)
    response = llm_client.generate_structured(
        prompt=prompt,
        schema=CandidateRuleList,
        model=model,
        prompt_version="rule_extraction_v1",
    )
    return response.data.rules
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_rules.py -v
```

Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/skiljo_core/extraction/rules.py packages/core/tests/test_rules.py
git commit -m "feat(core): extraction pass 2 — rule extraction per segment"
```

---

### Task 6: Extraction pass 3 — decision zone classification

**Files:**
- Create: `packages/core/src/skiljo_core/extraction/zones.py`
- Test: `packages/core/tests/test_zones.py`

**Interfaces:**
- Consumes: `skiljo_core.schemas.rule_schema.DeterministicRule`; `skiljo_core.schemas.skill_schema.DecisionZones`.
- Produces: `skiljo_core.extraction.zones.ZoneClassification` (`zone: Literal["deterministic", "llm_assisted", "human_only"]`), `classify_zone(llm_client, rule: DeterministicRule, model=config.DEFAULT_MODEL) -> str`, `classify_rules(llm_client, rules: list[DeterministicRule], model=config.DEFAULT_MODEL) -> DecisionZones`.

`classify_rules` calls `classify_zone` once per rule (matching the design doc's per-rule classification framing) and buckets each into the matching `DecisionZones` list, constructing `LLMAssistedRule`/`HumanOnlyRule` from the candidate's `condition`/`action` as needed.

- [ ] **Step 1: Write the failing test — `packages/core/tests/test_zones.py`**

```python
from fakes import FakeLLMClient

from skiljo_core.extraction.zones import ZoneClassification, classify_rules, classify_zone
from skiljo_core.schemas.rule_schema import Condition, DeterministicRule, Operator, Predicate


def _rule(action: str) -> DeterministicRule:
    return DeterministicRule(
        condition=Condition(all=[Predicate(field="refund_amount", op=Operator.lt, value=100)]),
        action=action,
    )


def test_classify_zone_returns_fake_response_zone() -> None:
    fake_client = FakeLLMClient([ZoneClassification(zone="deterministic")])

    zone = classify_zone(fake_client, _rule("approve_refund"))

    assert zone == "deterministic"
    assert fake_client.calls[0]["prompt_version"] == "zone_classification_v1"


def test_classify_rules_buckets_into_decision_zones() -> None:
    fake_client = FakeLLMClient(
        [
            ZoneClassification(zone="deterministic"),
            ZoneClassification(zone="llm_assisted"),
            ZoneClassification(zone="human_only"),
        ]
    )
    rules = [_rule("approve_refund"), _rule("goodwill_exception"), _rule("escalate_fraud_dispute")]

    decision_zones = classify_rules(fake_client, rules)

    assert len(decision_zones.deterministic) == 1
    assert decision_zones.deterministic[0].action == "approve_refund"
    assert len(decision_zones.llm_assisted) == 1
    assert decision_zones.llm_assisted[0].action == "goodwill_exception"
    assert decision_zones.llm_assisted[0].requires_human_approval is True
    assert len(decision_zones.human_only) == 1
    assert decision_zones.human_only[0].action == "escalate_fraud_dispute"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_zones.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skiljo_core.extraction.zones'`.

- [ ] **Step 3: Create `packages/core/src/skiljo_core/extraction/zones.py`**

```python
from typing import Literal

from pydantic import BaseModel

from skiljo_core import config
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.rule_schema import DeterministicRule, HumanOnlyRule, LLMAssistedRule
from skiljo_core.schemas.skill_schema import DecisionZones

ZONE_CLASSIFICATION_PROMPT_V1 = """Classify the following policy rule into exactly one decision zone:

- deterministic: mechanically evaluable from structured ticket data alone (numeric thresholds, exact matches, simple boolean conditions).
- llm_assisted: requires interpreting ambiguous or subjective criteria (e.g. "goodwill", "reasonable", "anomalous use") before a decision can be made, but is not so high-stakes that it requires a human to decide.
- human_only: too high-stakes, legally sensitive, or judgment-heavy to automate even with LLM assistance (e.g. fraud disputes, legal threats, large dollar amounts).

Rule condition: {condition_json}
Rule action: {action}
"""


class ZoneClassification(BaseModel):
    zone: Literal["deterministic", "llm_assisted", "human_only"]


def classify_zone(
    llm_client: LLMClient, rule: DeterministicRule, model: str = config.DEFAULT_MODEL
) -> str:
    prompt = ZONE_CLASSIFICATION_PROMPT_V1.format(
        condition_json=rule.condition.model_dump_json(),
        action=rule.action,
    )
    response = llm_client.generate_structured(
        prompt=prompt,
        schema=ZoneClassification,
        model=model,
        prompt_version="zone_classification_v1",
    )
    return response.data.zone


def classify_rules(
    llm_client: LLMClient, rules: list[DeterministicRule], model: str = config.DEFAULT_MODEL
) -> DecisionZones:
    deterministic: list[DeterministicRule] = []
    llm_assisted: list[LLMAssistedRule] = []
    human_only: list[HumanOnlyRule] = []
    for rule in rules:
        zone = classify_zone(llm_client, rule, model=model)
        if zone == "deterministic":
            deterministic.append(rule)
        elif zone == "llm_assisted":
            llm_assisted.append(
                LLMAssistedRule(condition=rule.condition, action=rule.action, requires_human_approval=True)
            )
        else:
            human_only.append(HumanOnlyRule(condition=rule.condition, action=rule.action))
    return DecisionZones(deterministic=deterministic, llm_assisted=llm_assisted, human_only=human_only)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_zones.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/skiljo_core/extraction/zones.py packages/core/tests/test_zones.py
git commit -m "feat(core): extraction pass 3 — decision zone classification"
```

---

### Task 7: Extraction pass 4 — assembly, schema validation, and pipeline orchestration

**Files:**
- Create: `packages/core/src/skiljo_core/extraction/assembly.py`
- Create: `packages/core/src/skiljo_core/extraction/pipeline.py`
- Test: `packages/core/tests/test_assembly.py`
- Test: `packages/core/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `DecisionZones`, `Skill`, `Input` (skill_schema); `Condition`, `Predicate` (rule_schema); `segment_policy`, `extract_rules`, `classify_rules` (Tasks 4–6).
- Produces: `assemble_skill(llm_client, skill_name: str, trigger: str, decision_zones: DecisionZones, model=config.DEFAULT_MODEL) -> Skill`.
- Produces: `run_extraction_pipeline(llm_client, policy_text: str, skill_name: str, trigger: str, model=config.DEFAULT_MODEL) -> Skill` — the function Task 8's API endpoint calls.

**Design note (deviation from a literal reading of the design doc):** the "repair loop" is NOT a separate retry counter in `assembly.py`. Assembly builds a deterministic candidate dict (skill_name/trigger from the caller, inputs guessed from the fields referenced in `decision_zones`'s conditions). If `Skill.model_validate(candidate)` fails, exactly one call is made to `generate_structured(schema=Skill, ...)`, which already retries up to 3 times internally with validation feedback (Task 2's mechanism) — reusing it instead of reimplementing a second retry loop.

- [ ] **Step 1: Write the failing test — `packages/core/tests/test_assembly.py`**

```python
from fakes import FakeLLMClient

from skiljo_core.extraction.assembly import assemble_skill
from skiljo_core.schemas.rule_schema import Condition, DeterministicRule, Operator, Predicate
from skiljo_core.schemas.skill_schema import DecisionZones, Skill


def _decision_zones() -> DecisionZones:
    rule = DeterministicRule(
        condition=Condition(
            all=[
                Predicate(field="refund_amount", op=Operator.lt, value=100),
                Predicate(field="purchase_days_ago", op=Operator.lte, value=30),
            ]
        ),
        action="approve_refund",
    )
    return DecisionZones(deterministic=[rule], llm_assisted=[], human_only=[])


def test_assemble_skill_succeeds_without_llm_call_when_valid() -> None:
    fake_client = FakeLLMClient([])  # no LLM call expected on the happy path

    skill = assemble_skill(
        fake_client,
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
        decision_zones=_decision_zones(),
    )

    assert skill.skill_name == "process_refund_request"
    by_name = {i.name: i.type.value for i in skill.inputs}
    assert by_name == {"refund_amount": "number", "purchase_days_ago": "integer"}
    assert len(fake_client.calls) == 0


def test_assemble_skill_repairs_invalid_skill_name_via_llm() -> None:
    repaired = Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[{"name": "refund_amount", "type": "number"}],
        decision_zones=_decision_zones(),
    )
    fake_client = FakeLLMClient([repaired])

    skill = assemble_skill(
        fake_client,
        skill_name="ProcessRefundRequest",  # invalid: uppercase violates skill_name's pattern
        trigger="customer_requests_refund",
        decision_zones=_decision_zones(),
    )

    assert skill.skill_name == "process_refund_request"
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["prompt_version"] == "assembly_repair_v1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_assembly.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skiljo_core.extraction.assembly'`.

- [ ] **Step 3: Create `packages/core/src/skiljo_core/extraction/assembly.py`**

```python
from typing import Any

from pydantic import ValidationError

from skiljo_core import config
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.rule_schema import Condition, Predicate
from skiljo_core.schemas.skill_schema import DecisionZones, Skill


def _collect_condition_fields(condition: Condition) -> list[str]:
    fields: list[str] = []
    for clause_list in (condition.all, condition.any):
        if clause_list is None:
            continue
        for item in clause_list:
            inner = item.root
            if isinstance(inner, Predicate):
                fields.append(inner.field)
            else:
                fields.extend(_collect_condition_fields(inner))
    return fields


def _collect_fields(decision_zones: DecisionZones) -> list[str]:
    fields: list[str] = []
    for rule in (*decision_zones.deterministic, *decision_zones.llm_assisted, *decision_zones.human_only):
        fields.extend(_collect_condition_fields(rule.condition))
    return sorted(set(fields))


def _guess_input_type(field_name: str) -> str:
    lowered = field_name.lower()
    if any(token in lowered for token in ("amount", "price", "fee", "rate", "percent")):
        return "number"
    if any(token in lowered for token in ("days", "count", "version", "tokens")):
        return "integer"
    if any(token in lowered for token in ("flags", "tags", "items")):
        return "array"
    return "string"


def _build_inputs(fields: list[str]) -> list[dict[str, str]]:
    return [{"name": field, "type": _guess_input_type(field)} for field in fields]


def assemble_skill(
    llm_client: LLMClient,
    skill_name: str,
    trigger: str,
    decision_zones: DecisionZones,
    model: str = config.DEFAULT_MODEL,
) -> Skill:
    fields = _collect_fields(decision_zones)
    candidate: dict[str, Any] = {
        "skill_name": skill_name,
        "version": 1,
        "trigger": trigger,
        "inputs": _build_inputs(fields),
        "decision_zones": decision_zones.model_dump(mode="json"),
    }
    try:
        return Skill.model_validate(candidate)
    except ValidationError as exc:
        repair_prompt = (
            "The following draft Skill spec failed JSON Schema validation.\n\n"
            f"Draft:\n{candidate}\n\n"
            f"Validation error:\n{exc}\n\n"
            "Return a corrected Skill spec that fixes this specific violation without changing anything else."
        )
        response = llm_client.generate_structured(
            prompt=repair_prompt,
            schema=Skill,
            model=model,
            prompt_version="assembly_repair_v1",
        )
        return response.data
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_assembly.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 5: Write the failing test — `packages/core/tests/test_pipeline.py`**

```python
from fakes import FakeLLMClient

from skiljo_core.extraction.pipeline import run_extraction_pipeline
from skiljo_core.extraction.rules import CandidateRuleList
from skiljo_core.extraction.segmentation import Segment, SegmentationResult
from skiljo_core.extraction.zones import ZoneClassification
from skiljo_core.schemas.rule_schema import Condition, DeterministicRule, Operator, Predicate


def test_pipeline_runs_all_four_passes_and_produces_schema_valid_skill() -> None:
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[
                    Segment(segment_type="thresholds", text="Refunds under $100 within 30 days are approved.")
                ]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[Predicate(field="refund_amount", op=Operator.lt, value=100)]),
                        action="approve_refund",
                    )
                ]
            ),
            ZoneClassification(zone="deterministic"),
        ]
    )

    skill = run_extraction_pipeline(
        fake_client,
        policy_text="Refunds under $100 within 30 days are approved.",
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
    )

    assert skill.skill_name == "process_refund_request"
    assert len(skill.decision_zones.deterministic) == 1
    assert len(fake_client.calls) == 3  # segmentation, rule extraction, zone classification; assembly needs none
```

- [ ] **Step 6: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_pipeline.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skiljo_core.extraction.pipeline'`.

- [ ] **Step 7: Create `packages/core/src/skiljo_core/extraction/pipeline.py`**

```python
from skiljo_core import config
from skiljo_core.extraction.assembly import assemble_skill
from skiljo_core.extraction.rules import extract_rules
from skiljo_core.extraction.segmentation import segment_policy
from skiljo_core.extraction.zones import classify_rules
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.rule_schema import DeterministicRule
from skiljo_core.schemas.skill_schema import Skill


def run_extraction_pipeline(
    llm_client: LLMClient,
    policy_text: str,
    skill_name: str,
    trigger: str,
    model: str = config.DEFAULT_MODEL,
) -> Skill:
    segments = segment_policy(llm_client, policy_text, model=model)
    candidate_rules: list[DeterministicRule] = []
    for segment in segments:
        candidate_rules.extend(extract_rules(llm_client, segment, model=model))
    decision_zones = classify_rules(llm_client, candidate_rules, model=model)
    return assemble_skill(
        llm_client,
        skill_name=skill_name,
        trigger=trigger,
        decision_zones=decision_zones,
        model=model,
    )
```

- [ ] **Step 8: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_pipeline.py -v
```

Expected: PASS (1 test).

- [ ] **Step 9: Commit**

```bash
git add packages/core/src/skiljo_core/extraction/assembly.py packages/core/src/skiljo_core/extraction/pipeline.py packages/core/tests/test_assembly.py packages/core/tests/test_pipeline.py
git commit -m "feat(core): extraction pass 4 — assembly and schema validation"
```

---

### Task 8: POST /skills/extract endpoint with background job

**Files:**
- Create: `packages/api/src/skiljo_api/dependencies.py`
- Create: `packages/api/src/skiljo_api/routers/__init__.py`
- Create: `packages/api/src/skiljo_api/routers/skills.py`
- Modify: `packages/api/src/skiljo_api/main.py`
- Test: `packages/api/tests/test_skills_extract.py`

**Interfaces:**
- Consumes: `skiljo_core.extraction.pipeline.run_extraction_pipeline`; `skiljo_core.db.session.SessionLocal`; `skiljo_core.db.models.{Job, Policy, Skill, SkillVersion}`.
- Produces: `skiljo_api.dependencies.get_llm_client() -> LLMClient` (FastAPI dependency, overridable in tests via `app.dependency_overrides`).
- Produces: `POST /skills/extract` — request `{policy_text: str, skill_name: str, trigger: str}`, response 202 `{job_id: UUID, status: "pending"}`. On completion (synchronous within `BackgroundTasks`), creates a `Policy` row, a `Skill` row, a `SkillVersion` row (`status="draft"`), and updates the `Job` row to `status="completed"` with `result_ref` = the new `SkillVersion.id`.

This task's test needs Postgres running (same as Task 3).

- [ ] **Step 1: Create `packages/api/src/skiljo_api/dependencies.py`**

```python
from skiljo_core.llm.anthropic_client import AnthropicClient
from skiljo_core.llm.base import LLMClient

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = AnthropicClient()
    return _client
```

- [ ] **Step 2: Create `packages/api/src/skiljo_api/routers/__init__.py`** (empty file)

- [ ] **Step 3: Write the failing test — `packages/api/tests/test_skills_extract.py`**

```python
import uuid

from fastapi.testclient import TestClient

from fakes import FakeLLMClient

from skiljo_api.dependencies import get_llm_client
from skiljo_api.main import app
from skiljo_core.db.models import Job, Policy, Skill, SkillVersion
from skiljo_core.db.session import SessionLocal
from skiljo_core.extraction.rules import CandidateRuleList
from skiljo_core.extraction.segmentation import Segment, SegmentationResult
from skiljo_core.extraction.zones import ZoneClassification
from skiljo_core.schemas.rule_schema import Condition, DeterministicRule, Operator, Predicate


def _clean_tables() -> None:
    with SessionLocal() as session:
        session.query(SkillVersion).delete()
        session.query(Skill).delete()
        session.query(Job).delete()
        session.query(Policy).delete()
        session.commit()


def test_extract_endpoint_creates_draft_skill_version() -> None:
    _clean_tables()
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[
                    Segment(segment_type="thresholds", text="Refunds under $100 within 30 days are approved.")
                ]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[Predicate(field="refund_amount", op=Operator.lt, value=100)]),
                        action="approve_refund",
                    )
                ]
            ),
            ZoneClassification(zone="deterministic"),
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: fake_client
    try:
        client = TestClient(app)
        response = client.post(
            "/skills/extract",
            json={
                "policy_text": "Refunds under $100 within 30 days are approved.",
                "skill_name": "process_refund_request",
                "trigger": "customer_requests_refund",
            },
        )
        assert response.status_code == 202
        job_id = uuid.UUID(response.json()["job_id"])

        with SessionLocal() as session:
            job = session.get(Job, job_id)
            assert job.status == "completed"
            version = session.get(SkillVersion, job.result_ref)
            assert version is not None
            assert version.status == "draft"
            assert version.spec["skill_name"] == "process_refund_request"
            assert len(version.spec["decision_zones"]["deterministic"]) == 1
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 4: Run test to verify it fails**

```bash
uv run pytest packages/api/tests/test_skills_extract.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skiljo_api.routers.skills'` (or a 404, since the route doesn't exist yet). The `fakes` import resolves from `packages/core/tests/fakes.py` only if that directory is on `sys.path` — since `packages/api/tests/` is a **different** directory, this import will actually fail with `ModuleNotFoundError: No module named 'fakes'` first. Fix this before continuing: copy the fixture.

- [ ] **Step 4b: Make `FakeLLMClient` available to `packages/api/tests/`**

`packages/api/tests/` is a separate pytest rootdir from `packages/core/tests/`, so it needs its own copy of the fixture (matching the project's existing flat, no-`__init__.py` test layout — duplicating one small fixture file is simpler than introducing cross-package test imports).

```bash
cp packages/core/tests/fakes.py packages/api/tests/fakes.py
```

- [ ] **Step 5: Re-run test to verify it now fails for the right reason**

```bash
uv run pytest packages/api/tests/test_skills_extract.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skiljo_api.routers.skills'`.

- [ ] **Step 6: Create `packages/api/src/skiljo_api/routers/skills.py`**

```python
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel

from skiljo_api.dependencies import get_llm_client
from skiljo_core.db.models import Job, Policy, Skill, SkillVersion
from skiljo_core.db.session import SessionLocal
from skiljo_core.extraction.pipeline import run_extraction_pipeline
from skiljo_core.llm.base import LLMClient

router = APIRouter()


class ExtractRequest(BaseModel):
    policy_text: str
    skill_name: str
    trigger: str


class ExtractResponse(BaseModel):
    job_id: uuid.UUID
    status: str


def _run_extraction_job(
    job_id: uuid.UUID, policy_id: uuid.UUID, skill_name: str, trigger: str, llm_client: LLMClient
) -> None:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        job.status = "running"
        job.started_at = datetime.now(UTC)
        session.commit()

        try:
            policy = session.get(Policy, policy_id)
            skill_spec = run_extraction_pipeline(
                llm_client, policy_text=policy.raw_text, skill_name=skill_name, trigger=trigger
            )
            skill_row = Skill(name=skill_name)
            session.add(skill_row)
            session.flush()
            version_row = SkillVersion(
                skill_id=skill_row.id,
                version_number=1,
                spec=skill_spec.model_dump(mode="json"),
                source_policy_id=policy_id,
                status="draft",
            )
            session.add(version_row)
            session.flush()

            job.status = "completed"
            job.result_ref = version_row.id
            job.completed_at = datetime.now(UTC)
            session.commit()
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = datetime.now(UTC)
            session.commit()


@router.post("/skills/extract", status_code=202)
def extract_skill(
    request: ExtractRequest,
    background_tasks: BackgroundTasks,
    llm_client: LLMClient = Depends(get_llm_client),
) -> ExtractResponse:
    with SessionLocal() as session:
        policy = Policy(raw_text=request.policy_text)
        session.add(policy)
        session.flush()

        job = Job(
            kind="extraction",
            status="pending",
            payload={
                "policy_id": str(policy.id),
                "skill_name": request.skill_name,
                "trigger": request.trigger,
            },
        )
        session.add(job)
        session.commit()

        job_id = job.id
        policy_id = policy.id

    background_tasks.add_task(_run_extraction_job, job_id, policy_id, request.skill_name, request.trigger, llm_client)
    return ExtractResponse(job_id=job_id, status="pending")
```

- [ ] **Step 7: Mount the router in `packages/api/src/skiljo_api/main.py`**

Replace the full file contents:

```python
from fastapi import FastAPI

from skiljo_api.routers import skills

app = FastAPI(title="Skiljo API")
app.include_router(skills.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 8: Run test to verify it passes**

```bash
uv run pytest packages/api/tests/test_skills_extract.py packages/api/tests/test_health.py -v
```

Expected: PASS (2 tests) — confirms the existing `/health` test still works alongside the new router.

- [ ] **Step 9: Commit**

```bash
git add packages/api/src/skiljo_api packages/api/tests/test_skills_extract.py packages/api/tests/fakes.py
git commit -m "feat(api): POST /skills/extract endpoint with background job"
```

---

### Task 9: GET /jobs/{id} polling endpoint

**Files:**
- Create: `packages/api/src/skiljo_api/routers/jobs.py`
- Modify: `packages/api/src/skiljo_api/main.py`
- Test: `packages/api/tests/test_jobs.py`

**Interfaces:**
- Consumes: `skiljo_core.db.models.Job`; `skiljo_core.db.session.SessionLocal`.
- Produces: `GET /jobs/{job_id}` — response `{job_id: UUID, status: str, result_ref: UUID | None, error: str | None}`; 404 if the job doesn't exist.

- [ ] **Step 1: Write the failing test — `packages/api/tests/test_jobs.py`**

```python
import uuid

from fastapi.testclient import TestClient

from skiljo_api.main import app
from skiljo_core.db.models import Job
from skiljo_core.db.session import SessionLocal


def _clean_jobs() -> None:
    with SessionLocal() as session:
        session.query(Job).delete()
        session.commit()


def test_get_job_returns_status_and_result_ref() -> None:
    _clean_jobs()
    result_ref = uuid.uuid4()
    with SessionLocal() as session:
        job = Job(kind="extraction", status="completed", result_ref=result_ref)
        session.add(job)
        session.commit()
        job_id = job.id

    client = TestClient(app)
    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == str(job_id)
    assert body["status"] == "completed"
    assert body["result_ref"] == str(result_ref)
    assert body["error"] is None


def test_get_job_404_for_unknown_id() -> None:
    client = TestClient(app)
    response = client.get(f"/jobs/{uuid.uuid4()}")
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/api/tests/test_jobs.py -v
```

Expected: FAIL — 404 for both tests (no `/jobs/{id}` route registered yet, so the first test's 200 assertion fails).

- [ ] **Step 3: Create `packages/api/src/skiljo_api/routers/jobs.py`**

```python
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from skiljo_core.db.models import Job
from skiljo_core.db.session import SessionLocal

router = APIRouter()


class JobResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    result_ref: uuid.UUID | None = None
    error: str | None = None


@router.get("/jobs/{job_id}")
def get_job(job_id: uuid.UUID) -> JobResponse:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JobResponse(job_id=job.id, status=job.status, result_ref=job.result_ref, error=job.error)
```

- [ ] **Step 4: Mount the router in `packages/api/src/skiljo_api/main.py`**

```python
from fastapi import FastAPI

from skiljo_api.routers import jobs, skills

app = FastAPI(title="Skiljo API")
app.include_router(skills.router)
app.include_router(jobs.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest packages/api/tests/test_jobs.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/skiljo_api/routers/jobs.py packages/api/src/skiljo_api/main.py packages/api/tests/test_jobs.py
git commit -m "feat(api): GET /jobs/{id} polling endpoint"
```

---

### Task 10: GET /skills, /skills/{id}, /skills/{id}/versions endpoints

**Files:**
- Modify: `packages/api/src/skiljo_api/routers/skills.py`
- Test: `packages/api/tests/test_skills_read.py`

**Interfaces:**
- Produces: `GET /skills -> list[SkillSummary]`, `GET /skills/{id} -> SkillSummary` (404 if missing), `GET /skills/{id}/versions -> list[SkillVersionSummary]`.
- `SkillSummary`: `{id: UUID, name: str, current_version_id: UUID | None}`.
- `SkillVersionSummary`: `{id: UUID, version_number: int, status: str, spec: dict}`.

- [ ] **Step 1: Write the failing test — `packages/api/tests/test_skills_read.py`**

```python
import uuid

from fastapi.testclient import TestClient

from skiljo_api.main import app
from skiljo_core.db.models import Skill, SkillVersion
from skiljo_core.db.session import SessionLocal


def _clean_tables() -> None:
    with SessionLocal() as session:
        session.query(SkillVersion).delete()
        session.query(Skill).delete()
        session.commit()


def _seed_skill_with_version() -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as session:
        skill = Skill(name="process_refund_request")
        session.add(skill)
        session.flush()
        version = SkillVersion(
            skill_id=skill.id,
            version_number=1,
            spec={"skill_name": "process_refund_request"},
            status="draft",
        )
        session.add(version)
        session.commit()
        return skill.id, version.id


def test_list_skills_includes_seeded_skill() -> None:
    _clean_tables()
    skill_id, _ = _seed_skill_with_version()

    client = TestClient(app)
    response = client.get("/skills")

    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert str(skill_id) in ids


def test_get_skill_returns_detail() -> None:
    _clean_tables()
    skill_id, _ = _seed_skill_with_version()

    client = TestClient(app)
    response = client.get(f"/skills/{skill_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "process_refund_request"


def test_get_skill_404_for_unknown_id() -> None:
    client = TestClient(app)
    response = client.get(f"/skills/{uuid.uuid4()}")
    assert response.status_code == 404


def test_list_skill_versions_includes_seeded_version() -> None:
    _clean_tables()
    skill_id, version_id = _seed_skill_with_version()

    client = TestClient(app)
    response = client.get(f"/skills/{skill_id}/versions")

    assert response.status_code == 200
    versions = response.json()
    assert len(versions) == 1
    assert versions[0]["id"] == str(version_id)
    assert versions[0]["status"] == "draft"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/api/tests/test_skills_read.py -v
```

Expected: FAIL — 404 for all routes (not registered yet).

- [ ] **Step 3: Append read endpoints to `packages/api/src/skiljo_api/routers/skills.py`**

Change the existing `from fastapi import APIRouter, BackgroundTasks, Depends` line to:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
```

And add this import alongside the existing `from skiljo_core.db.models import ...` line:

```python
from skiljo_core.db.models import Job, Policy, Skill, SkillVersion
```

Append to the end of the file:

```python
class SkillSummary(BaseModel):
    id: uuid.UUID
    name: str
    current_version_id: uuid.UUID | None


class SkillVersionSummary(BaseModel):
    id: uuid.UUID
    version_number: int
    status: str
    spec: dict


@router.get("/skills")
def list_skills() -> list[SkillSummary]:
    with SessionLocal() as session:
        rows = session.query(Skill).all()
        return [SkillSummary(id=r.id, name=r.name, current_version_id=r.current_version_id) for r in rows]


@router.get("/skills/{skill_id}")
def get_skill(skill_id: uuid.UUID) -> SkillSummary:
    with SessionLocal() as session:
        skill = session.get(Skill, skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail="skill not found")
        return SkillSummary(id=skill.id, name=skill.name, current_version_id=skill.current_version_id)


@router.get("/skills/{skill_id}/versions")
def list_skill_versions(skill_id: uuid.UUID) -> list[SkillVersionSummary]:
    with SessionLocal() as session:
        rows = session.query(SkillVersion).filter(SkillVersion.skill_id == skill_id).all()
        return [
            SkillVersionSummary(id=r.id, version_number=r.version_number, status=r.status, spec=r.spec)
            for r in rows
        ]
```

**Note:** FastAPI resolves routes in registration order with exact-then-pattern matching; `/skills/{skill_id}` and `/skills/{skill_id}/versions` don't collide with the existing `/skills/extract` POST route since they're different HTTP methods and `/skills/extract` is a fixed path checked as a literal segment before the `{skill_id}` patterns — no reordering needed.

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/api/tests/test_skills_read.py -v
```

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/skiljo_api/routers/skills.py packages/api/tests/test_skills_read.py
git commit -m "feat(api): GET /skills, /skills/{id}, /skills/{id}/versions endpoints"
```

---

### Task 11: 20 hand-labeled policy-to-skill examples

**Files:**
- Create: `data/eval/train/<NN>_<slug>.policy.txt` × 20
- Create: `data/eval/train/<NN>_<slug>.skill.yaml` × 20
- Test: `packages/core/tests/test_eval_data.py`

**Format:** each example is a pair of files sharing a basename. `<NN>_<slug>.policy.txt` is the raw policy text (or the called-for excerpt) fetched from the corpus URL, verbatim. `<NN>_<slug>.skill.yaml` is the hand-written ground-truth `Skill` spec — a plain YAML document matching `schemas/skill.schema.json`'s structure exactly (same shape as the worked example in `docs/DESIGN_DOCUMENT.md` §4): `skill_name`, `version: 1`, `trigger`, `inputs`, `decision_zones: {deterministic, llm_assisted, human_only}`, each rule as `{condition: {all/any: [{field, op, value}, ...]}, action}` (`llm_assisted` rules also carry `requires_human_approval: true`).

**The 20 examples** (resolves `docs/POLICY_CORPUS.md`'s "How to use this corpus" guidance, which names 16 and reserves 4 of those for a later dev split, to the design doc's literal 20-in-`data/eval/train/` target — all 16 named examples go into `train/` for this initial pass since Week 2 doesn't introduce a separate dev split directory, plus 4 more drawn from currently-unused Tier 1/Tier 2 corpus entries):

| # | Corpus # | Company / policy | Source URL (from POLICY_CORPUS.md) | Notes |
|---|---|---|---|---|
| 01 | 11 | Notion — Refund policy | notion.com/help/refunds | Easy. Basic pass: 3-day/30-day windows. |
| 02 | 4 | Amazon S3 — SLA | aws.amazon.com/s3/sla/ | Easy. Single-tier credit SLA. |
| 03 | 5 | AWS Audit Manager — SLA | aws.amazon.com/audit-manager/sla/ | Easy. Smallest AWS SLA. |
| 04 | 2 | Stripe Docs — plan terms | docs.stripe.com/bundled-pricing/terms | Easy. Product-doc voice. |
| 05 | 6 | OpenAI — Service Credit Terms | openai.com/policies/service-credit-terms/ | Easy. Non-refundable + expiration. |
| 06 | 8 | Twilio — Terms of Service | twilio.com/en-us/legal/tos | Easy. Time-window + late-fee rules. |
| 07 | 13 | Shopify Plus — Plus Terms | shopify.com/plus/legal/terms | Easy. Enterprise non-refund language. |
| 08 | 10a | Vercel Pro — billing docs (excerpt) | vercel.com/docs/plans/pro-plan | Easy. Excerpt: just the included-allocation + overage clause. |
| 09 | 1 | Stripe — Subscription policy | stripe.com/legal/subscription-policy | Hard. Entitlements + overage + non-refund hedges. |
| 10 | 3 | Amazon EC2 — SLA | aws.amazon.com/compute/sla/ | Hard. Dual region/instance-level SLA. |
| 11 | 7 | OpenAI — Services Agreement | openai.com/policies/services-agreement/ | Hard. Event-triggered refund conditions. |
| 12 | 9 | Vercel — Terms of Service | vercel.com/legal/terms | Hard. Ambiguous "anomalous use" trigger — should classify `llm_assisted`, not deterministic. |
| 13 | 10b | Vercel Pro — billing docs (full) | vercel.com/docs/plans/pro-plan | Hard. Full hybrid billing model. |
| 14 | 11b | Notion — re-labeled with regional override | notion.com/help/refunds | Hard. Same source as #01, separate rule for EU/UK 14-day override. |
| 15 | 12-excerpt | Shopify — refund policy (excerpt) | help.shopify.com/.../refund-policy-subscriptions | Hard. **Excerpt only** — both the "no refunds" ToS line and the "case-by-case review" help-center line, to exercise contradiction detection later. Full document reserved for `data/eval/test/`. |
| 16 | 14-excerpt | Steam — refund policy (excerpt) | store.steampowered.com/steam_refunds/ | Hard. **Excerpt only** — base 14-day/2-hour rule plus the DLC exception. Full document reserved for `data/eval/test/`. |
| 17 | 18 | Square — Payment Terms | squareup.com/us/en/legal/general/payment-annotated | Additional. Refund limit + reserve withholding rules. |
| 18 | 19 | Atlassian — Refund policy | support.atlassian.com/.../request-a-refund/ | Additional. Window-based, split by cadence. |
| 19 | 20 | GitHub — ToS (payments section) | docs.github.com/.../github-terms-of-service | Additional. Absolute no-refund clause (human_only candidate). |
| 20 | 15 | Google Cloud — Compute Engine SLA | cloud.google.com/compute/sla | Additional. Cross-vendor sibling of EC2 (#10). |

- [ ] **Step 1: Fetch each source policy's real text**

For each row above, fetch the page at its source URL and save the relevant policy text (or the called-for excerpt, for rows 15 and 16) to `data/eval/train/<NN>_<slug>.policy.txt`. Use the company name lowercased with underscores as `<slug>` (e.g. `01_notion.policy.txt`, `08_vercel_pro_excerpt.policy.txt`).

- [ ] **Step 2: Worked example — `data/eval/train/01_notion.policy.txt`**

Save the fetched Notion refund policy text from notion.com/help/refunds to this file verbatim (representative shape, to be replaced with the actual fetched text during execution):

```
Notion Refund Policy

If you are on a monthly billing plan, you may request a refund within 3 days of your most recent payment.

If you are on an annual billing plan, you may request a refund within 30 days of your most recent payment.

If you are located in the European Union or United Kingdom, you are entitled to a refund within 14 days of your most recent payment, regardless of billing cadence, as required by applicable consumer protection law.

If a paid member was added to your workspace by mistake, contact support within 7 days of the charge for a full refund of that member's seat.

To request a refund, contact support@notion.so with your workspace name and the email associated with your billing.
```

- [ ] **Step 3: Worked example — `data/eval/train/01_notion.skill.yaml`**

```yaml
skill_name: process_notion_refund_request
version: 1
trigger: customer_requests_refund
inputs:
  - name: billing_cadence
    type: string
    description: "monthly or annual"
  - name: days_since_payment
    type: integer
  - name: customer_region
    type: string
    description: "ISO region code; EU/UK get a mandatory override window"
  - name: is_accidental_member_addition
    type: boolean
decision_zones:
  deterministic:
    - condition:
        any:
          - all:
              - field: customer_region
                op: in
                value: ["EU", "UK"]
              - field: days_since_payment
                op: lte
                value: 14
          - all:
              - field: billing_cadence
                op: eq
                value: monthly
              - field: days_since_payment
                op: lte
                value: 3
          - all:
              - field: billing_cadence
                op: eq
                value: annual
              - field: days_since_payment
                op: lte
                value: 30
      action: approve_refund
    - condition:
        all:
          - field: is_accidental_member_addition
            op: eq
            value: true
          - field: days_since_payment
            op: lte
            value: 7
      action: approve_seat_refund
  llm_assisted: []
  human_only: []
```

- [ ] **Step 4: Label the remaining 19 examples**

Repeat Steps 1–3's exact procedure for rows 02–20 in the table above: fetch the real text into `<NN>_<slug>.policy.txt`, then hand-write `<NN>_<slug>.skill.yaml` in the same structure — a `skill_name` (snake_case, matching `^[a-z_][a-z0-9_]*$`), a `trigger`, the `inputs` the rules reference, and `decision_zones` with each rule's `condition`/`action` (plus `requires_human_approval: true` for any `llm_assisted` rule). Use each row's "Notes" column and `docs/POLICY_CORPUS.md`'s per-policy "Extraction challenges" / "Good for testing" prose (already written there for every numbered entry) as the rubric for which rules matter most in that document. Row 12 (Vercel ambiguous "anomalous use" trigger) must produce an `llm_assisted` rule, not `deterministic` — this is the corpus doc's explicit test for zone-classification judgment, not an extraction-pipeline test, but the *ground truth* itself needs to reflect the correct zone.

- [ ] **Step 5: Write the validation test — `packages/core/tests/test_eval_data.py`**

```python
from pathlib import Path

import yaml

from skiljo_core.schemas.skill_schema import Skill

EVAL_TRAIN_DIR = Path(__file__).resolve().parents[3] / "data" / "eval" / "train"


def test_all_eval_examples_have_schema_valid_ground_truth() -> None:
    skill_files = sorted(EVAL_TRAIN_DIR.glob("*.skill.yaml"))
    assert len(skill_files) == 20, f"expected 20 examples, found {len(skill_files)}"

    for skill_file in skill_files:
        policy_file = skill_file.with_name(skill_file.name.replace(".skill.yaml", ".policy.txt"))
        assert policy_file.exists(), f"missing policy text for {skill_file.name}"
        assert policy_file.stat().st_size > 0, f"empty policy text for {skill_file.name}"

        with open(skill_file) as f:
            raw = yaml.safe_load(f)
        skill = Skill.model_validate(raw)
        assert skill.skill_name
```

- [ ] **Step 6: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_eval_data.py -v
```

Expected: PASS (1 test) — confirms all 20 pairs exist and every ground-truth spec validates against `skill.schema.json`.

- [ ] **Step 7: Add PyYAML as an explicit dependency**

It's already resolved transitively (via `datamodel-code-generator`), but add it explicitly to the root `pyproject.toml`'s dev dependency group since `test_eval_data.py` imports it directly:

```toml
dev = [
    "ruff>=0.6",
    "mypy>=1.11",
    "pytest>=8.3",
    "httpx>=0.27",
    "datamodel-code-generator>=0.26",
    "pyyaml>=6.0",
]
```

```bash
uv sync --all-packages
```

- [ ] **Step 8: Commit**

```bash
git add data/eval packages/core/tests/test_eval_data.py pyproject.toml uv.lock
git commit -m "data: 20 hand-labeled policy-to-skill examples"
```

---

### Task 12: Unit tests for extraction pipeline — close coverage gaps

**Files:**
- Modify: `packages/core/pyproject.toml` is not touched; add `pytest-cov` to root `pyproject.toml` dev group
- Modify: `packages/core/tests/test_assembly.py` (add 2 tests)
- Modify: `packages/core/tests/test_pipeline.py` (add 1 test)

**Interfaces:** none new — this task only adds tests against Tasks 4–7's existing functions to close three untested branches: nested `Condition` recursion in `_collect_fields`, the `"array"` branch of `_guess_input_type`, and the pipeline's multi-segment accumulation loop.

- [ ] **Step 1: Add `pytest-cov` to the root `pyproject.toml` dev group**

```toml
dev = [
    "ruff>=0.6",
    "mypy>=1.11",
    "pytest>=8.3",
    "pytest-cov>=5.0",
    "httpx>=0.27",
    "datamodel-code-generator>=0.26",
    "pyyaml>=6.0",
]
```

```bash
uv sync --all-packages
```

- [ ] **Step 2: Write the failing test — append to `packages/core/tests/test_assembly.py`**

```python
def test_assemble_skill_handles_nested_conditions_and_array_fields() -> None:
    from skiljo_core.schemas.rule_schema import Condition

    rule = DeterministicRule(
        condition=Condition(
            any=[
                Predicate(field="fraud_flags", op=Operator.not_empty, value=None),
                Condition(all=[Predicate(field="refund_amount", op=Operator.gt, value=1000)]),
            ]
        ),
        action="escalate_review",
    )
    decision_zones = DecisionZones(deterministic=[rule], llm_assisted=[], human_only=[])
    fake_client = FakeLLMClient([])

    skill = assemble_skill(
        fake_client,
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
        decision_zones=decision_zones,
    )

    by_name = {i.name: i.type.value for i in skill.inputs}
    assert by_name["fraud_flags"] == "array"
    assert by_name["refund_amount"] == "number"
```

- [ ] **Step 3: Run test to verify it fails or passes for the right reason**

```bash
uv run pytest packages/core/tests/test_assembly.py -v
```

Expected: this should already PASS given Task 7's implementation (both branches — nested `Condition` recursion and the `"array"` keyword match — were implemented in Task 7, just not exercised by a test until now). If it fails, the nested-condition recursion or the array-keyword matching in `_collect_condition_fields`/`_guess_input_type` has a bug — fix it before continuing, per `superpowers:systematic-debugging`.

- [ ] **Step 4: Write the failing test — append to `packages/core/tests/test_pipeline.py`**

```python
def test_pipeline_accumulates_rules_across_multiple_segments() -> None:
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[
                    Segment(segment_type="thresholds", text="Refunds under $100 within 30 days are approved."),
                    Segment(segment_type="exceptions", text="Goodwill exceptions may be granted by support leads."),
                ]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[Predicate(field="refund_amount", op=Operator.lt, value=100)]),
                        action="approve_refund",
                    )
                ]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[Predicate(field="goodwill_requested", op=Operator.eq, value=True)]),
                        action="goodwill_exception",
                    )
                ]
            ),
            ZoneClassification(zone="deterministic"),
            ZoneClassification(zone="llm_assisted"),
        ]
    )

    skill = run_extraction_pipeline(
        fake_client,
        policy_text="(full policy text)",
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
    )

    assert len(skill.decision_zones.deterministic) == 1
    assert len(skill.decision_zones.llm_assisted) == 1
    assert len(fake_client.calls) == 5
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_pipeline.py -v
```

Expected: PASS (2 tests).

- [ ] **Step 6: Run full coverage check on the extraction module**

```bash
uv run pytest --cov=skiljo_core.extraction --cov-report=term-missing packages/core/tests/
```

Expected: coverage for `skiljo_core/extraction/*` is above 70%. If any module falls short, identify the uncovered lines from the `term-missing` report and add one targeted test per gap (following the same pattern as Steps 2–5) before committing.

- [ ] **Step 7: Run the full test suite to confirm nothing regressed**

```bash
uv run pytest
```

Expected: all tests pass (Week 1's `test_health.py`/`test_models.py` plus all Week 2 tests added in Tasks 1–12).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock packages/core/tests/test_assembly.py packages/core/tests/test_pipeline.py
git commit -m "test(core): unit tests for extraction pipeline"
```

---

## Final verification (Week 2 complete)

- [ ] `uv run pytest` — full suite passes (Week 1 + Week 2 tests).
- [ ] `uv run ruff check .` and `uv run mypy packages/core/src packages/api/src packages/demo/src --exclude 'schemas/'` — both clean.
- [ ] `uv run pytest --cov=skiljo_core.extraction --cov-report=term-missing packages/core/tests/` — extraction module coverage >70%.
- [ ] `uv run pytest packages/core/tests/test_eval_data.py -v` — all 20 eval examples present and schema-valid.
- [ ] CI green on `main` (push and `gh run watch`).
- [ ] Cross-check against `docs/DESIGN_DOCUMENT.md` §12 "Week 2" commit list (14–25) — every commit's stated acceptance criterion is met (adjusted for mocking per this plan's testing strategy, as recorded in the spec).
