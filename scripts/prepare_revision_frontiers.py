#!/usr/bin/env python3
"""Explicit retained-history preparation/check; no re-ingest, model or review writes."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflows.revision_frontiers_postgres_v1 import capture, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='append', required=True)
    parser.add_argument('--check', action='store_true', help='Read-only validation')
    args = parser.parse_args()
    config = PostgresCanonicalConfig.from_environ()
    credential = None
    if not config.dsn:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
    store = PostgresWorkflowDocumentRuntimeStore(config, credential=credential)
    failed = False
    for sid in dict.fromkeys(args.snapshot):
        try:
            if args.check:
                with store._connect() as con:
                    with con.transaction():
                        con.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                        if con.execute('SELECT 1 FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone() is None:
                            raise WorkflowDocumentStoreError('unknown_snapshot')
                        ids = [row['object_id'] for row in con.execute('SELECT DISTINCT object_id '
                            'FROM workflow.document_objects WHERE snapshot_id=%s', (sid,)).fetchall()]
                        window = capture(store, con, sid, ids)
                        if window is None:
                            raise WorkflowDocumentStoreError('revision_frontier_unprepared')
                        result = {'snapshot_id': sid, 'objects': len(window), 'status': 'current'}
            else:
                result = prepare(store, sid)
        except Exception as error:
            code = str(error) if isinstance(error, WorkflowDocumentStoreError) else ''
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,100}', code):
                code = 'revision_frontier_preparation_failed'
            result = {'snapshot_id': sid, 'status': 'unavailable', 'reason': code}
            failed = True
        print(json.dumps(result))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
