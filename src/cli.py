#!/usr/bin/env python3
"""Authoritative CLI for the V&VN Data Services pilot."""
from __future__ import annotations
import argparse, json
from pathlib import Path

import os

from src.build_review_queue_v3 import build as build_review_queue, read_jsonl
from src.prepublication_gate_v3 import evaluate as evaluate_prepublication
from src.source_registry import register_source
from src.bind_source_manifest import bind as bind_source_manifest
from src.extract_html_v1 import extract as extract_html, validate as validate_html_raw
from src.semantic_transform_generic_v1 import transform as transform_generic, validate as validate_generic_objects, load_jsonl as load_generic_jsonl

ROOT = Path(__file__).resolve().parents[1]


def write_jsonl(path:Path, rows:list[dict])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows),encoding='utf-8')


def cmd_review_queue(a:argparse.Namespace)->dict:
    rows=read_jsonl(a.input); queue=build_review_queue(rows,a.track); write_jsonl(a.out,queue)
    return {'status':'PASS','track':a.track,'queue_count':len(queue),'out':str(a.out)}


def cmd_source_register(a:argparse.Namespace)->dict:
    rec=register_source(a.source_id,a.binary,a.source_url,a.version)
    data={'registry_version':'1.0','sources':[rec]}; a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'status':'PASS','source_id':a.source_id,'source_checksum':rec['source_checksum'],'out':str(a.out)}



def cmd_source_bind(a:argparse.Namespace)->dict:
    manifest=json.loads(a.manifest.read_text(encoding='utf-8')); out=bind_source_manifest(manifest,a.source_registry)
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'status':'PASS','source_id':out['canonical_source']['source_id'],'source_checksum':out['canonical_source']['source_checksum'],'out':str(a.out)}


def cmd_extract_html(a: argparse.Namespace) -> dict:
    rows = extract_html(a.input, document_id=a.document_id, source_id=a.source_id)
    errors = validate_html_raw(rows, a.schema)
    write_jsonl(a.out, rows)
    return {
        "status": "PASS" if rows and not errors else "BLOCKED",
        "fragment_count": len(rows),
        "schema_errors": errors,
        "out": str(a.out),
    }


def cmd_semantic_generic(a: argparse.Namespace) -> dict:
    spec = json.loads(a.spec.read_text(encoding="utf-8"))
    manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
    raw = load_generic_jsonl(a.raw)
    rows = transform_generic(spec, manifest, raw)
    errors = validate_generic_objects(rows, a.schema)
    write_jsonl(a.out, rows)
    return {
        "status": "PASS" if rows and not errors else "BLOCKED",
        "object_count": len(rows),
        "schema_errors": errors,
        "out": str(a.out),
    }

def cmd_prepublish(a:argparse.Namespace)->dict:
    return evaluate_prepublication(read_jsonl(a.input),schema=a.schema,source_registry=a.source_registry,raw_extract=a.raw_extract)


def cmd_audit_current(a:argparse.Namespace)->dict:
    from src.integrity_kernel import load_raw_objects, schema_errors, validate_hashes, validate_source_fragments, validate_parent_relations
    rows=read_jsonl(a.input); raw=load_raw_objects(a.raw_extract)
    object_errors=[]
    for o in rows:
        e=schema_errors(o,a.schema)+validate_hashes(o)+validate_source_fragments(o,raw)
        if e: object_errors.append({'object_id':o['object_id'],'errors':e})
    relation_errors=validate_parent_relations(rows)
    pre=evaluate_prepublication(rows,schema=a.schema,source_registry=a.source_registry,raw_extract=a.raw_extract)
    integrity_ok=not object_errors and not relation_errors
    return {'status':'PASS' if integrity_ok else 'BLOCKED','integrity_ok':integrity_ok,'object_count':len(rows),'object_errors':object_errors,'relation_errors':relation_errors,
            'publication_gate':pre['status'],'publication_blocker_count':len(pre['errors'])}



def cmd_serve(a: argparse.Namespace) -> dict:
    import uvicorn
    from src.service_app import create_app
    os.environ["VVN_SERVICE_MODE"] = a.mode
    uvicorn.run(create_app(a.mode), host=a.host, port=a.port)
    return {"status": "PASS"}


def cmd_serve_api(a: argparse.Namespace) -> dict:
    import uvicorn
    from src.product_api_v1 import create_product_app
    uvicorn.run(create_product_app(a.mode, allow_fixture=(a.mode == "fixture")), host=a.host, port=a.port)
    return {"status": "PASS"}

def main()->int:
    ap=argparse.ArgumentParser(prog='vvn-data-service'); sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('audit-current'); p.add_argument('--input',type=Path,default=ROOT/'data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v21.jsonl'); p.add_argument('--schema',type=Path,default=ROOT/'schemas/knowledge_object.schema.v1.1.json'); p.add_argument('--source-registry',type=Path,default=ROOT/'data/source_registry.json'); p.add_argument('--raw-extract',type=Path,default=ROOT/'data/fixtures/baseline_v0_1/fractuurpreventie_page15_raw.jsonl'); p.add_argument('--report',type=Path)
    p=sub.add_parser('review-queue'); p.add_argument('--input',type=Path,required=True); p.add_argument('--track',choices=['clinical','technical'],required=True); p.add_argument('--out',type=Path,required=True); p.add_argument('--report',type=Path)
    p=sub.add_parser('source-register'); p.add_argument('--source-id',required=True); p.add_argument('--binary',type=Path,required=True); p.add_argument('--source-url',required=True); p.add_argument('--version'); p.add_argument('--out',type=Path,required=True); p.add_argument('--report',type=Path)
    p=sub.add_parser('source-bind'); p.add_argument('--manifest',type=Path,required=True); p.add_argument('--source-registry',type=Path,required=True); p.add_argument('--out',type=Path,required=True); p.add_argument('--report',type=Path)
    p=sub.add_parser('prepublish'); p.add_argument('--input',type=Path,required=True); p.add_argument('--schema',type=Path,required=True); p.add_argument('--source-registry',type=Path,required=True); p.add_argument('--raw-extract',type=Path,required=True); p.add_argument('--report',type=Path)
    p=sub.add_parser('extract-html'); p.add_argument('--input',type=Path,required=True); p.add_argument('--document-id',required=True); p.add_argument('--source-id',required=True); p.add_argument('--schema',type=Path,default=ROOT/'schemas/raw_fragment.schema.v1.1.json'); p.add_argument('--out',type=Path,required=True); p.add_argument('--report',type=Path)
    p=sub.add_parser('semantic-generic'); p.add_argument('--spec',type=Path,required=True); p.add_argument('--manifest',type=Path,required=True); p.add_argument('--raw',type=Path,required=True); p.add_argument('--schema',type=Path,default=ROOT/'schemas/knowledge_object.schema.v1.2.json'); p.add_argument('--out',type=Path,required=True); p.add_argument('--report',type=Path)
    p=sub.add_parser('serve'); p.add_argument('--mode',choices=['real','fixture'],default='real'); p.add_argument('--host',default='0.0.0.0'); p.add_argument('--port',type=int,default=8000)
    p=sub.add_parser('serve-api'); p.add_argument('--mode',choices=['real','fixture'],default='real'); p.add_argument('--host',default='0.0.0.0'); p.add_argument('--port',type=int,default=8080)
    a=ap.parse_args()
    try:
        if a.cmd=='audit-current': rep=cmd_audit_current(a)
        elif a.cmd=='review-queue': rep=cmd_review_queue(a)
        elif a.cmd=='source-register': rep=cmd_source_register(a)
        elif a.cmd=='source-bind': rep=cmd_source_bind(a)
        elif a.cmd=='prepublish': rep=cmd_prepublish(a)
        elif a.cmd=='extract-html': rep=cmd_extract_html(a)
        elif a.cmd=='semantic-generic': rep=cmd_semantic_generic(a)
        elif a.cmd=='serve': rep=cmd_serve(a)
        elif a.cmd=='serve-api': rep=cmd_serve_api(a)
        else: raise AssertionError(a.cmd)
    except Exception as exc:
        rep={'status':'BLOCKED','error':type(exc).__name__,'message':str(exc)}
    text=json.dumps(rep,ensure_ascii=False,indent=2)
    if getattr(a,'report',None): a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(text+'\n',encoding='utf-8')
    print(text); return 0 if rep.get('status')=='PASS' else 2
if __name__=='__main__': raise SystemExit(main())
