"""Fail-closed ingest payload size limits for the operations console.

ROADMAP wave 2 (beschikbaarheid). Upload and URL-download bytes are rejected
when they exceed a documented, env-overridable maximum. Defaults are safe
for first-wave HTML/PDF. PROTOCOL.md is not edited. publish() stays G2-BLOCKED.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from src.operations_console_v1 import ConsoleError, OperationsConsole, UrlFetcher, default_url_fetcher

DEFAULT_INGEST_MAX_BYTES = 32 * 1024 * 1024
ENV_INGEST_MAX_BYTES = "CONSOLE_INGEST_MAX_BYTES"
INGEST_PAYLOAD_TOO_LARGE = "ingest_payload_too_large"
_READ_CHUNK = 64 * 1024


def ingest_max_bytes() -> int:
    """Return the active max payload size. Invalid env values fall back to the safe default."""
    raw = os.environ.get(ENV_INGEST_MAX_BYTES, "").strip()
    if not raw:
        return DEFAULT_INGEST_MAX_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_INGEST_MAX_BYTES
    if value <= 0:
        return DEFAULT_INGEST_MAX_BYTES
    return value


def enforce_ingest_payload_size(size: int, *, limit: int | None = None) -> None:
    max_bytes = ingest_max_bytes() if limit is None else limit
    if size > max_bytes:
        raise ConsoleError(INGEST_PAYLOAD_TOO_LARGE)


async def read_upload_limited(upload) -> bytes:
    """Read an UploadFile in chunks and fail closed as soon as it exceeds the max."""
    limit = ingest_max_bytes()
    chunks: list[bytes] = []
    total = 0
    declared = getattr(upload, "size", None)
    if isinstance(declared, int) and declared > 0:
        enforce_ingest_payload_size(declared, limit=limit)
    while True:
        chunk = await upload.read(_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        enforce_ingest_payload_size(total, limit=limit)
        chunks.append(chunk)
    return b"".join(chunks)


def fetch_url_limited(url: str) -> tuple[bytes, str, str]:
    """GET ``url`` with Content-Length and streamed-body size checks. No SSRF changes."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ConsoleError("url_scheme_not_allowed")
    limit = ingest_max_bytes()
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "vvn-operations-console/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            declared = response.headers.get("Content-Length")
            if declared is not None and str(declared).strip():
                try:
                    enforce_ingest_payload_size(int(declared), limit=limit)
                except ValueError:
                    pass
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(_READ_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                enforce_ingest_payload_size(total, limit=limit)
                chunks.append(chunk)
            data = b"".join(chunks)
            content_type = str(response.headers.get("Content-Type") or "")
    except ConsoleError:
        raise
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise ConsoleError("url_snapshot_failed") from exc
    filename = Path(parsed.path).name or "snapshot.bin"
    return data, content_type, filename


def limited_url_fetcher(inner: UrlFetcher | None = None) -> UrlFetcher:
    """Wrap a fetcher so returned bytes still fail closed (custom test fetchers)."""
    if inner is None or inner is default_url_fetcher:
        return fetch_url_limited

    def wrapped(url: str) -> tuple[bytes, str, str]:
        data, content_type, filename = inner(url)
        enforce_ingest_payload_size(len(data))
        return data, content_type, filename

    return wrapped


def install_ingest_limits(console: OperationsConsole) -> None:
    """Bind fail-closed size limits onto an existing console instance."""
    console.url_fetcher = limited_url_fetcher(console.url_fetcher)
