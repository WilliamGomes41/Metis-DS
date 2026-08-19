#!/usr/bin/env python3
"""Reconcile legacy first reviews to Protocol v2.1 exact-object snapshots.

Use only for reviews collected before exact canonical-object hashes were included
in the review package. A named reconciler must explicitly attest each current
canonical object hash; no silent migration is allowed.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
from src.integrity_kernel import exact_review_snapshot_hash
from src.review_ledger import append_event

def read_jsonl(p:Path)->list[dict[str,Any]]:
 return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def main()->int:
 ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,required=True); ap.add_argument('--attestations',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--report',type=Path,required=True); ap.add_argument('--ledger',type=Path)
 a=ap.parse_args(); rows=read_jsonl(a.input); at={x['object_id']:x for x in read_jsonl(a.attestations)}; errors=[]; reconciled=0
 for o in rows:
  g=o['governance']
  if g.get('validation_status')!='approved': continue
  current=exact_review_snapshot_hash(o)
  if g.get('review_snapshot_hash')==current: continue
  d=at.get(o['object_id'])
  if not d: errors.append({'object_id':o['object_id'],'error':'reconciliation_attestation_missing'}); continue
  if d.get('current_canonical_object_hash')!=current: errors.append({'object_id':o['object_id'],'error':'reconciliation_hash_mismatch'}); continue
  reconciler=str(d.get('reconciler','')).strip(); rdate=str(d.get('reconciliation_date','')).strip(); comment=str(d.get('comment','')).strip()
  if not reconciler or not rdate or not comment: errors.append({'object_id':o['object_id'],'error':'reconciler_date_comment_required'}); continue
  g['review_snapshot_hash']=current; reconciled+=1
  if a.ledger: append_event(a.ledger,event_type='legacy_review_reconciled',object_id=o['object_id'],object_version=o['object_version'],actor=reconciler,details={'canonical_object_hash':current,'comment':comment})
 a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows),encoding='utf-8')
 rep={'reconciled':reconciled,'errors':errors,'status':'PASS' if not errors else 'BLOCKED'}; a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(rep,ensure_ascii=False,indent=2)); return 0 if not errors else 2
if __name__=='__main__': raise SystemExit(main())
