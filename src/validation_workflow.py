#!/usr/bin/env python3
import argparse, csv, json, hashlib
from pathlib import Path
from datetime import date
from jsonschema import Draft202012Validator

ALLOWED_DECISIONS = {"approve", "reject", "revise", ""}

def load_jsonl(path):
    rows=[]
    with open(path, encoding='utf-8') as f:
        for line in f:
            if line.strip(): rows.append(json.loads(line))
    return rows

def save_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path,'w',encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False)+"\n")

def load_reviews(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f, delimiter=';')
        return {r['object_id']: r for r in reader}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--review', required=True)
    p.add_argument('--schema', required=True)
    p.add_argument('--approved-out', required=True)
    p.add_argument('--rejected-out', required=True)
    p.add_argument('--pending-out', required=True)
    p.add_argument('--report', required=True)
    p.add_argument('--validator', required=True)
    p.add_argument('--validation-date', default=str(date.today()))
    args=p.parse_args()

    objects=load_jsonl(args.input)
    reviews=load_reviews(args.review)
    schema=json.load(open(args.schema, encoding='utf-8'))
    validator=Draft202012Validator(schema)

    approved=[]; rejected=[]; pending=[]; errors=[]
    seen=set()
    for obj in objects:
        oid=obj['object_id']; seen.add(oid)
        r=reviews.get(oid)
        if not r:
            pending.append(obj); errors.append({'object_id':oid,'error':'missing_review_row'}); continue
        decision=(r.get('review_decision') or '').strip().lower()
        comment=(r.get('review_comment') or '').strip()
        if decision not in ALLOWED_DECISIONS:
            pending.append(obj); errors.append({'object_id':oid,'error':f'invalid_decision:{decision}'}); continue
        if decision == 'approve':
            x=json.loads(json.dumps(obj))
            x['governance']['validation_status']='approved'
            x['governance']['validated_by']=args.validator
            x['governance']['validation_date']=args.validation_date
            x['technical']['content_hash']=hashlib.sha256(x['content']['clean_text'].encode('utf-8')).hexdigest()
            verr=[e.message for e in validator.iter_errors(x)]
            if verr:
                pending.append(obj); errors.append({'object_id':oid,'error':'schema_error_after_approval','details':verr}); continue
            approved.append(x)
        elif decision == 'reject':
            if not comment:
                pending.append(obj); errors.append({'object_id':oid,'error':'reject_requires_comment'}); continue
            x=json.loads(json.dumps(obj)); x['governance']['validation_status']='rejected'; x['governance']['validated_by']=args.validator; x['governance']['validation_date']=args.validation_date
            rejected.append(x)
        else:
            pending.append(obj)

    extra=[oid for oid in reviews if oid not in seen]
    if extra: errors.append({'error':'review_rows_without_object','object_ids':extra})

    save_jsonl(args.approved_out, approved); save_jsonl(args.rejected_out,rejected); save_jsonl(args.pending_out,pending)
    report={'input_objects':len(objects),'approved':len(approved),'rejected':len(rejected),'pending_or_revise':len(pending),'errors':errors,'validator':args.validator,'validation_date':args.validation_date,'all_reviewed':len(pending)==0 and not errors}
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    json.dump(report, open(args.report,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__=='__main__': main()
