#!/usr/bin/env python3
"""Operator CLI for Metis publication-chain backup, restore and integrity proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.g2_source_store import AzureBlobSourceStore
from src.publication_chain_recovery_v1 import (
    PostgresPublicationBackupAdapter,
    backup_publication_chain,
    live_publication_chain_integrity,
)
from src.publication_chain_recovery_guard_v1 import (
    restore_publication_chain,
    verify_publication_chain_backup,
)
from src.runtime_data_inventory_v1 import DEFAULT_DATA_ROOT


def _live_dependencies():
    store = PostgresCanonicalPublicationStore()
    store.verify_schema()
    return PostgresPublicationBackupAdapter(store), AzureBlobSourceStore()


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

    args = parser.parse_args()
    try:
        if args.command == "verify-backup":
            result = verify_publication_chain_backup(args.archive)
        else:
            database, source_store = _live_dependencies()
            if args.command == "backup":
                manifest = backup_publication_chain(
                    args.archive,
                    database=database,
                    source_store=source_store,
                    runtime_root=args.runtime_root,
                )
                result = {"ok": True, "archive": str(args.archive), "manifest": manifest}
            elif args.command == "restore":
                result = restore_publication_chain(
                    args.archive,
                    database=database,
                    source_store=source_store,
                    runtime_dest=args.runtime_dest,
                )
            elif args.command == "check-live":
                result = live_publication_chain_integrity(
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
