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
