#!/usr/bin/env python3
"""Canonical storage and release-based publication layer for V&VN Data Services.

Reference runtime uses SQLite so the workflow is locally reproducible without an
external database. db/schema_v2.sql is the PostgreSQL production reference.

Safety properties:
- only fully approved, source-verified objects can enter canonical storage;
- publication never mutates the canonical object JSON;
- releases are explicit and owned;
- emergency unpublish changes only the publication registry;
- every state change writes an audit event;
- content hashes are recomputed before import and again before release.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.integrity_kernel import compute_canonical_object_hash, exact_review_snapshot_hash


SQLITE_SCHEMA = r"""
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS canonical_object_versions (
    object_id TEXT NOT NULL,
    object_version TEXT NOT NULL,
    document_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status = 'approved'),
    source_checksum TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    PRIMARY KEY (object_id, object_version),
    UNIQUE (object_id, object_version, content_hash)
);
CREATE TABLE IF NOT EXISTS publication_releases (
    release_id TEXT PRIMARY KEY,
    release_version TEXT NOT NULL UNIQUE,
    release_owner TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','withdrawn')),
    notes TEXT,
    created_at TEXT NOT NULL,
    published_at TEXT,
    withdrawn_at TEXT
);
CREATE TABLE IF NOT EXISTS publication_release_items (
    release_id TEXT NOT NULL REFERENCES publication_releases(release_id),
    object_id TEXT NOT NULL,
    object_version TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'publish' CHECK (action IN ('publish','supersede')),
    replaces_object_version TEXT,
    content_hash TEXT NOT NULL,
    PRIMARY KEY (release_id, object_id, object_version),
    FOREIGN KEY (object_id, object_version)
      REFERENCES canonical_object_versions(object_id, object_version)
);
CREATE TABLE IF NOT EXISTS publication_registry (
    object_id TEXT PRIMARY KEY,
    object_version TEXT NOT NULL,
    release_id TEXT NOT NULL REFERENCES publication_releases(release_id),
    state TEXT NOT NULL CHECK (state IN ('active','emergency_unpublished')),
    published_at TEXT NOT NULL,
    unpublished_at TEXT,
    unpublish_reason TEXT,
    FOREIGN KEY (object_id, object_version)
      REFERENCES canonical_object_versions(object_id, object_version)
);
CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('object','release')),
    entity_id TEXT NOT NULL,
    entity_version TEXT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_at TEXT NOT NULL,
    details_json TEXT NOT NULL
);
CREATE VIEW IF NOT EXISTS published_knowledge_objects AS
SELECT c.object_id, c.object_version, c.document_id, c.object_type,
       c.content_hash, c.canonical_json, r.release_id,
       rel.release_version, r.published_at
FROM publication_registry r
JOIN canonical_object_versions c
  ON c.object_id = r.object_id AND c.object_version = r.object_version
JOIN publication_releases rel ON rel.release_id = r.release_id
WHERE r.state = 'active' AND rel.status = 'published';
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def recompute_content_hash(obj: dict[str, Any]) -> str:
    """Full immutable canonical-object hash (integrity kernel)."""
    return compute_canonical_object_hash(obj)


def first_review_snapshot_hash(obj: dict[str, Any]) -> str:
    """Exact review snapshot of the canonical object (integrity kernel)."""
    return exact_review_snapshot_hash(obj)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(db: Path) -> None:
    with connect(db) as con:
        con.executescript(SQLITE_SCHEMA)


def audit(con: sqlite3.Connection, *, entity_type: str, entity_id: str, entity_version: str | None,
          event_type: str, actor: str, details: dict[str, Any] | None = None) -> None:
    con.execute(
        "INSERT INTO audit_events(entity_type,entity_id,entity_version,event_type,actor,event_at,details_json) VALUES(?,?,?,?,?,?,?)",
        (entity_type, entity_id, entity_version, event_type, actor, utc_now(),
         json.dumps(details or {}, ensure_ascii=False, sort_keys=True)),
    )


def eligibility_errors(obj: dict[str, Any], validator: Draft202012Validator) -> list[str]:
    errors: list[str] = []
    if list(validator.iter_errors(obj)):
        errors.append("schema_invalid")
        return errors
    g = obj["governance"]
    p = obj["provenance"]
    src = obj["source"]
    risk = obj["risk"]
    if g["validation_status"] != "approved":
        errors.append(f"validation_status_{g['validation_status']}")
    if g["publication_status"] != "unpublished":
        errors.append("canonical_object_must_remain_unpublished")
    if not g.get("validated_by") or not g.get("validation_date") or not g.get("review_snapshot_hash"):
        errors.append("approval_metadata_incomplete")
    elif g.get("review_snapshot_hash") != first_review_snapshot_hash(obj):
        errors.append("first_review_snapshot_mismatch")
    if g.get("validated_by") == p.get("created_by"):
        errors.append("reviewer_must_differ_from_creator")
    if obj["uncertainty"]["has_uncertainty"]:
        errors.append("unresolved_uncertainty")
    checksum = src.get("source_checksum")
    if src.get("integrity_status") != "verified" or not checksum:
        errors.append("source_not_hash_verified")
    elif len(checksum) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in checksum):
        errors.append("invalid_source_sha256")
    if p.get("proposal_id") is not None or p.get("transformation_mode") != "deterministic":
        errors.append("non_deterministic_or_proposal")
    actual_hash = recompute_content_hash(obj)
    if actual_hash != p.get("content_hash"):
        errors.append("content_hash_mismatch")
    if risk["requires_second_review"]:
        sr = g["second_review"]
        if sr.get("status") != "approved" or not sr.get("reviewer") or not sr.get("review_date") or not sr.get("snapshot_hash"):
            errors.append("second_review_incomplete")
        elif sr.get("reviewer") == g.get("validated_by"):
            errors.append("second_reviewer_must_differ_from_first")
        elif sr.get("snapshot_hash") != first_review_snapshot_hash(obj):
            errors.append("second_review_snapshot_mismatch")
    return errors


def import_approved(db: Path, input_path: Path, schema_path: Path, actor: str) -> dict[str, Any]:
    init_db(db)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    rows = read_jsonl(input_path)
    imported = 0
    blocked: list[dict[str, Any]] = []
    with connect(db) as con:
        for obj in rows:
            errs = eligibility_errors(obj, validator)
            if errs:
                blocked.append({"object_id": obj.get("object_id"), "object_version": obj.get("object_version"), "errors": errs})
                continue
            payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            existing = con.execute(
                "SELECT content_hash FROM canonical_object_versions WHERE object_id=? AND object_version=?",
                (obj["object_id"], obj["object_version"]),
            ).fetchone()
            if existing and existing["content_hash"] != obj["provenance"]["content_hash"]:
                blocked.append({"object_id": obj["object_id"], "object_version": obj["object_version"], "errors": ["immutable_version_content_conflict"]})
                continue
            if not existing:
                con.execute(
                    "INSERT INTO canonical_object_versions(object_id,object_version,document_id,object_type,validation_status,source_checksum,content_hash,canonical_json,imported_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (obj["object_id"], obj["object_version"], obj["document_id"], obj["object_type"], "approved",
                     obj["source"]["source_checksum"], obj["provenance"]["content_hash"], payload, utc_now()),
                )
                audit(con, entity_type="object", entity_id=obj["object_id"], entity_version=obj["object_version"],
                      event_type="canonical_imported", actor=actor, details={"content_hash": obj["provenance"]["content_hash"]})
                imported += 1
    return {"input_objects": len(rows), "imported_objects": imported, "blocked_objects": len(blocked), "blocked": blocked}


def load_release_spec(path: Path) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    required = {"release_id", "release_version", "release_owner", "items"}
    missing = sorted(required - spec.keys())
    if missing:
        raise ValueError(f"release spec missing: {', '.join(missing)}")
    if not spec["release_owner"]:
        raise ValueError("release_owner is required")
    return spec


def create_release(db: Path, spec_path: Path, actor: str) -> dict[str, Any]:
    init_db(db)
    try:
        spec = load_release_spec(spec_path)
    except ValueError as exc:
        return {"status": "BLOCKED", "errors": [{"error": "invalid_release_spec", "message": str(exc)}]}
    errors: list[dict[str, Any]] = []
    with connect(db) as con:
        if con.execute("SELECT 1 FROM publication_releases WHERE release_id=?", (spec["release_id"],)).fetchone():
            return {"status": "BLOCKED", "errors": [{"error": "release_id_exists"}]}
        for item in spec["items"]:
            row = con.execute(
                "SELECT content_hash FROM canonical_object_versions WHERE object_id=? AND object_version=?",
                (item["object_id"], item["object_version"]),
            ).fetchone()
            if not row:
                errors.append({"object_id": item["object_id"], "object_version": item["object_version"], "error": "canonical_version_not_found"})
                continue
            if row["content_hash"] != item["content_hash"]:
                errors.append({"object_id": item["object_id"], "object_version": item["object_version"], "error": "release_content_hash_mismatch"})
            action = item.get("action", "publish")
            if action not in {"publish", "supersede"}:
                errors.append({"object_id": item["object_id"], "error": "invalid_release_action"})
            if action == "supersede" and not item.get("replaces_object_version"):
                errors.append({"object_id": item["object_id"], "error": "supersede_requires_replaces_object_version"})
        if errors:
            return {"status": "BLOCKED", "errors": errors}
        con.execute(
            "INSERT INTO publication_releases(release_id,release_version,release_owner,status,notes,created_at) VALUES(?,?,?,?,?,?)",
            (spec["release_id"], spec["release_version"], spec["release_owner"], "draft", spec.get("notes"), utc_now()),
        )
        for item in spec["items"]:
            con.execute(
                "INSERT INTO publication_release_items(release_id,object_id,object_version,action,replaces_object_version,content_hash) VALUES(?,?,?,?,?,?)",
                (spec["release_id"], item["object_id"], item["object_version"], item.get("action", "publish"),
                 item.get("replaces_object_version"), item["content_hash"]),
            )
        audit(con, entity_type="release", entity_id=spec["release_id"], entity_version=spec["release_version"],
              event_type="release_created", actor=actor, details={"item_count": len(spec["items"]), "release_owner": spec["release_owner"]})
    return {"status": "PASS", "release_id": spec["release_id"], "items": len(spec["items"])}


def publish_release(db: Path, release_id: str, actor: str) -> dict[str, Any]:
    init_db(db)
    errors: list[dict[str, Any]] = []
    now = utc_now()
    with connect(db) as con:
        rel = con.execute("SELECT * FROM publication_releases WHERE release_id=?", (release_id,)).fetchone()
        if not rel:
            return {"status": "BLOCKED", "errors": [{"error": "release_not_found"}]}
        if rel["status"] != "draft":
            return {"status": "BLOCKED", "errors": [{"error": "release_not_draft", "status": rel["status"]}]}
        if not rel["release_owner"]:
            return {"status": "BLOCKED", "errors": [{"error": "release_owner_missing"}]}
        items = con.execute("SELECT * FROM publication_release_items WHERE release_id=? ORDER BY object_id", (release_id,)).fetchall()
        if not items:
            return {"status": "BLOCKED", "errors": [{"error": "release_has_no_items"}]}
        for item in items:
            cov = con.execute(
                "SELECT content_hash, canonical_json FROM canonical_object_versions WHERE object_id=? AND object_version=?",
                (item["object_id"], item["object_version"]),
            ).fetchone()
            if not cov:
                errors.append({"object_id": item["object_id"], "error": "canonical_version_missing_at_publish"})
                continue
            if cov["content_hash"] != item["content_hash"]:
                errors.append({"object_id": item["object_id"], "error": "content_hash_changed_since_release_creation"})
            obj = json.loads(cov["canonical_json"])
            if recompute_content_hash(obj) != cov["content_hash"]:
                errors.append({"object_id": item["object_id"], "error": "stored_canonical_hash_invalid"})
            if obj["governance"]["validation_status"] != "approved":
                errors.append({"object_id": item["object_id"], "error": "stored_object_not_approved"})
            current = con.execute("SELECT * FROM publication_registry WHERE object_id=?", (item["object_id"],)).fetchone()
            if item["action"] == "publish":
                if current and current["state"] == "active" and current["object_version"] != item["object_version"]:
                    errors.append({"object_id": item["object_id"], "error": "active_version_exists_use_supersede", "active_version": current["object_version"]})
            elif item["action"] == "supersede":
                if not current or current["state"] != "active":
                    errors.append({"object_id": item["object_id"], "error": "no_active_version_to_supersede"})
                elif current["object_version"] != item["replaces_object_version"]:
                    errors.append({"object_id": item["object_id"], "error": "supersede_version_mismatch", "active_version": current["object_version"]})
        if errors:
            return {"status": "BLOCKED", "errors": errors}

        # One transaction: either the complete release becomes visible or none of it does.
        for item in items:
            current = con.execute("SELECT * FROM publication_registry WHERE object_id=?", (item["object_id"],)).fetchone()
            if current and item["action"] == "supersede":
                audit(con, entity_type="object", entity_id=item["object_id"], entity_version=current["object_version"],
                      event_type="superseded", actor=actor,
                      details={"superseded_by_version": item["object_version"], "release_id": release_id})
            con.execute(
                "INSERT INTO publication_registry(object_id,object_version,release_id,state,published_at,unpublished_at,unpublish_reason) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(object_id) DO UPDATE SET object_version=excluded.object_version,release_id=excluded.release_id,state='active',published_at=excluded.published_at,unpublished_at=NULL,unpublish_reason=NULL",
                (item["object_id"], item["object_version"], release_id, "active", now, None, None),
            )
            audit(con, entity_type="object", entity_id=item["object_id"], entity_version=item["object_version"],
                  event_type="published", actor=actor, details={"release_id": release_id})
        con.execute("UPDATE publication_releases SET status='published', published_at=? WHERE release_id=?", (now, release_id))
        audit(con, entity_type="release", entity_id=release_id, entity_version=rel["release_version"],
              event_type="release_published", actor=actor, details={"item_count": len(items), "release_owner": rel["release_owner"]})
    return {"status": "PASS", "release_id": release_id, "published_items": len(items)}


def withdraw_release(db: Path, release_id: str, actor: str, reason: str) -> dict[str, Any]:
    if not reason.strip():
        return {"status": "BLOCKED", "errors": [{"error": "reason_required"}]}
    init_db(db)
    with connect(db) as con:
        rel = con.execute("SELECT * FROM publication_releases WHERE release_id=?", (release_id,)).fetchone()
        if not rel:
            return {"status": "BLOCKED", "errors": [{"error": "release_not_found"}]}
        if rel["status"] != "published":
            return {"status": "BLOCKED", "errors": [{"error": "release_not_published", "status": rel["status"]}]}
        now = utc_now()
        active = con.execute("SELECT * FROM publication_registry WHERE release_id=? AND state='active'", (release_id,)).fetchall()
        for row in active:
            con.execute(
                "UPDATE publication_registry SET state='emergency_unpublished', unpublished_at=?, unpublish_reason=? WHERE object_id=? AND release_id=?",
                (now, reason, row["object_id"], release_id),
            )
            audit(con, entity_type="object", entity_id=row["object_id"], entity_version=row["object_version"],
                  event_type="release_withdrawal_unpublished", actor=actor, details={"reason": reason, "release_id": release_id})
        con.execute("UPDATE publication_releases SET status='withdrawn', withdrawn_at=? WHERE release_id=?", (now, release_id))
        audit(con, entity_type="release", entity_id=release_id, entity_version=rel["release_version"],
              event_type="release_withdrawn", actor=actor, details={"reason": reason, "affected_active_objects": len(active)})
    return {"status": "PASS", "release_id": release_id, "withdrawn_active_objects": len(active)}


def emergency_unpublish(db: Path, object_id: str, actor: str, reason: str) -> dict[str, Any]:
    if not reason.strip():
        return {"status": "BLOCKED", "errors": [{"error": "reason_required"}]}
    init_db(db)
    with connect(db) as con:
        row = con.execute("SELECT * FROM publication_registry WHERE object_id=?", (object_id,)).fetchone()
        if not row or row["state"] != "active":
            return {"status": "BLOCKED", "errors": [{"error": "object_not_actively_published"}]}
        now = utc_now()
        con.execute(
            "UPDATE publication_registry SET state='emergency_unpublished', unpublished_at=?, unpublish_reason=? WHERE object_id=?",
            (now, reason, object_id),
        )
        audit(con, entity_type="object", entity_id=object_id, entity_version=row["object_version"],
              event_type="emergency_unpublished", actor=actor, details={"reason": reason, "release_id": row["release_id"]})
    return {"status": "PASS", "object_id": object_id, "state": "emergency_unpublished"}


def export_published(db: Path, out: Path) -> dict[str, Any]:
    init_db(db)
    with connect(db) as con:
        rows = con.execute("SELECT * FROM published_knowledge_objects ORDER BY object_id").fetchall()
        payloads = []
        for row in rows:
            obj = json.loads(row["canonical_json"])
            payloads.append({
                "knowledge_object": obj,
                "publication": {
                    "release_id": row["release_id"],
                    "release_version": row["release_version"],
                    "published_at": row["published_at"],
                },
            })
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for p in payloads:
            f.write(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n")
    return {"published_objects": len(payloads), "out": str(out)}


def status(db: Path) -> dict[str, Any]:
    init_db(db)
    with connect(db) as con:
        counts = {
            "canonical_approved_versions": con.execute("SELECT COUNT(*) FROM canonical_object_versions").fetchone()[0],
            "draft_releases": con.execute("SELECT COUNT(*) FROM publication_releases WHERE status='draft'").fetchone()[0],
            "published_releases": con.execute("SELECT COUNT(*) FROM publication_releases WHERE status='published'").fetchone()[0],
            "active_published_objects": con.execute("SELECT COUNT(*) FROM publication_registry WHERE state='active'").fetchone()[0],
            "emergency_unpublished_objects": con.execute("SELECT COUNT(*) FROM publication_registry WHERE state='emergency_unpublished'").fetchone()[0],
            "audit_events": con.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
        }
    return counts


def write_report(report: dict[str, Any], path: Path | None) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--db", type=Path, required=True)

    p = sub.add_parser("import-approved")
    p.add_argument("--db", type=Path, required=True); p.add_argument("--input", type=Path, required=True)
    p.add_argument("--schema", type=Path, required=True); p.add_argument("--actor", required=True)
    p.add_argument("--report", type=Path)

    p = sub.add_parser("create-release")
    p.add_argument("--db", type=Path, required=True); p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--actor", required=True); p.add_argument("--report", type=Path)

    p = sub.add_parser("publish-release")
    p.add_argument("--db", type=Path, required=True); p.add_argument("--release-id", required=True)
    p.add_argument("--actor", required=True); p.add_argument("--report", type=Path)

    p = sub.add_parser("withdraw-release")
    p.add_argument("--db", type=Path, required=True); p.add_argument("--release-id", required=True)
    p.add_argument("--actor", required=True); p.add_argument("--reason", required=True); p.add_argument("--report", type=Path)

    p = sub.add_parser("emergency-unpublish")
    p.add_argument("--db", type=Path, required=True); p.add_argument("--object-id", required=True)
    p.add_argument("--actor", required=True); p.add_argument("--reason", required=True); p.add_argument("--report", type=Path)

    p = sub.add_parser("export-published")
    p.add_argument("--db", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    p.add_argument("--report", type=Path)

    p = sub.add_parser("status")
    p.add_argument("--db", type=Path, required=True); p.add_argument("--report", type=Path)

    args = ap.parse_args()
    try:
        if args.cmd == "init":
            init_db(args.db); report = {"status": "PASS", "db": str(args.db)}
        elif args.cmd == "import-approved":
            report = import_approved(args.db, args.input, args.schema, args.actor)
            report["status"] = "PASS" if report["blocked_objects"] == 0 else "BLOCKED"
        elif args.cmd == "create-release":
            report = create_release(args.db, args.spec, args.actor)
        elif args.cmd == "publish-release":
            report = publish_release(args.db, args.release_id, args.actor)
        elif args.cmd == "withdraw-release":
            report = withdraw_release(args.db, args.release_id, args.actor, args.reason)
        elif args.cmd == "emergency-unpublish":
            report = emergency_unpublish(args.db, args.object_id, args.actor, args.reason)
        elif args.cmd == "export-published":
            report = export_published(args.db, args.out); report["status"] = "PASS"
        elif args.cmd == "status":
            report = status(args.db); report["status"] = "PASS"
        else:
            raise AssertionError(args.cmd)
    except (ValueError, sqlite3.DatabaseError) as exc:
        report = {"status": "BLOCKED", "errors": [{"error": type(exc).__name__, "message": str(exc)}]}
    write_report(report, getattr(args, "report", None))
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
