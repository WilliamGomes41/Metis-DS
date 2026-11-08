#!/usr/bin/env python3
"""Strict first-line clinical or technical review for Protocol v2.1.

A decision is valid only for the exact canonical object hash supplied to the
reviewer. This module never applies proposed corrections in place.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any
from src.integrity_kernel import exact_review_snapshot_hash, schema_errors, stamp_canonical_hashes
from src.review.review_ledger import append_event

ALLOWED={"approve","revise","reject"}

def _apply_review_state(objects:list[dict[str,Any]], decisions:list[dict[str,Any]], *, track:str, schema_path:Path,
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
        elif decision=='revise':
            g['validation_status']='needs_review'; stats['revise']+=1
        else:
            g['validation_status']='rejected'; stats['rejected']+=1
        # Governance mutation must not change canonical content hash.
        stamp_canonical_hashes(o)
        serr=schema_errors(o,schema_path)
        if serr: errors.append({'object_id':o['object_id'],'error':'schema_error_after_review','details':serr})
        if ledger_path:
            details={'review_snapshot_hash':current,'comment':comment,'proposed_correction':correction}
            interaction=d.get('review_interaction')
            if isinstance(interaction,dict):
                details['review_interaction']=deepcopy(interaction)
                details['snapshot_id']=str(interaction.get('snapshot_id') or '')
            append_event(ledger_path,event_type=f'{track}_review_{decision}',object_id=o['object_id'],object_version=o['object_version'],actor=reviewer,
                         details=details)
        out.append(o)
    extras=sorted(set(by)-{o['object_id'] for o in objects})
    if extras: errors.append({'error':'review_rows_without_object','object_ids':extras})
    report={'track':track,'input_objects':len(objects),'decision_rows':len(decisions),'stats':stats,'errors':errors,
            'complete':stats['pending']==0 and stats['snapshot_mismatch']==0 and not errors}
    return out,report

