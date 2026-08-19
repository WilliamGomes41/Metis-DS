#!/usr/bin/env python3
"""Fail-closed release gate before step 5 (storage/retrieval activation)."""
from __future__ import annotations
import argparse, json
from pathlib import Path


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--semantic-report', type=Path, required=True)
    p.add_argument('--validation-report', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args=p.parse_args()
    sem=json.loads(args.semantic_report.read_text(encoding='utf-8'))
    val=json.loads(args.validation_report.read_text(encoding='utf-8'))
    checks={
        'semantic_schema_valid': bool(sem.get('schema_valid')),
        'semantic_integrity_valid': all((sem.get('integrity_checks') or {}).values()),
        'clinical_review_complete': bool(val.get('all_reviewed')),
        'validation_errors_zero': not bool(val.get('errors')),
        'pending_zero': int(val.get('pending_or_revise', 0)) == 0,
    }
    status='PASS' if all(checks.values()) else 'BLOCKED'
    report={'gate':'pre_step5','status':status,'checks':checks}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if status=='PASS' else 2

if __name__=='__main__': raise SystemExit(main())
