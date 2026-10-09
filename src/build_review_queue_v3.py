#!/usr/bin/env python3
"""Build strict clinical/technical review queue bound to exact canonical object hashes."""
from __future__ import annotations

from src.source_representation_v1 import preserve_fragments
import argparse, json
from pathlib import Path
from typing import Any
from src.integrity_kernel import exact_review_snapshot_hash
from src.review_duty_v1 import review_duty_for

def read_jsonl(p:Path)->list[dict[str,Any]]:
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]

def build(rows:list[dict[str,Any]], track:str, *, review_path="richtlijn", bindings=(), fragments=None)->list[dict[str,Any]]:
    bindings=tuple(bindings)
    fragments=preserve_fragments(fragments) if fragments is not None else None
    q=[]
    for o in rows:
        duty=review_duty_for(o, review_path=review_path, bindings=bindings, fragments=fragments)
        if not duty:
            continue
        if o['governance']['review_track']!=track: continue
        q.append({
          'object_id':o['object_id'],'object_version':o['object_version'],'review_track':track,
          'reviewed_canonical_object_hash':exact_review_snapshot_hash(o),
          'text':o['content']['clean_text'],'object_type':o['object_type'],'risk_fields':o['risk']['risk_fields'],
          'source_id':o['source']['source_id'],'source_page':o['source']['source_page'],
          'source_fragments':o['provenance']['source_fragments'],
          'decision':'','reviewer':'','review_date':'','proposed_correction':'','comment':''
        })
    return q

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,required=True); ap.add_argument('--track',choices=['clinical','technical'],required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--raw-extract',type=Path,required=True); ap.add_argument('--bindings',type=Path,required=True); ap.add_argument('--review-path',choices=['richtlijn','boom'],default='richtlijn')
    a=ap.parse_args(); q=build(read_jsonl(a.input),a.track, review_path=a.review_path, bindings=read_jsonl(a.bindings), fragments=read_jsonl(a.raw_extract)); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in q),encoding='utf-8'); print(json.dumps({'track':a.track,'queue_count':len(q)},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
