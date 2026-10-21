"""Process-local Azure PostgreSQL access-token reuse.

PostgreSQL connections remain short-lived in this slice. The credential and its
AAD access token are reused inside one worker process so every connect does not
repeat managed-identity discovery and token acquisition.
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any

from azure.identity import DefaultAzureCredential


class CachedAzurePostgresCredential:
    """Cache one Azure access token per scope until shortly before expiry."""

    def __init__(
        self,
        credential: Any | None = None,
        *,
        refresh_skew_seconds: int = 120,
    ) -> None:
        self._credential = credential or DefaultAzureCredential()
        self._refresh_skew_seconds = max(0, int(refresh_skew_seconds))
        self._tokens: dict[tuple[str, ...], Any] = {}
        self._lock = Lock()

    def _usable(self, token: Any | None) -> bool:
        if token is None:
            return False
        expires_on = int(getattr(token, "expires_on", 0) or 0)
        return expires_on - self._refresh_skew_seconds > int(time.time())

    def get_token(self, *scopes: str, **kwargs: Any) -> Any:
        """Mirror TokenCredential.get_token while caching ordinary scope reads."""
        if kwargs:
            return self._credential.get_token(*scopes, **kwargs)
        key = tuple(scopes)
        token = self._tokens.get(key)
        if self._usable(token):
            return token
        with self._lock:
            token = self._tokens.get(key)
            if self._usable(token):
                return token
            token = self._credential.get_token(*scopes)
            self._tokens[key] = token
            return token
