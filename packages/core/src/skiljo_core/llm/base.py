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
