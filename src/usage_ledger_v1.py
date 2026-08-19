#!/usr/bin/env python3
"""Privacy-minimizing usage and audit ledger for Product API v1."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_usage (
  request_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  status_code INTEGER NOT NULL,
  behavior TEXT,
  result_count INTEGER NOT NULL DEFAULT 0,
  query_sha256 TEXT,
  result_object_ids_json TEXT NOT NULL DEFAULT '[]',
  latency_ms REAL NOT NULL,
  synthetic_fixture INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_api_usage_tenant_created ON api_usage(tenant_id, created_at);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def hash_query(query: str | None) -> str | None:
    if query is None:
        return None
    normalized = " ".join(query.split()).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class UsageLedger:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def record(
        self,
        *,
        request_id: str,
        tenant_id: str,
        endpoint: str,
        status_code: int,
        behavior: str | None,
        result_count: int,
        query: str | None,
        result_object_ids: list[str] | None,
        latency_ms: float,
        synthetic_fixture: bool,
    ) -> None:
        with self._connect() as con:
            con.execute(
                """INSERT INTO api_usage(
                    request_id,created_at,tenant_id,endpoint,status_code,behavior,result_count,
                    query_sha256,result_object_ids_json,latency_ms,synthetic_fixture
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    request_id, utc_now(), tenant_id, endpoint, status_code, behavior, int(result_count),
                    hash_query(query), json.dumps(result_object_ids or [], ensure_ascii=False, separators=(",", ":")),
                    float(latency_ms), 1 if synthetic_fixture else 0,
                ),
            )

    def summary(self, tenant_id: str) -> dict[str, Any]:
        with self._connect() as con:
            totals = con.execute(
                """SELECT COUNT(*) AS requests,
                          SUM(CASE WHEN behavior='retrieve' THEN 1 ELSE 0 END) AS retrieves,
                          SUM(CASE WHEN behavior='abstain' THEN 1 ELSE 0 END) AS abstains,
                          SUM(result_count) AS results_returned
                   FROM api_usage WHERE tenant_id=?""",
                (tenant_id,),
            ).fetchone()
            by_endpoint = con.execute(
                """SELECT endpoint, COUNT(*) AS requests
                   FROM api_usage WHERE tenant_id=? GROUP BY endpoint ORDER BY endpoint""",
                (tenant_id,),
            ).fetchall()
        return {
            "tenant_id": tenant_id,
            "requests": int(totals["requests"] or 0),
            "retrieves": int(totals["retrieves"] or 0),
            "abstains": int(totals["abstains"] or 0),
            "results_returned": int(totals["results_returned"] or 0),
            "by_endpoint": [{"endpoint": r["endpoint"], "requests": int(r["requests"])} for r in by_endpoint],
        }
