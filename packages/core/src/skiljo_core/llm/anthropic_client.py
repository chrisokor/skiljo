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
            return StructuredResponse(data=data, attempts=attempt, llm_call_id=llm_call_id)
        assert last_error is not None
        raise last_error
