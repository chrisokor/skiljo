from typing import Any, TypeVar, cast

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
        data = cast(T, self._responses.pop(0))
        return StructuredResponse(data=data, attempts=1)
