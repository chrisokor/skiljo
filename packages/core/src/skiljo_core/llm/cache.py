import hashlib
from collections.abc import Callable

from sqlalchemy.orm import Session

from skiljo_core.db.models import LLMCache


class LLMCacheStore:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def compute_key(provider: str, model: str, prompt_version: str, prompt_text: str) -> str:
        raw = f"{provider}|{model}|{prompt_version}|{prompt_text}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> str | None:
        with self._session_factory() as session:
            row = session.get(LLMCache, key)
            return row.response_text if row is not None else None

    def set(self, key: str, response_text: str) -> None:
        with self._session_factory() as session:
            row = LLMCache(cache_key=key, response_text=response_text)
            session.merge(row)
            session.commit()
