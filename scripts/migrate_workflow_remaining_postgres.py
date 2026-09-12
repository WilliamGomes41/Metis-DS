#!/usr/bin/env python3
"""Migrate remaining mutable console authority to PostgreSQL.

Run after migrations 002-005 and after identity/document/review migrations.
This command is explicit and fail-closed; application startup never imports local
state automatically.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore, WorkflowRemainingStoreError


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"workflow_remaining_invalid_json:{path.name}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"workflow_remaining_invalid_json:{path.name}")
    return value


def _migrate_audits(runtime: Path, store: PostgresWorkflowRemainingStore) -> int:
    root = runtime / "audits"
    local = [_read_json(path) for path in sorted(root.glob("audit-*.json"))] if root.is_dir() else []
    existing = store.list_audits()
    if existing:
        if existing != sorted(local, key=lambda row: (str(row.get("created_at") or ""), str(row.get("audit_id") or "")), reverse=True):
            raise RuntimeError("workflow_audit_migration_conflict")
        return len(local)
    for record in local:
        store.create_audit(record)
    return len(local)


def _migrate_secret(runtime: Path, store: PostgresWorkflowRemainingStore) -> int:
    path = runtime / "audit_secrets" / "llm_api_key.json"
    local = _read_json(path) if path.is_file() else None
    existing = store.get_secret_payload("llm_api_key")
    if existing is not None and existing != local:
        raise RuntimeError("workflow_audit_secret_migration_conflict")
    if existing is None and local is not None:
        store.set_secret_payload("llm_api_key", local)
    return 1 if local is not None else 0


def _history_rows(path: Path) -> list[dict]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("workflow_class_history_invalid") from exc
    if any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("workflow_class_history_invalid")
    return rows


def _migrate_class_history(runtime: Path, documents: PostgresWorkflowDocumentRuntimeStore) -> int:
    migrated = 0
    history_root = runtime / "class_change_history"
    for envelope in documents.list_envelopes():
        changed = False
        history = []
        for record in envelope.get("prior_processing_history") or []:
            item = dict(record)
            if isinstance(item.get("objects"), list):
                history.append(item)
                continue
            filename = str(item.get("history_file") or "")
            if not filename or Path(filename).name != filename:
                raise RuntimeError("workflow_class_history_cutover_not_prepared")
            path = history_root / filename
            if not path.is_file():
                raise RuntimeError("workflow_class_history_cutover_not_prepared")
            rows = _history_rows(path)
            expected_ids = [str(value or "") for value in item.get("object_ids") or []]
            actual_ids = [str(row.get("object_id") or "") for row in rows]
            if int(item.get("object_count") or 0) != len(rows) or expected_ids != actual_ids:
                raise RuntimeError("workflow_class_history_migration_conflict")
            item["objects"] = rows
            item["history_file"] = ""
            history.append(item)
            changed = True
            migrated += 1
        if changed:
            updated = dict(envelope)
            updated["prior_processing_history"] = history
            documents.write_bundle(envelope=updated)
    return migrated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    args = parser.parse_args()

    remaining = PostgresWorkflowRemainingStore()
    remaining.verify_remaining_schema()
    documents = PostgresWorkflowDocumentRuntimeStore()
    documents.verify_cutover_schema()
    try:
        result = {
            "audits": _migrate_audits(args.runtime, remaining),
            "audit_secrets": _migrate_secret(args.runtime, remaining),
            "class_history_records": _migrate_class_history(args.runtime, documents),
        }
    except WorkflowRemainingStoreError as exc:
        raise RuntimeError("workflow_remaining_migration_failed") from exc
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
