"""Durable derived-report lifecycle, local or PostgreSQL (never a PG fallback).

One calculation key fixes owner/scope/definition/input. Exclusive locks cover
short status transactions and computation; a dropped connection/process releases
the claim. A later claimant records the interrupted attempt before retrying.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable

from src.integrity_kernel import stable_hash
from src.quality_evidence_v1 import instant
from src.quality_metrics_v1 import DEFINITION_VERSION


class QualityStoreError(RuntimeError):
    pass


class QualityReportStore:
    def __init__(self, directory: Path, *, connect: Callable | None = None):
        self.directory = directory
        self.connect = connect

    @contextmanager
    def _locked(self, key: str):
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise QualityStoreError("invalid_calculation_id")
        if self.connect is not None:
            with self.connect() as con:
                con.autocommit = True
                lock_key = int(key[:15], 16)
                con.execute("SELECT pg_advisory_lock(%s)", (lock_key,))
                try:
                    yield con
                finally:
                    con.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
        else:
            self.directory.mkdir(parents=True, exist_ok=True)
            with (self.directory / (key + ".lock")).open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                try:
                    yield None
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def _read(self, key: str, con: Any = None) -> dict[str, Any] | None:
        if con is not None:
            row = con.execute("SELECT payload FROM workflow.quality_measurements WHERE calculation_id=%s", (key,)).fetchone()
            return deepcopy(row["payload"]) if row else None
        path = self.directory / (key + ".json")
        return json.loads(path.read_text()) if path.exists() else None

    def _write(self, record: dict[str, Any], con: Any = None) -> None:
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
        if con is not None:
            with con.transaction():
                con.execute("INSERT INTO workflow.quality_measurements(calculation_id,owner_account_id,payload) "
                            "VALUES(%s,%s,%s::jsonb) ON CONFLICT(calculation_id) DO UPDATE "
                            "SET payload=EXCLUDED.payload,updated_at=CURRENT_TIMESTAMP",
                            (record["calculation_id"], record["owner_account_id"], payload))
        else:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / (record["calculation_id"] + ".json")
            name = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", dir=self.directory, delete=False) as tmp:
                    name = tmp.name
                    tmp.write(payload)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                os.replace(name, path)
                fd = os.open(self.directory, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            finally:
                if name and os.path.exists(name):
                    os.unlink(name)

    def calculate(self, *, owner: str, inputs: dict[str, Any], build: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        frozen = deepcopy(inputs)
        key = stable_hash({"owner": owner, "definition": DEFINITION_VERSION, "inputs": {k: v for k, v in frozen.items() if k != "observed_at"}})
        with self._locked(key) as con:
            record = self._read(key, con)
            if record and record["status"] == "available":
                return record
            if record is None:
                record = {"calculation_id": key, "owner_account_id": owner,
                          "definition_version": DEFINITION_VERSION, "status": "requested",
                          "created_at": instant(), "inputs": frozen, "attempts": []}
                self._write(record, con)
            elif record["status"] == "running":
                record["attempts"][-1].update(status="interrupted", finished_at=instant())
                record["status"] = "interrupted"
                self._write(record, con)
            record["status"] = "requested"
            self._write(record, con)
            attempt = {"number": len(record["attempts"]) + 1, "started_at": instant(), "status": "running"}
            record["attempts"].append(attempt)
            record["status"] = "running"
            self._write(record, con)
            try:
                report = build(deepcopy(record["inputs"]))
            except Exception as exc:
                attempt.update(status="failed", finished_at=instant(), error_type=type(exc).__name__)
                record["status"] = "failed"
                self._write(record, con)
                raise QualityStoreError("quality_calculation_failed") from exc
            attempt.update(status="available", finished_at=instant())
            record.update(status="available", report=report, completed_at=instant())
            self._write(record, con)
            return deepcopy(record)

    def history(self, *, owner: str, allowed_scope: set[str]) -> list[dict[str, Any]]:
        if self.connect is not None:
            with self.connect() as con:
                rows = [r["payload"] for r in con.execute(
                    "SELECT payload FROM workflow.quality_measurements WHERE owner_account_id=%s ORDER BY updated_at DESC",
                    (owner,)).fetchall()]
        else:
            rows = [json.loads(p.read_text()) for p in self.directory.glob("*.json")] if self.directory.exists() else []
        return sorted([r for r in rows if r.get("owner_account_id") == owner
                       and r.get("status") == "available"
                       and {d["envelope"]["snapshot_id"] for d in r.get("inputs", {}).get("documents", [])} <= allowed_scope],
                      key=lambda r: r["completed_at"], reverse=True)
