from types import SimpleNamespace
from unittest.mock import Mock

import pytest
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
        assert rows[0].cost_estimate_usd is not None
        assert float(rows[0].cost_estimate_usd) == round((7 * 3.00 + 3 * 15.00) / 1_000_000, 6)


def test_cache_hit_skips_api_call_and_logs_cached_true(
    tmp_path: pytest.fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cache hit: no API call, logged with cached=True, same structured output returned."""
    from pydantic import BaseModel
    from skiljo_core.llm.anthropic_client import AnthropicClient

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
