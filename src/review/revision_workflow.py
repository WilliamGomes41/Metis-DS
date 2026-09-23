#!/usr/bin/env python3
"""Create a new immutable object version from an explicit reviewed revision patch."""
from __future__ import annotations
import argparse, json, re
from copy import deepcopy
from pathlib import Path
from typing import Any
from src.integrity_kernel import stable_hash, stamp_canonical_hashes, schema_errors
from src.review_ledger import append_event

ALLOWED_ROOTS={'content','logic','relations','risk','uncertainty','structure','decision_graph'}

def bump_patch(v:str)->str:
    m=re.fullmatch(r'(\d+)\.(\d+)(?:\.(\d+))?',v)
    if not m: raise ValueError('object_version_must_be_semver_like')
    major,minor,patch=int(m.group(1)),int(m.group(2)),int(m.group(3) or 0)
    return f'{major}.{minor}.{patch+1}'

def set_path(obj:dict[str,Any], path:str, value:Any)->None:
    parts=path.split('.')
    if not parts or parts[0] not in ALLOWED_ROOTS: raise ValueError(f'patch_path_not_allowed:{path}')
    cur:Any=obj
    for key in parts[:-1]:
        if isinstance(cur,dict) and key in cur: cur=cur[key]
        else: raise ValueError(f'patch_path_missing:{path}')
    if not isinstance(cur,dict): raise ValueError(f'patch_parent_not_object:{path}')
    cur[parts[-1]]=value

def create_revision(obj:dict[str,Any], patch:dict[str,Any], *, actor:str, schema_path:Path, ledger:Path|None=None)->dict[str,Any]:
    if obj['governance']['validation_status']!='revise': raise ValueError('source_object_not_in_revise_state')
    if not patch.get('reason'): raise ValueError('revision_reason_required')
    ops=patch.get('operations') or []
    if not ops: raise ValueError('revision_operations_required')
    x=deepcopy(obj); previous=x['object_version']; x['object_version']=patch.get('new_object_version') or bump_patch(previous)
    for op in ops:
        if op.get('op')!='set': raise ValueError('only_set_operation_supported')
        set_path(x,op['path'],op.get('value'))
    g=x['governance']; g['validation_status']='needs_review'; g['validated_by']=None; g['validation_date']=None; g['review_snapshot_hash']=None
    g['publication_status']='unpublished'; g['second_review']={'required':x['risk']['requires_second_review'],'status':'pending' if x['risk']['requires_second_review'] else 'not_required','reviewer':None,'review_date':None,'snapshot_hash':None}
    p=x['provenance']; p['previous_object_version']=previous; p['revision_reason']=patch['reason']; p['revision_patch_hash']=stable_hash(patch)
    stamp_canonical_hashes(x)
    errs=schema_errors(x,schema_path)
    if errs: raise ValueError('revision_schema_invalid:'+' | '.join(errs))
    if ledger: append_event(ledger,event_type='revision_created',object_id=x['object_id'],object_version=x['object_version'],actor=actor,
                            details={'previous_object_version':previous,'revision_patch_hash':p['revision_patch_hash'],'reason':patch['reason']})
    return x

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--object',type=Path,required=True); ap.add_argument('--patch',type=Path,required=True); ap.add_argument('--schema',type=Path,required=True)
    ap.add_argument('--actor',required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--ledger',type=Path)
    a=ap.parse_args(); obj=json.loads(a.object.read_text()); patch=json.loads(a.patch.read_text()); x=create_revision(obj,patch,actor=a.actor,schema_path=a.schema,ledger=a.ledger)
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'status':'PASS','object_id':x['object_id'],'object_version':x['object_version']},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
