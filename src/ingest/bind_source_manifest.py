#!/usr/bin/env python3
"""Bind a cryptographically verified source-registry record into a new source manifest."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any
from src.integrity_kernel import load_verified_source_registry, sha256_file

def bind(manifest:dict[str,Any], registry_path:Path)->dict[str,Any]:
    verified=load_verified_source_registry(registry_path)
    src=manifest['canonical_source']; sid=src['source_id']
    checksum=verified.get(sid)
    if not checksum: raise ValueError('source_id_not_verified_in_registry')
    registry=json.loads(registry_path.read_text(encoding='utf-8'))
    rec=next(x for x in registry.get('sources',[]) if x.get('source_id')==sid and x.get('source_checksum')==checksum)
    out=json.loads(json.dumps(manifest)); s=out['canonical_source']
    s['source_checksum']=checksum; s['integrity_status']='verified'; s['binary_path']=rec['binary_path']; s['verification_method']='binary_sha256_verified'; s['publication_eligibility']='eligible_for_transform_and_review'
    old=str(out.get('manifest_version','2.0')); out['previous_manifest_version']=old; out['manifest_version']='2.1'
    return out

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--manifest',type=Path,required=True); ap.add_argument('--source-registry',type=Path,required=True); ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args(); out=bind(json.loads(a.manifest.read_text(encoding='utf-8')),a.source_registry); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'status':'PASS','source_id':out['canonical_source']['source_id'],'source_checksum':out['canonical_source']['source_checksum'],'out':str(a.out)},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
