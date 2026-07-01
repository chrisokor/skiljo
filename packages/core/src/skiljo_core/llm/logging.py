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
            # TODO(week3): compute cost_estimate_usd from usage.input_tokens + output_tokens × model rate
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
