#!/usr/bin/env python3
"""Explicit reversible attempt relocation. Default dry-run; never called by GET/startup.

Historical inline validator inputs remain explicitly legacy diagnostic evidence.
They are not promoted to reusable TaskResults. New attempts use input references.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError, _json_text
from src.workflows.formation_task_store_v1 import FormationTaskStore


def migrate(store, snapshot_id, *, apply=False):
    with store._connect() as con:
        with con.transaction():
            row = con.execute("SELECT envelope_payload,processing_storage_version FROM workflow.documents "
                              "WHERE snapshot_id=%s FOR UPDATE",(snapshot_id,)).fetchone()
            if not row:
                raise WorkflowDocumentStoreError("workflow_document_not_found")
            if row["processing_storage_version"] == 1:
                return {"snapshot_id":snapshot_id,"status":"already_migrated","applied":False}
            if store._release_history_locked(con,snapshot_id):
                raise WorkflowDocumentStoreError("published_objects_must_not_be_rewritten")
            envelope = row["envelope_payload"]
            attempts = envelope.get("processing_attempts") or []
            if any(a.get("state") == "running" for a in attempts):
                raise WorkflowDocumentStoreError("processing_attempt_in_progress")
            result = {"snapshot_id":snapshot_id,"status":"eligible","attempt_count":len(attempts),
                      "inline_attempt_bytes":len(_json_text(attempts).encode()),"applied":apply}
            if apply:
                FormationTaskStore.save_attempts(con,snapshot_id,attempts)
                if FormationTaskStore.attempts(con,snapshot_id) != attempts:
                    raise WorkflowDocumentStoreError("processing_migration_verification_failed")
                envelope = {k:v for k,v in envelope.items() if k != "processing_attempts"}
                envelope["processing_storage"] = "task-v1"
                con.execute("UPDATE workflow.documents SET envelope_payload=%s::jsonb,processing_storage_version=1 "
                            "WHERE snapshot_id=%s",(_json_text(envelope),snapshot_id))
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-id",required=True)
    parser.add_argument("--apply",action="store_true")
    args = parser.parse_args()
    print(json.dumps(migrate(PostgresConcurrentWorkflowDocumentStore(),args.snapshot_id,apply=args.apply)))


if __name__ == "__main__":
    main()
