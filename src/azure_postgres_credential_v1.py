"""Azure PostgreSQL peer verification and process-local access-token reuse.

PostgreSQL connections remain short-lived in this slice. The credential and its
AAD access token are reused inside one worker process so every connect does not
repeat managed-identity discovery and token acquisition.
"""
from __future__ import annotations

import os
from pathlib import Path
import ssl
import time
from threading import Lock
from typing import Any

from azure.identity import DefaultAzureCredential


def azure_postgres_tls_options(*, sslrootcert: str | None = None) -> dict[str, str]:
    """Verify Azure's peer against an explicit root or the image's system bundle.

    An explicitly configured but unavailable root is an error, never a reason to
    fall back to another certificate or to encryption without peer verification.
    Connection owners retain their existing error handling and token lifecycle.
    """
    root = sslrootcert if sslrootcert is not None else os.environ.get("PGSSLROOTCERT")
    if not root:
        root = ssl.get_default_verify_paths().cafile
    try:
        if not root:
            raise ValueError("missing trust root")
        path = Path(root).expanduser()
        if not path.is_file():
            raise ValueError("trust root is not a file")
        with path.open("rb") as certificate:
            certificate.read(1)
    except (OSError, ValueError) as exc:
        raise ValueError("azure_postgres_trust_root_unavailable") from exc
    return {"sslmode": "verify-full", "sslrootcert": str(path)}


def postgres_dsn_tls_options(dsn: str) -> dict[str, str]:
    """Keep local DSNs intact; an Azure host anywhere in the list requires TLS.

    Parse libpq's URI and keyword forms rather than matching the raw string.
    Explicit host options take precedence over PGHOST, as in libpq itself.
    """
    from psycopg.conninfo import conninfo_to_dict

    options = conninfo_to_dict(dsn)
    hosts = options.get("host") or os.environ.get("PGHOST", "")
    azure = any(host.strip().lower().rstrip(".").endswith(".postgres.database.azure.com")
                for host in hosts.split(","))
    if not azure:
        return {}
    return azure_postgres_tls_options(sslrootcert=options.get("sslrootcert"))


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
