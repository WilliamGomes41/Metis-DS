#!/usr/bin/env python3
"""Strict four-eyes review bound to the exact canonical object hash."""
from __future__ import annotations
import argparse,json
from copy import deepcopy
from pathlib import Path
from typing import Any
from src.integrity_kernel import exact_review_snapshot_hash
from src.review_ledger import append_event


def read_jsonl(p:Path)->list[dict[str,Any]]:
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]

def apply_second(rows:list[dict[str,Any]], decisions:list[dict[str,Any]], ledger:Path|None=None)->tuple[list[dict[str,Any]],dict[str,Any]]:
    by={x['object_id']:x for x in decisions}; out=[]; errors=[]; stats={'approved':0,'rejected_to_revise':0,'pending':0,'snapshot_mismatch':0}
    for original in rows:
        o=deepcopy(original); g=o['governance']; sr=g['second_review']
        if not (g['validation_status']=='approved' and o['risk']['requires_second_review']): out.append(o); continue
        d=by.get(o['object_id'])
        if not d or not str(d.get('decision','')).strip(): stats['pending']+=1; out.append(o); continue
        decision=str(d['decision']).lower().strip(); reviewer=str(d.get('reviewer','')).strip(); rdate=str(d.get('review_date','')).strip(); comment=str(d.get('comment','')).strip()
        if decision not in {'approve','reject'}: errors.append({'object_id':o['object_id'],'error':'invalid_second_review_decision'}); out.append(o); continue
        if not reviewer or not rdate: errors.append({'object_id':o['object_id'],'error':'second_reviewer_date_required'}); out.append(o); continue
        if reviewer==g.get('validated_by'): errors.append({'object_id':o['object_id'],'error':'second_reviewer_must_differ'}); out.append(o); continue
        current=exact_review_snapshot_hash(o); seen=str(d.get('reviewed_canonical_object_hash','')).strip().lower()
        if seen!=current: stats['snapshot_mismatch']+=1; errors.append({'object_id':o['object_id'],'error':'second_review_snapshot_mismatch'}); out.append(o); continue
        sr.update({'reviewer':reviewer,'review_date':rdate,'snapshot_hash':current})
        if decision=='approve': sr['status']='approved'; stats['approved']+=1
        else:
            if not comment: errors.append({'object_id':o['object_id'],'error':'second_reject_requires_comment'}); out.append(original); continue
            sr['status']='rejected'; g['validation_status']='revise'; stats['rejected_to_revise']+=1
        if ledger: append_event(ledger,event_type=f'second_review_{decision}',object_id=o['object_id'],object_version=o['object_version'],actor=reviewer,details={'review_snapshot_hash':current,'comment':comment})
        out.append(o)
    return out,{'stats':stats,'errors':errors,'complete':stats['pending']==0 and stats['snapshot_mismatch']==0 and not errors}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,required=True); ap.add_argument('--decisions',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--report',type=Path,required=True); ap.add_argument('--ledger',type=Path)
    a=ap.parse_args(); out,rep=apply_second(read_jsonl(a.input),read_jsonl(a.decisions),a.ledger); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in out),encoding='utf-8'); a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(rep,ensure_ascii=False,indent=2)); return 0 if rep['complete'] else 2
if __name__=='__main__': raise SystemExit(main())
