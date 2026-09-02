#!/usr/bin/env python3
"""Coordinate-preserving deterministic PDF extraction for Protocol v2.1."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any
import fitz
from src.integrity_kernel import stable_hash, schema_errors

PARSER_VERSION='pdf-fragments-v2.1.0'

def clean_text(text:str)->str:
    text=text.replace('\u00ad','')
    text=re.sub(r'(?<=\w)-\n(?=\w)','',text)
    text=re.sub(r'[ \t]+\n','\n',text)
    text=re.sub(r'\n{3,}','\n\n',text)
    return text.strip()

def style(block:dict[str,Any])->tuple[float,bool]:
    sizes=[]; bold=False
    for line in block.get('lines',[]):
        for span in line.get('spans',[]):
            if span.get('text','').strip():
                sizes.append(float(span.get('size',0))); f=str(span.get('font','')).lower(); bold=bold or 'bold' in f or 'semibold' in f
    return (max(sizes) if sizes else 0.0,bold)

def classify(text:str,max_size:float,bold:bool)->str:
    t=text.strip()
    if t in {'DOEN','OVERWEEG','AFRADEN','NIET DOEN'}: return 'stamp'
    if max_size>=16 or (bold and max_size>=13 and len(t)<120): return 'section'
    return 'content'

def fragment_payload(x:dict[str,Any])->dict[str,Any]:
    return {k:x[k] for k in ['fragment_id','document_id','source_id','source_page','bbox','source_locator','raw_text','clean_text','section_path','heading','sequence','parser_version']}

def page_bbox_locator(page_no:int,bbox:list[float])->dict[str,str]:
    coordinates=','.join(f'{value:.6f}' for value in bbox)
    return {'locator_type':'page_bbox','locator_value':f'page:{page_no};bbox:{coordinates}'}

def extract(pdf:Path, *, document_id:str, source_id:str, pages:list[int]|None=None)->list[dict[str,Any]]:
    doc=fitz.open(pdf); selected=pages or list(range(1,len(doc)+1)); out=[]; stack=[]; seq=0
    for page_no in selected:
        page=doc[page_no-1]; height=page.rect.height
        data=page.get_text('dict')
        for block in data.get('blocks',[]):
            if block.get('type')!=0: continue
            lines=[''.join(span.get('text','') for span in line.get('spans',[])) for line in block.get('lines',[])]
            raw='\n'.join(lines).strip()
            if not raw: continue
            c=clean_text(raw); bbox=[float(v) for v in block.get('bbox',[0,0,0,0])]
            if bbox[1]>height-55 and re.fullmatch(r'\d+',c): continue
            if c==str(page_no): continue
            max_size,bold=style(block); kind=classify(c,max_size,bold); heading=None
            if kind=='section':
                heading=c.replace('\n',' ').strip()
                if max_size>=20: stack=[heading]
                elif max_size>=15: stack=stack[:1]+[heading] if stack else [heading]
                else: stack=stack+[heading]
                path=stack.copy()
            else: path=stack.copy()
            seq+=1; fid=f'{document_id}-p{page_no:03d}-f{seq:03d}'
            x={'fragment_id':fid,'document_id':document_id,'source_id':source_id,'source_page':page_no,'bbox':bbox,'source_locator':page_bbox_locator(page_no,bbox),'raw_text':raw,'clean_text':c,'section_path':path,'heading':heading,'sequence':seq,'parser_version':PARSER_VERSION,'fragment_hash':'0'*64}
            x['fragment_hash']=stable_hash(fragment_payload(x)); out.append(x)
    return out

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('pdf',type=Path); ap.add_argument('--document-id',required=True); ap.add_argument('--source-id',required=True); ap.add_argument('--pages'); ap.add_argument('--schema',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--report',type=Path,required=True)
    a=ap.parse_args(); pages=[int(x) for x in a.pages.split(',')] if a.pages else None; rows=extract(a.pdf,document_id=a.document_id,source_id=a.source_id,pages=pages)
    errs=[]
    for r in rows:
        for e in schema_errors(r,a.schema): errs.append({'fragment_id':r['fragment_id'],'error':e})
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows),encoding='utf-8')
    rep={'parser_version':PARSER_VERSION,'fragment_count':len(rows),'schema_valid':not errs,'schema_errors':errs,'coordinates':'captured'}; a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(rep,ensure_ascii=False,indent=2)); return 0 if not errs else 2
if __name__=='__main__': raise SystemExit(main())
