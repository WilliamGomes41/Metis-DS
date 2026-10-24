"""Explicit, resumable derived-metadata backfill. Never called by GET/startup."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore


def backfill(store, *, apply=False, batch_size=32):
    if not 1 <= batch_size <= 1000:
        raise ValueError('source_summary_batch_size_invalid')
    processed = 0
    if apply:
        while True:
            with store._connect() as connection:
                rows = connection.execute("""
                    WITH pending AS (
                        SELECT snapshot_id FROM workflow.documents
                        WHERE source_selection_summary IS NULL
                        ORDER BY snapshot_id LIMIT %s FOR UPDATE SKIP LOCKED
                    )
                    UPDATE workflow.documents AS d SET source_selection_summary=NULL
                    FROM pending WHERE d.snapshot_id=pending.snapshot_id RETURNING d.snapshot_id
                """, (batch_size,)).fetchall()
            processed += len(rows)
            if not rows:
                break
    with store._connect() as connection:
        remaining = connection.execute(
            'SELECT count(*) AS n FROM workflow.documents WHERE source_selection_summary IS NULL'
        ).fetchone()['n']
    return {'applied': apply, 'processed': processed, 'remaining': remaining}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--batch-size', type=int, default=32)
    args = parser.parse_args()
    try:
        result = backfill(PostgresWorkflowDocumentRuntimeStore(), apply=args.apply,
                          batch_size=args.batch_size)
    except Exception:
        print('source_summary_backfill_failed', file=sys.stderr)
        return 1
    print(json.dumps(result))
    return int(bool(args.apply and result['remaining']))


if __name__ == '__main__':
    raise SystemExit(main())
