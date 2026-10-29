#!/usr/bin/env python3
"""Explicit additive Review-card preparation/check; never invoked by GET/startup."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflows.workflow_transaction_v1 import workflow_read_transaction
from src.workflows.review_card_inputs_postgres_v1 import capture_review_cards, prepare_review_cards


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--snapshot', action='append', help='Explicit snapshot; repeat for several documents')
    scope.add_argument('--all', action='store_true', help='Explicitly prepare/check all existing workflow documents')
    parser.add_argument('--check', action='store_true', help='Read-only validation; do not prepare anything')
    args = parser.parse_args()
    config = PostgresCanonicalConfig.from_environ()
    credential = None
    if not config.dsn:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
    store = PostgresWorkflowDocumentRuntimeStore(config, credential=credential)
    with store._connect() as con:
        ids = args.snapshot or [row['snapshot_id'] for row in con.execute(
            'SELECT snapshot_id FROM workflow.documents ORDER BY snapshot_id').fetchall()]
    failed = False
    for sid in dict.fromkeys(ids):
        try:
            if args.check:
                with workflow_read_transaction(store) as con:
                    result = capture_review_cards(store, con, [sid])[sid]
                if 'unavailable' in result:
                    raise WorkflowDocumentStoreError(result['unavailable'])
                report = {'snapshot_id': sid, 'objects': len(result['objects']), 'status': 'current'}
            else:
                report = {**prepare_review_cards(store, sid), 'status': 'prepared'}
        except Exception as error:
            # Permit only owned machine-readable codes, never payloads, database
            # exception text or credentials. Unexpected failures remain generic.
            code = str(error) if isinstance(error, WorkflowDocumentStoreError) else ''
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,100}', code):
                code = 'review_card_preparation_failed'
            report = {'snapshot_id': sid, 'status': 'unavailable', 'reason': code}
            failed = True
        print(json.dumps(report, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
