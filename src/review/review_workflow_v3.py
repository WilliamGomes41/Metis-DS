#!/usr/bin/env python3
"""Strict first-line clinical or technical review for Protocol v2.1.

A decision is valid only for the exact canonical object hash supplied to the
reviewer. This module never applies proposed corrections in place.
"""
from __future__ import annotations
import argparse, json
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any
from src.integrity_kernel import exact_review_snapshot_hash, schema_errors, stamp_canonical_hashes
from src.review_ledger import append_event

ALLOWED={"approve","revise","reject"}

def read_jsonl(p:Path)->list[dict[str,Any]]:
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def write_jsonl(p:Path,rows:list[dict[str,Any]])->None:
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows),encoding='utf-8')

def apply_reviews(objects:list[dict[str,Any]], decisions:list[dict[str,Any]], *, track:str, schema_path:Path,
                  ledger_path:Path|None=None)->tuple[list[dict[str,Any]],dict[str,Any]]:
    by={d['object_id']:d for d in decisions}; out=[]; errors=[]; stats={"approved":0,"revise":0,"rejected":0,"pending":0,"snapshot_mismatch":0}
    for original in objects:
        o=deepcopy(original); g=o['governance']
        if g['review_track']!=track:
            out.append(o); continue
        d=by.get(o['object_id'])
        if not d or not str(d.get('decision','')).strip():
            stats['pending']+=1; out.append(o); continue
        decision=str(d['decision']).strip().lower()
        if decision not in ALLOWED:
            errors.append({'object_id':o['object_id'],'error':'invalid_decision'}); out.append(o); continue
        reviewer=str(d.get('reviewer','')).strip(); rdate=str(d.get('review_date') or date.today()).strip()
        if not reviewer:
            errors.append({'object_id':o['object_id'],'error':'reviewer_required'}); out.append(o); continue
        seen=str(d.get('reviewed_canonical_object_hash','')).strip().lower(); current=exact_review_snapshot_hash(o)
        if seen != current:
            stats['snapshot_mismatch']+=1; errors.append({'object_id':o['object_id'],'error':'review_snapshot_mismatch','reviewed':seen,'current':current}); out.append(o); continue
        comment=str(d.get('comment','')).strip(); correction=str(d.get('proposed_correction','')).strip()
        if decision=='revise' and not (comment or correction):
            errors.append({'object_id':o['object_id'],'error':'revise_requires_comment_or_correction'}); out.append(o); continue
        if decision=='reject' and not comment:
            errors.append({'object_id':o['object_id'],'error':'reject_requires_comment'}); out.append(o); continue
        g['validated_by']=reviewer; g['validation_date']=rdate; g['review_snapshot_hash']=current
        if decision=='approve':
            g['validation_status']='approved'; stats['approved']+=1
            if o['risk']['requires_second_review']: g['second_review']['status']='pending'
        elif decision=='revise':
            g['validation_status']='revise'; stats['revise']+=1
        else:
            g['validation_status']='rejected'; stats['rejected']+=1
        # Governance mutation must not change canonical content hash.
        stamp_canonical_hashes(o)
        serr=schema_errors(o,schema_path)
        if serr: errors.append({'object_id':o['object_id'],'error':'schema_error_after_review','details':serr})
        if ledger_path:
            append_event(ledger_path,event_type=f'{track}_review_{decision}',object_id=o['object_id'],object_version=o['object_version'],actor=reviewer,
                         details={'review_snapshot_hash':current,'comment':comment,'proposed_correction':correction})
        out.append(o)
    extras=sorted(set(by)-{o['object_id'] for o in objects})
    if extras: errors.append({'error':'review_rows_without_object','object_ids':extras})
    report={'track':track,'input_objects':len(objects),'decision_rows':len(decisions),'stats':stats,'errors':errors,
            'complete':stats['pending']==0 and stats['snapshot_mismatch']==0 and not errors}
    return out,report

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,required=True); ap.add_argument('--decisions',type=Path,required=True)
    ap.add_argument('--track',choices=['clinical','technical'],required=True); ap.add_argument('--schema',type=Path,required=True); ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True); ap.add_argument('--ledger',type=Path)
    a=ap.parse_args(); objs=read_jsonl(a.input); ds=read_jsonl(a.decisions); out,rep=apply_reviews(objs,ds,track=a.track,schema_path=a.schema,ledger_path=a.ledger)
    write_jsonl(a.out,out); a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(rep,ensure_ascii=False,indent=2)); return 0 if rep['complete'] else 2
if __name__=='__main__': raise SystemExit(main())
