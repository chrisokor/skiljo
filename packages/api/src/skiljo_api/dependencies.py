from skiljo_core.llm.anthropic_client import AnthropicClient
from skiljo_core.llm.base import LLMClient

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = AnthropicClient()
    return _client
