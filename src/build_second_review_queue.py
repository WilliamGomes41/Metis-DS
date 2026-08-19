#!/usr/bin/env python3
"""Create a four-eyes review queue for approved high-risk knowledge objects."""
from __future__ import annotations
import argparse, json
from pathlib import Path


def read_jsonl(path: Path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('input', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    args=ap.parse_args()
    queue=[]
    for o in read_jsonl(args.input):
        g=o['governance']
        if g['validation_status']=='approved' and o['risk']['requires_second_review'] and g['second_review']['status']!='approved':
            queue.append({
                'object_id':o['object_id'],
                'object_version':o['object_version'],
                'text':o['content']['clean_text'],
                'risk_fields':o['risk']['risk_fields'],
                'first_reviewer':g['validated_by'],
                'first_review_date':g['validation_date'],
                'review_snapshot_hash':g['review_snapshot_hash'],
                'reviewed_canonical_object_hash':o['provenance']['canonical_object_hash'],
                'second_review_decision':'',
                'second_reviewer':'',
                'second_review_date':'',
                'comment':''
            })
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(queue,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'queue_count':len(queue)},indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
