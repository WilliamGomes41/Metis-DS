"""Isolated, versioned comparison evidence for Quality & workprocess.

The aggregate owns experimental state only. It never writes KnowledgeObjects,
review bindings, publication records, or the normal quality event ledger.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable
from uuid import uuid4

VERSION = "route-comparison-v1"
ASSESSMENT_VERSION = "route-assessment-v1"
ROUTES = ("deterministic", "semantic")
CHOICES = ("direct", "repair", "unusable", "unassessable")
_ID = re.compile(r"rc_[0-9a-f]{32}")


class ComparisonError(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _event(row: dict[str, Any], actor: str, action: str) -> None:
    row["version"] += 1
    row["events"].append({"actor": actor, "action": action, "at": now(),
                          "version": row["version"]})


def new_comparison(*, owner: str, snapshot_id: str, source_hash: str,
                   title: str) -> dict[str, Any]:
    if not owner or not snapshot_id or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        raise ComparisonError("comparison_source_invalid")
    row = {"schema_version": VERSION, "comparison_id": "rc_" + uuid4().hex,
           "owner_account_id": owner, "snapshot_id": snapshot_id,
           "source_hash": source_hash, "title": title, "state": "draft",
           "version": 0, "created_at": now(), "events": [], "arms": {},
           "assessments": {}, "analyses": []}
    _event(row, owner, "created")
    return row


def freeze(row: dict[str, Any], *, actor: str, source_hash: str,
           fragments: list[dict[str, Any]], code_version: str, semantic_model: str) -> None:
    if row["state"] != "draft" or actor != row["owner_account_id"]:
        raise ComparisonError("comparison_transition_forbidden")
    if source_hash != row["source_hash"] or not fragments or len(fragments) > 30:
        raise ComparisonError("comparison_source_mismatch")
    if not code_version or not semantic_model or sum(len(str(f.get("clean_text") or f.get("raw_text") or "")) for f in fragments) > 20000:
        raise ComparisonError("comparison_input_limit")
    ids = [str(f.get("fragment_id") or "") for f in fragments]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ComparisonError("comparison_fragments_invalid")
    row["fragments"] = deepcopy(fragments)
    row["input_hash"] = digest(fragments)
    row["code_version"] = code_version
    row["semantic_model"] = semantic_model
    row["arms"] = {route: {"status": "pending", "attempts": []} for route in ROUTES}
    # The mapping is retained only in the aggregate; the assessment view hides it.
    row["blind_order"] = list(ROUTES) if int(digest(row["comparison_id"])[0], 16) % 2 else list(reversed(ROUTES))
    row["state"] = "frozen"
    _event(row, actor, "frozen")


def claim_arm(row: dict[str, Any], *, actor: str, route: str) -> str:
    if actor != row["owner_account_id"] or route not in ROUTES:
        raise ComparisonError("comparison_transition_forbidden")
    if row["state"] not in {"frozen", "running", "blocked"}:
        raise ComparisonError("comparison_transition_forbidden")
    arm = row["arms"][route]
    if arm["status"] == "succeeded":
        return ""
    if arm["status"] == "running":
        started = datetime.fromisoformat(arm["attempts"][-1]["started_at"])
        if datetime.now(timezone.utc) - started < timedelta(minutes=10):
            raise ComparisonError("comparison_arm_running")
        arm["attempts"][-1].update(status="interrupted", finished_at=now())
    attempt_id = uuid4().hex
    arm["attempts"].append({"attempt_id": attempt_id, "status": "running",
                            "started_at": now()})
    arm["status"] = "running"
    row["state"] = "running"
    _event(row, actor, "arm_claimed:" + route)
    return attempt_id


def finish_arm(row: dict[str, Any], *, actor: str, route: str, attempt_id: str,
               output: list[dict[str, Any]], execution: dict[str, Any]) -> None:
    arm = row["arms"].get(route)
    if row["state"] != "running" or actor != row["owner_account_id"] or not arm or arm["status"] != "running" or (
        arm["attempts"][-1]["attempt_id"] != attempt_id
    ):
        raise ComparisonError("comparison_stale_attempt")
    if not isinstance(output, list) or len(output) > 200 or not all(
        isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip()
        and isinstance(item.get("source_fragment_ids"), list) for item in output
    ):
        raise ComparisonError("comparison_output_invalid")
    known = {f["fragment_id"] for f in row["fragments"]}
    if any(not set(item["source_fragment_ids"]) <= known or not item["source_fragment_ids"] for item in output):
        raise ComparisonError("comparison_output_source_unbound")
    arm["output"] = deepcopy(output)
    arm["output_hash"] = digest(output)
    arm["execution"] = deepcopy(execution)
    arm["status"] = "succeeded"
    arm["attempts"][-1].update(status="succeeded", finished_at=now())
    row["state"] = "output_ready" if all(a["status"] == "succeeded" for a in row["arms"].values()) else "running"
    _event(row, actor, "arm_succeeded:" + route)


def fail_arm(row: dict[str, Any], *, actor: str, route: str,
             attempt_id: str, error_code: str) -> None:
    arm = row["arms"].get(route)
    if row["state"] != "running" or actor != row["owner_account_id"] or not arm or arm["status"] != "running" or (
        arm["attempts"][-1]["attempt_id"] != attempt_id
    ):
        raise ComparisonError("comparison_stale_attempt")
    arm["status"] = "failed"
    arm["attempts"][-1].update(status="failed", finished_at=now(), error_code=error_code)
    row["state"] = "blocked"
    _event(row, actor, "arm_failed:" + route)


def blind_view(row: dict[str, Any]) -> dict[str, Any]:
    if row["state"] not in {"output_ready", "assessing", "assessed"}:
        raise ComparisonError("comparison_not_assessable")
    return {"comparison_id": row["comparison_id"], "snapshot_id": row["snapshot_id"],
            "title": row["title"], "source_hash": row["source_hash"],
            "source_text": [str(f.get("clean_text") or f.get("raw_text") or "") for f in row["fragments"]],
            "arms": {label: deepcopy(row["arms"][route]["output"])
                     for label, route in zip(("A", "B"), row["blind_order"])},
            "assessed": sorted(row["assessments"])}


def assess(row: dict[str, Any], *, actor: str, label: str,
           choices: list[str], coverage: str, problems: list[str],
           actions: int) -> None:
    if row["state"] not in {"output_ready", "assessing"} or label not in {"A", "B"}:
        raise ComparisonError("comparison_transition_forbidden")
    if label in row["assessments"]:
        raise ComparisonError("comparison_assessment_locked")
    view = blind_view(row)
    if len(choices) != len(view["arms"][label]) or any(c not in CHOICES for c in choices):
        raise ComparisonError("comparison_assessment_invalid")
    if coverage not in {"complete", "partial", "missing", "unassessable"} or (
        not isinstance(actions, int) or isinstance(actions, bool) or actions < 0
    ):
        raise ComparisonError("comparison_assessment_invalid")
    if not choices and coverage == "complete":
        raise ComparisonError("comparison_empty_output_cannot_cover_source")
    allowed = {"missing_qualifier", "unsupported_addition", "wrong_relation",
               "fragmentation", "other"}
    if not isinstance(problems, list) or any(p not in allowed for p in problems):
        raise ComparisonError("comparison_assessment_invalid")
    row["assessments"][label] = {"version": ASSESSMENT_VERSION, "actor": actor,
                                  "at": now(), "choices": list(choices),
                                  "coverage": coverage, "problems": list(problems),
                                  "actions": actions}
    row["state"] = "assessed" if len(row["assessments"]) == 2 else "assessing"
    _event(row, actor, "assessed:" + label)


def analyze(row: dict[str, Any], *, actor: str) -> dict[str, Any]:
    if row["state"] not in {"assessed", "analyzed"} or actor != row["owner_account_id"]:
        raise ComparisonError("comparison_transition_forbidden")
    if row["state"] == "analyzed":
        return deepcopy(row["analyses"][-1])
    results = {}
    for label, route in zip(("A", "B"), row["blind_order"]):
        a = row["assessments"][label]
        results[route] = {"candidate_count": len(a["choices"]),
                          "direct": a["choices"].count("direct"),
                          "repair": a["choices"].count("repair"),
                          "unusable": a["choices"].count("unusable"),
                          "unassessable": a["choices"].count("unassessable"),
                          "coverage": a["coverage"], "problems": a["problems"],
                          "actions": a["actions"],
                          "output_hash": row["arms"][route]["output_hash"]}
    report = {"definition_version": VERSION, "source_hash": row["source_hash"],
              "input_hash": row["input_hash"], "code_version": row["code_version"],
              "semantic_model": row["semantic_model"],
              "comparison_id": row["comparison_id"], "results": results,
              "limits": "Eén broncase; kandidaten kunnen verschillen in aantal. Geen causale of klinische kwaliteitsclaim."}
    row["analyses"].append(deepcopy(report))
    row["state"] = "analyzed"
    _event(row, actor, "analyzed")
    return report


def close(row: dict[str, Any], *, actor: str, decision: str) -> None:
    if row["state"] != "analyzed" or actor != row["owner_account_id"] or decision not in {
        "inconclusive", "more_cases", "implementation_proposal"
    }:
        raise ComparisonError("comparison_transition_forbidden")
    row["decision"] = decision
    row["state"] = "closed"
    _event(row, actor, "closed")


def cancel(row: dict[str, Any], *, actor: str, reason: str) -> None:
    if actor != row["owner_account_id"] or row["state"] in {"closed", "cancelled"} or not reason.strip():
        raise ComparisonError("comparison_transition_forbidden")
    row["cancellation_reason"] = reason.strip()
    row["state"] = "cancelled"
    _event(row, actor, "cancelled")


class ComparisonStore:
    """One authoritative record per comparison, with short cross-process locks."""

    def __init__(self, directory: Path, *, connect: Callable | None = None):
        self.directory, self.connect = Path(directory), connect

    @contextmanager
    def _locked(self, comparison_id: str):
        if not _ID.fullmatch(comparison_id):
            raise ComparisonError("comparison_id_invalid")
        if self.connect:
            with self.connect() as con:
                con.autocommit = True
                key = int(hashlib.sha256(comparison_id.encode()).hexdigest()[:15], 16)
                con.execute("SELECT pg_advisory_lock(%s)", (key,))
                try:
                    yield con
                finally:
                    con.execute("SELECT pg_advisory_unlock(%s)", (key,))
        else:
            self.directory.mkdir(parents=True, exist_ok=True)
            with (self.directory / (comparison_id + ".lock")).open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                try:
                    yield None
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def _read(self, comparison_id: str, con: Any = None) -> dict[str, Any] | None:
        if con is not None:
            record = con.execute("SELECT payload FROM workflow.route_comparisons WHERE comparison_id=%s",
                                 (comparison_id,)).fetchone()
            return deepcopy(record["payload"]) if record else None
        path = self.directory / (comparison_id + ".json")
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def _write(self, row: dict[str, Any], con: Any = None) -> None:
        payload = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if con is not None:
            with con.transaction():
                con.execute("INSERT INTO workflow.route_comparisons(comparison_id,owner_account_id,payload) "
                            "VALUES(%s,%s,%s::jsonb) ON CONFLICT(comparison_id) DO UPDATE "
                            "SET payload=EXCLUDED.payload,updated_at=CURRENT_TIMESTAMP",
                            (row["comparison_id"], row["owner_account_id"], payload))
        else:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / (row["comparison_id"] + ".json")
            name = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory, delete=False) as tmp:
                    name = tmp.name
                    tmp.write(payload)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                os.replace(name, path)
            finally:
                if name and os.path.exists(name):
                    os.unlink(name)

    def create(self, row: dict[str, Any]) -> dict[str, Any]:
        with self._locked(row["comparison_id"]) as con:
            if self._read(row["comparison_id"], con):
                raise ComparisonError("comparison_duplicate")
            self._write(row, con)
            return deepcopy(row)

    def get(self, comparison_id: str, *, allowed_scope: set[str]) -> dict[str, Any] | None:
        with self._locked(comparison_id) as con:
            row = self._read(comparison_id, con)
            if row and row["snapshot_id"] in allowed_scope:
                return row
        return None

    def list(self, *, owner: str, allowed_scope: set[str]) -> list[dict[str, Any]]:
        if self.connect:
            with self.connect() as con:
                rows = [r["payload"] for r in con.execute(
                    "SELECT payload FROM workflow.route_comparisons WHERE owner_account_id=%s ORDER BY updated_at DESC",
                    (owner,)).fetchall()]
        else:
            rows = [json.loads(p.read_text(encoding="utf-8")) for p in self.directory.glob("rc_*.json")]
        return [r for r in rows if r["owner_account_id"] == owner and r["snapshot_id"] in allowed_scope]

    def change(self, comparison_id: str, *, owner: str, allowed_scope: set[str],
               expected_version: int, operation: Callable[[dict[str, Any]], Any]) -> tuple[dict[str, Any], Any]:
        with self._locked(comparison_id) as con:
            row = self._read(comparison_id, con)
            if row is None or row["owner_account_id"] != owner or row["snapshot_id"] not in allowed_scope:
                raise ComparisonError("comparison_not_found")
            if row["version"] != expected_version:
                raise ComparisonError("comparison_stale_version")
            result = operation(row)
            self._write(row, con)
            return deepcopy(row), result
