#!/usr/bin/env python3
"""Protocol-v2 heavy pre-publication gate.

This gate does not publish anything. It proves that canonical candidates satisfy
source, meaning and governance constraints before a release can be created.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from jsonschema import Draft202012Validator


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--schema', type=Path, required=True)
    ap.add_argument('--source-manifest', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args=ap.parse_args()

    rows=read_jsonl(args.input)
    schema=json.loads(args.schema.read_text(encoding='utf-8'))
    manifest=json.loads(args.source_manifest.read_text(encoding='utf-8'))
    validator=Draft202012Validator(schema)
    ids={o['object_id'] for o in rows}
    errors=[]

    schema_errors=[]
    for o in rows:
        errs=[e.message for e in validator.iter_errors(o)]
        if errs:
            schema_errors.append({'object_id':o.get('object_id'),'errors':errs})
    if schema_errors: errors.append({'error':'schema_invalid','details':schema_errors})

    if manifest['canonical_source'].get('integrity_status')!='verified' or not manifest['canonical_source'].get('source_checksum'):
        errors.append({'error':'canonical_source_not_hash_verified','integrity_status':manifest['canonical_source'].get('integrity_status')})

    for o in rows:
        oid=o['object_id']; g=o['governance']; risk=o['risk']; prov=o['provenance']
        if o.get('parent_object_id') and o['parent_object_id'] not in ids:
            errors.append({'object_id':oid,'error':'missing_parent_target'})
        for rel in o.get('relations',[]):
            if rel['target_object_id'] not in ids:
                errors.append({'object_id':oid,'error':'missing_relation_target','target':rel['target_object_id']})
        if g['publication_status']!='unpublished':
            errors.append({'object_id':oid,'error':'prepublication_input_already_published'})
        if prov.get('proposal_id') is not None or prov.get('transformation_mode')!='deterministic':
            errors.append({'object_id':oid,'error':'non_deterministic_or_proposal_in_canonical'})

        # Every object intended for the release must have a final review state.
        if g['validation_status'] in {'draft','needs_review','revise'}:
            errors.append({'object_id':oid,'error':'review_not_final','status':g['validation_status'],'track':g['review_track']})
        if g['validation_status']=='approved':
            if not g.get('validated_by') or not g.get('validation_date') or not g.get('review_snapshot_hash'):
                errors.append({'object_id':oid,'error':'approval_metadata_incomplete'})
            if g.get('validated_by') == prov.get('created_by'):
                errors.append({'object_id':oid,'error':'reviewer_must_differ_from_creator'})
            if o['uncertainty']['has_uncertainty']:
                errors.append({'object_id':oid,'error':'approved_object_has_unresolved_uncertainty'})
            if o['source'].get('integrity_status')!='verified' or not o['source'].get('source_checksum'):
                errors.append({'object_id':oid,'error':'approved_object_source_not_hash_verified'})
            if risk['requires_second_review']:
                sr=g['second_review']
                if sr['status']!='approved' or not sr.get('reviewer') or not sr.get('review_date') or not sr.get('snapshot_hash'):
                    errors.append({'object_id':oid,'error':'second_review_incomplete','risk_fields':risk['risk_fields']})
                elif sr['reviewer']==g.get('validated_by'):
                    errors.append({'object_id':oid,'error':'second_reviewer_must_differ_from_first'})
        elif g['validation_status']=='rejected':
            # Rejected objects are retained in audit history, not eligible for publication.
            pass
        elif g['validation_status']=='superseded':
            pass

    approved=[o for o in rows if o['governance']['validation_status']=='approved']
    publishable=[o for o in approved if not any(e.get('object_id')==o['object_id'] for e in errors)]
    status='PASS' if not errors else 'BLOCKED'
    report={
        'gate':'protocol_v2_prepublication',
        'status':status,
        'input_objects':len(rows),
        'approved_objects':len(approved),
        'publishable_objects':len(publishable),
        'high_risk_objects':sum(1 for o in rows if o['risk']['requires_second_review']),
        'canonical_source_integrity_status':manifest['canonical_source'].get('integrity_status'),
        'errors':errors,
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if status=='PASS' else 2

if __name__=='__main__': raise SystemExit(main())
