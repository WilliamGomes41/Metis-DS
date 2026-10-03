#!/usr/bin/env python3
"""Bounded read-only task-count measurement without app bootstrap or migrations."""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / ".python_packages"), str(ROOT)]

from src.azure_postgres_credential_v1 import CachedAzurePostgresCredential
from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.console_performance_v1 import performance_scope
from src.operations_console_v1 import SCHEMA_V14
from src.workflows.workflow_badge_counts_postgres_v1 import (
    FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole as Console,
)
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True)
    args = parser.parse_args()

    def stop(*_args):
        print(json.dumps({"status": "timeout", "limit_seconds": 60}), flush=True)
        raise SystemExit(1)

    signal.signal(signal.SIGALRM, stop)
    signal.alarm(60)
    credential = CachedAzurePostgresCredential()

    def readonly(store):
        original = store._connect

        def connect():
            con = original()
            try:
                con.execute("SET TRANSACTION READ ONLY")
                con.execute("SET LOCAL statement_timeout = '10s'")
                return con
            except Exception:
                con.close()
                raise

        store._connect = connect
        return store

    # Deliberately avoid constructors with reconciliation/startup side effects.
    probe = object.__new__(Console)
    probe.workflow_identity_store = readonly(PostgresWorkflowIdentityStore(credential=credential))
    probe.workflow_document_store = readonly(PostgresConcurrentWorkflowDocumentStore(credential=credential))
    probe.workflow_review_store = readonly(PostgresWorkflowReviewStore(credential=credential))
    probe.canonical_publication_store = readonly(PostgresCanonicalPublicationStore(credential=credential))
    probe.root = ROOT
    data = Path(os.environ.get("CONSOLE_DATA_ROOT", "/home/data/metis-console"))
    probe.runtime = Path(os.environ.get("CONSOLE_RUNTIME", str(data / "output/runtime/operations-console")))
    probe.source_store = Path(os.environ.get("CONSOLE_SOURCE_STORE", str(data / "sources/private")))
    probe.schema_path = SCHEMA_V14
    probe.immutable_source_store = None
    probe._envelopes = {}
    probe._bindings = {}
    probe._ledger_path = probe.runtime / "review_ledger.jsonl"
    try:
        for number in range(1, 4):
            start = time.perf_counter()
            with performance_scope() as metrics:
                probe.waiting_task_counts(args.account_id)
            print(json.dumps({"measurement": number, "status": "ok",
                              "duration_ms": round((time.perf_counter() - start) * 1000, 3),
                              "badge_ms": round(metrics.badge_ms, 3),
                              "db_connections": metrics.connections,
                              "db_queries": metrics.queries}), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        return 1
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
