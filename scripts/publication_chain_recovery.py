#!/usr/bin/env python3
"""Operator CLI for full Metis PostgreSQL + Blob backup, restore and integrity proof."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.g2_source_store import AzureBlobSourceStore
from src.legacy_canonical_recovery_v1 import (
    prepare_legacy_canonical_candidate,
    recover_legacy_canonical_release,
)
from src.runtime_data_inventory_v1 import DEFAULT_DATA_ROOT
from src.workflow_chain_recovery_v1 import (
    PostgresWorkflowRecoveryAdapter,
    backup_workflow_chain,
    live_workflow_chain_integrity,
    restore_workflow_chain,
    verify_workflow_chain_backup,
)
from src.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflow_review_postgres_v1 import PostgresWorkflowReviewStore


def _live_dependencies():
    store = PostgresCanonicalPublicationStore()
    store.verify_schema()
    return PostgresWorkflowRecoveryAdapter(store), AzureBlobSourceStore()


def main() -> int:
    parser = argparse.ArgumentParser(prog="publication-chain-recovery")
    sub = parser.add_subparsers(dest="command", required=True)

    backup = sub.add_parser("backup")
    backup.add_argument("--archive", type=Path, required=True)
    backup.add_argument("--runtime-root", type=Path, default=DEFAULT_DATA_ROOT)

    restore = sub.add_parser("restore")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--runtime-dest", type=Path, required=True)

    verify = sub.add_parser("verify-backup")
    verify.add_argument("--archive", type=Path, required=True)

    check = sub.add_parser("check-live")
    check.add_argument("--runtime-root", type=Path, default=DEFAULT_DATA_ROOT)

    recover = sub.add_parser("recover-legacy-release")
    recover.add_argument("--manifest", type=Path, required=True)
    recover.add_argument("--execute", action="store_true")
    recover.add_argument("--confirm-release-id")

    args = parser.parse_args()
    try:
        if args.command == "verify-backup":
            result = verify_workflow_chain_backup(args.archive)
        elif args.command == "recover-legacy-release":
            canonical_store = PostgresCanonicalPublicationStore()
            canonical_store.verify_schema()
            source_store = AzureBlobSourceStore()
            candidate = prepare_legacy_canonical_candidate(
                args.manifest,
                documents=PostgresWorkflowDocumentRuntimeStore(),
                reviews=PostgresWorkflowReviewStore(),
                source_store=source_store,
            )
            if not args.execute:
                result = candidate.summary(status="PLANNED")
            elif args.confirm_release_id != candidate.release_id:
                result = {
                    "ok": False,
                    "status": "BLOCKED",
                    "error": "legacy_release_confirmation_mismatch",
                }
            else:
                result = recover_legacy_canonical_release(
                    candidate,
                    canonical_store=canonical_store,
                )
        else:
            database, source_store = _live_dependencies()
            if args.command == "backup":
                manifest = backup_workflow_chain(
                    args.archive,
                    database=database,
                    source_store=source_store,
                    runtime_root=args.runtime_root,
                )
                result = {"ok": True, "archive": str(args.archive), "manifest": manifest}
            elif args.command == "restore":
                result = restore_workflow_chain(
                    args.archive,
                    database=database,
                    source_store=source_store,
                    runtime_dest=args.runtime_dest,
                )
            elif args.command == "check-live":
                result = live_workflow_chain_integrity(
                    database=database,
                    source_store=source_store,
                    runtime_root=args.runtime_root,
                )
            else:
                raise AssertionError(args.command)
    except Exception as exc:
        result = {"ok": False, "error": type(exc).__name__, "message": str(exc)}

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
