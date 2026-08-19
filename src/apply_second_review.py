#!/usr/bin/env python3
"""Apply four-eyes review to already first-approved high-risk objects."""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from typing import Any
try:
    from src.integrity_kernel import exact_review_snapshot_hash
except ModuleNotFoundError:  # direct script compatibility
    from integrity_kernel import exact_review_snapshot_hash

ALLOWED={'approve','reject'}


def read_jsonl(path: Path)->list[dict[str,Any]]:
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]


def write_jsonl(path: Path, rows:list[dict[str,Any]])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows),encoding='utf-8')


def read_csv(path: Path)->dict[str,dict[str,str]]:
    with path.open(encoding='utf-8-sig',newline='') as f:
        rs=list(csv.DictReader(f,delimiter=';'))
    return {r['object_id'].strip():r for r in rs if r.get('object_id','').strip()}


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--review',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True)
    args=ap.parse_args()
    rows=read_jsonl(args.input); reviews=read_csv(args.review); errors=[]; approved=0; rejected=0
    for o in rows:
        if not (o['governance']['validation_status']=='approved' and o['risk']['requires_second_review']):
            continue
        r=reviews.get(o['object_id'])
        if not r or not (r.get('second_review_decision') or '').strip():
            continue
        decision=r['second_review_decision'].strip().lower()
        if decision not in ALLOWED:
            errors.append({'object_id':o['object_id'],'error':'invalid_second_review_decision'}); continue
        reviewer=(r.get('second_reviewer') or '').strip(); review_date=(r.get('second_review_date') or '').strip()
        seen_hash=(r.get('reviewed_canonical_object_hash') or r.get('reviewed_content_hash') or '').strip()
        if not reviewer or not review_date:
            errors.append({'object_id':o['object_id'],'error':'missing_second_reviewer_or_date'}); continue
        if reviewer==o['governance'].get('validated_by'):
            errors.append({'object_id':o['object_id'],'error':'second_reviewer_must_differ_from_first'}); continue
        if seen_hash != exact_review_snapshot_hash(o):
            errors.append({'object_id':o['object_id'],'error':'second_review_snapshot_mismatch'}); continue
        sr=o['governance']['second_review']
        sr['reviewer']=reviewer; sr['review_date']=review_date; sr['snapshot_hash']=seen_hash
        if decision=='approve':
            sr['status']='approved'; approved+=1
        else:
            sr['status']='rejected'; o['governance']['validation_status']='revise'; rejected+=1
    write_jsonl(args.out,rows)
    report={'second_review_approved':approved,'second_review_rejected_to_revise':rejected,'errors':errors}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if not errors else 2

if __name__=='__main__': raise SystemExit(main())
