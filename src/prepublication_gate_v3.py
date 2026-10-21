#!/usr/bin/env python3
"""Protocol v2.1 pre-publication gate using the central integrity kernel."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
from src.eligibility_policy import publication_errors
from src.integrity_kernel import load_raw_objects, load_verified_source_registry, validate_parent_relations


def read_jsonl(path:Path)->list[dict[str,Any]]:
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]

def evaluate(rows:list[dict[str,Any]], *, schema:Path, source_registry:Path, raw_extract:Path)->dict[str,Any]:
    verified=load_verified_source_registry(source_registry); raw=load_raw_objects(raw_extract)
    errors=[]; eligible=[]; excluded=[]
    relation_errors=validate_parent_relations(rows)
    for e in relation_errors: errors.append({'error':e})
    for o in rows:
        status=(o.get('governance') or {}).get('validation_status')
        if status in {'rejected','superseded'}:
            excluded.append({'object_id':o['object_id'],'status':status}); continue
        errs=publication_errors(o,schema_path=schema,verified_sources=verified,raw_objects=raw)
        if errs: errors.append({'object_id':o.get('object_id'),'errors':errs})
        else: eligible.append(o['object_id'])
    active=[o for o in rows if (o.get('governance') or {}).get('validation_status') not in {'rejected','superseded'}]
    status='PASS' if not errors and len(eligible)==len(active) else 'BLOCKED'
    return {'status':status,'input_objects':len(rows),'active_objects':len(active),'eligible_objects':len(eligible),'excluded_objects':excluded,
            'verified_source_count':len(verified),'errors':errors}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,required=True); ap.add_argument('--schema',type=Path,required=True)
    ap.add_argument('--source-registry',type=Path,required=True); ap.add_argument('--raw-extract',type=Path,required=True); ap.add_argument('--report',type=Path,required=True)
    a=ap.parse_args(); rep=evaluate(read_jsonl(a.input),schema=a.schema,source_registry=a.source_registry,raw_extract=a.raw_extract)
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(rep,ensure_ascii=False,indent=2)); return 0 if rep['status']=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
