#!/usr/bin/env python3
"""Tenant authentication, authorization and rate limiting for Product API v1.

Pilot implementation rules:
- API keys are never stored or logged in plaintext.
- Registry contains only SHA-256 hashes of API keys.
- Tenant entitlements are enforced before records enter retrieval.
- Rate limiting is in-process for the local pilot; Azure/APIM can replace it
  without changing the Product API contract.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def hash_api_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TenantPolicy:
    tenant_id: str
    name: str
    enabled: bool
    api_key_sha256: str
    scopes: frozenset[str]
    allowed_document_ids: frozenset[str]
    allowed_topics: frozenset[str]
    requests_per_minute: int
    max_top_k: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TenantPolicy":
        digest = str(data.get("api_key_sha256") or "").lower().strip()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"tenant {data.get('tenant_id')}: api_key_sha256 must be 64 lowercase hex chars")
        tenant_id = str(data.get("tenant_id") or "").strip()
        if not tenant_id:
            raise ValueError("tenant_id_missing")
        rpm = int(data.get("requests_per_minute", 60))
        max_top_k = int(data.get("max_top_k", 10))
        if rpm < 1 or max_top_k < 1:
            raise ValueError(f"tenant {tenant_id}: limits must be >= 1")
        return cls(
            tenant_id=tenant_id,
            name=str(data.get("name") or tenant_id),
            enabled=bool(data.get("enabled", True)),
            api_key_sha256=digest,
            scopes=frozenset(str(x) for x in data.get("scopes", [])),
            allowed_document_ids=frozenset(str(x) for x in data.get("allowed_document_ids", [])),
            allowed_topics=frozenset(str(x) for x in data.get("allowed_topics", ["*"])),
            requests_per_minute=rpm,
            max_top_k=max_top_k,
        )

    def has_scope(self, scope: str) -> bool:
        return "*" in self.scopes or scope in self.scopes

    def allows_document(self, document_id: str | None) -> bool:
        if not document_id:
            return False
        return "*" in self.allowed_document_ids or document_id in self.allowed_document_ids

    def allows_topics(self, topics: list[str] | tuple[str, ...] | None) -> bool:
        if "*" in self.allowed_topics:
            return True
        if not topics:
            return False
        return any(str(t) in self.allowed_topics for t in topics)


class TenantRegistry:
    def __init__(self, tenants: list[TenantPolicy]):
        ids = [t.tenant_id for t in tenants]
        hashes = [t.api_key_sha256 for t in tenants]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_tenant_id")
        if len(hashes) != len(set(hashes)):
            raise ValueError("duplicate_api_key_hash")
        self.tenants = tuple(tenants)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TenantRegistry":
        return cls([TenantPolicy.from_dict(x) for x in data.get("tenants", [])])

    @classmethod
    def from_path(cls, path: Path) -> "TenantRegistry":
        if not path.exists():
            return cls([])
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def authenticate(self, api_key: str) -> TenantPolicy | None:
        supplied = hash_api_key(api_key)
        # Compare all candidates rather than short-circuiting on prefix/string equality.
        match: TenantPolicy | None = None
        for tenant in self.tenants:
            if hmac.compare_digest(supplied, tenant.api_key_sha256):
                match = tenant
        if match is None or not match.enabled:
            return None
        return match


class SlidingWindowRateLimiter:
    """In-process pilot rate limiter. Use APIM/Redis for distributed deployment."""

    def __init__(self, *, now: Callable[[], float] = time.monotonic):
        self._now = now
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, tenant_id: str, limit: int) -> tuple[bool, int]:
        now = self._now()
        cutoff = now - 60.0
        with self._lock:
            q = self._events[tenant_id]
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= limit:
                retry_after = max(1, int(60 - (now - q[0]))) if q else 60
                return False, retry_after
            q.append(now)
            return True, 0
