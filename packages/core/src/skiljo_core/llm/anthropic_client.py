from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

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
