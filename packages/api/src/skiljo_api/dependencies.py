from skiljo_core.db.session import SessionLocal
from skiljo_core.llm.anthropic_client import AnthropicClient
from skiljo_core.llm.base import LLMClient
from skiljo_core.llm.logging import LLMCallLogger

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = AnthropicClient(logger=LLMCallLogger(SessionLocal))
    return _client
