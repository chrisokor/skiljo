from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from skiljo_core import config
from skiljo_core.db.session import SessionLocal
from skiljo_core.llm.anthropic_client import AnthropicClient
from skiljo_core.llm.base import LLMClient
from skiljo_core.llm.cache import LLMCacheStore
from skiljo_core.llm.logging import LLMCallLogger

_bearer = HTTPBearer()

_client: LLMClient | None = None


def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(_bearer)) -> None:
    if not config.API_KEY:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="API_KEY not configured")
    if credentials.credentials != config.API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = AnthropicClient(
            logger=LLMCallLogger(SessionLocal),
            cache_store=LLMCacheStore(SessionLocal),
        )
    return _client
