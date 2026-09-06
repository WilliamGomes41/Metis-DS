"""Fail-closed ingest payload size limits and URL-destination guards.

ROADMAP wave 2 (beschikbaarheid): upload/URL-download bytes are rejected
when they exceed a documented, env-overridable maximum.

ROADMAP wave 3 (toegang): URL-ingest MUST NOT follow SSRF to internal
destinations; each redirect hop is re-validated. PROTOCOL.md is not
edited. publish() stays G2-BLOCKED.
"""
from __future__ import annotations

import ipaddress
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from src.operations_console_v1 import ConsoleError, OperationsConsole, UrlFetcher, default_url_fetcher

DEFAULT_INGEST_MAX_BYTES = 32 * 1024 * 1024
ENV_INGEST_MAX_BYTES = "CONSOLE_INGEST_MAX_BYTES"
INGEST_PAYLOAD_TOO_LARGE = "ingest_payload_too_large"
URL_DESTINATION_NOT_ALLOWED = "url_destination_not_allowed"
_READ_CHUNK = 64 * 1024
_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata",
        "metadata.google.internal",
        "metadata.azure.com",
    }
)
_BLOCKED_NETWORKS = (
    ipaddress.ip_network("100.64.0.0/10"),
)


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


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _ip_is_blocked(ip.ipv4_mapped)
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    return any(ip in network for network in _BLOCKED_NETWORKS)


def assert_url_destination_allowed(url: str) -> None:
    """Fail-closed: reject loopback, link-local, RFC1918, metadata, and userinfo."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ConsoleError("url_scheme_not_allowed")
    if parsed.username is not None or parsed.password is not None:
        raise ConsoleError(URL_DESTINATION_NOT_ALLOWED)
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise ConsoleError(URL_DESTINATION_NOT_ALLOWED)
    if host in _BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        raise ConsoleError(URL_DESTINATION_NOT_ALLOWED)
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _ip_is_blocked(literal):
            raise ConsoleError(URL_DESTINATION_NOT_ALLOWED)
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ConsoleError(URL_DESTINATION_NOT_ALLOWED) from exc
    if not infos:
        raise ConsoleError(URL_DESTINATION_NOT_ALLOWED)
    for info in infos:
        addr = info[4][0]
        try:
            resolved = ipaddress.ip_address(addr)
        except ValueError as exc:
            raise ConsoleError(URL_DESTINATION_NOT_ALLOWED) from exc
        if _ip_is_blocked(resolved):
            raise ConsoleError(URL_DESTINATION_NOT_ALLOWED)


class IngestRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect hop. Internal Location MUST fail closed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        assert_url_destination_allowed(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_url_limited(url: str) -> tuple[bytes, str, str]:
    """GET ``url`` after SSRF checks, with Content-Length and streamed-body size checks."""
    assert_url_destination_allowed(url)
    parsed = urllib.parse.urlparse(url)
    limit = ingest_max_bytes()
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "vvn-operations-console/1.0"},
    )
    opener = urllib.request.build_opener(IngestRedirectHandler)
    try:
        with opener.open(request, timeout=30) as response:
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
