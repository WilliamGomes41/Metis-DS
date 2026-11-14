#!/usr/bin/env python3
"""Create a new immutable object version from an explicit reviewed revision patch."""
from __future__ import annotations
import argparse, json, re
from copy import deepcopy
from pathlib import Path
from typing import Any
from src.integrity_kernel import stable_hash, stamp_canonical_hashes, schema_errors
from src.review.review_ledger import append_event

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

def create_revision(obj:dict[str,Any], patch:dict[str,Any], *, actor:str, schema_path:Path, ledger:Path|None=None, snapshot_id:str|None=None)->dict[str,Any]:
    if obj['governance']['validation_status']!='revise': raise ValueError('source_object_not_in_revise_state')
    if not patch.get('reason'): raise ValueError('revision_reason_required')
    ops=patch.get('operations') or []
    if not ops: raise ValueError('revision_operations_required')
    x=deepcopy(obj); previous=x['object_version']; x['object_version']=patch.get('new_object_version') or bump_patch(previous)
    if _version(x['object_version']) <= _version(previous):
        raise ValueError('revision_version_not_increasing')
    for op in ops:
        if op.get('op')!='set': raise ValueError('only_set_operation_supported')
        set_path(x,op['path'],op.get('value'))
    g=x['governance']; g['validation_status']='needs_review'; g['validated_by']=None; g['validation_date']=None; g['review_snapshot_hash']=None
    g['publication_status']='unpublished'; g['second_review']={'required':x['risk']['requires_second_review'],'status':'pending' if x['risk']['requires_second_review'] else 'not_required','reviewer':None,'review_date':None,'snapshot_hash':None}
    p=x['provenance']; p['previous_object_version']=previous; p['revision_reason']=patch['reason']; p['revision_patch_hash']=stable_hash(patch)
    if snapshot_id is not None:
        x = revise_object(obj, x, snapshot_id=snapshot_id, reason=patch['reason'], actor=actor, force=True)
    stamp_canonical_hashes(x)
    errs=schema_errors(x,schema_path)
    if errs: raise ValueError('revision_schema_invalid:'+' | '.join(errs))
    if ledger: append_event(ledger,event_type='revision_created',object_id=x['object_id'],object_version=x['object_version'],actor=actor,
                            details={'previous_object_version':previous,'revision_patch_hash':x['provenance']['revision_patch_hash'],'reason':patch['reason']})
    return x

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--object',type=Path,required=True); ap.add_argument('--patch',type=Path,required=True); ap.add_argument('--schema',type=Path,required=True)
    ap.add_argument('--actor',required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--ledger',type=Path)
    a=ap.parse_args(); obj=json.loads(a.object.read_text()); patch=json.loads(a.patch.read_text()); x=create_revision(obj,patch,actor=a.actor,schema_path=a.schema,ledger=a.ledger)
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'status':'PASS','object_id':x['object_id'],'object_version':x['object_version']},indent=2)); return 0

# The cutover is an object-level durable contract, never a deployment timestamp.
LINEAGE_KEY = "revision_lineage"
LINEAGE_CONTRACT = "knowledge-revision-lineage-v1"


def lineage_evidence(obj):
    return (obj.get("metadata") or {}).get(LINEAGE_KEY)


def knowledge_revision(obj):
    """Scope includes blocked selected candidates; excludes source/structure/boom."""
    if lineage_evidence(obj) is not None:
        return True
    from src.vorming.admission_gate_v1 import is_boom_object
    from src.review.knowledge_path_v1 import is_structural_projection
    from src.vorming.source_accountability_v1 import is_source_record
    if (obj.get("object_type") == "document" or is_boom_object(obj)
            or is_structural_projection(obj) or is_source_record(obj)):
        return False
    semantic = (obj.get("metadata") or {}).get("semantic_passage") or {}
    return semantic.get("selection_origin") in {"proposal_selected", "human_annotation"}


def historical_revision_inputs(rows):
    """Intrinsic inputs of unseen historical rows, not a publication verdict."""
    return {'historical_has_knowledge': any(knowledge_revision(row) for row in rows),
            # Compatibility certificate shape; canonical registry owns sealing.
            'historical_has_publication': False}


def _version(value):
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", str(value))
    if not match:
        raise ValueError("object_version_must_be_semver_like")
    return tuple(int(part or 0) for part in match.groups())


def _meaning(obj):
    from src.integrity_kernel import canonical_object_payload
    payload = canonical_object_payload(obj)
    payload.pop("object_version", None)
    metadata = payload.get("metadata") or {}
    metadata.pop(LINEAGE_KEY, None)
    if not metadata:
        payload.pop("metadata", None)
    provenance = payload.get("provenance") or {}
    for field in ("previous_object_version", "revision_reason", "revision_patch_hash"):
        provenance.pop(field, None)
    return payload


def revise_object(previous, proposed, *, snapshot_id, reason, actor, force=False):
    """Prepare one successor; locked persistence validates the exact predecessor.

    Pure preparation does not grant review authority or perform durable writes.
    The caller supplies the actual current row, never a reconstructed predecessor.
    """
    from src.integrity_kernel import compute_canonical_object_hash
    from src.review.knowledge_path_v1 import is_structural_projection
    from src.review.knowledge_object_state_v1 import is_knowledge_object
    from src.vorming.admission_gate_v1 import is_boom_object
    heading_to_knowledge = (is_structural_projection(previous) and is_knowledge_object(proposed)
                            and not is_boom_object(proposed))
    if not (knowledge_revision(previous) or knowledge_revision(proposed) or heading_to_knowledge):
        return deepcopy(proposed)
    if not snapshot_id or not reason or not actor:
        raise ValueError("revision_evidence_required")
    if previous.get("object_id") != proposed.get("object_id"):
        raise ValueError("revision_object_identity_mismatch")
    if previous.get("document_id") != proposed.get("document_id") or previous.get("source") != proposed.get("source"):
        raise ValueError("revision_source_identity_mismatch")
    if not force and _meaning(previous) == _meaning(proposed):
        return deepcopy(previous) if proposed == previous else _unchanged_revision(previous, proposed)
    result = deepcopy(proposed)
    old_version = str(previous["object_version"])
    desired = str(proposed["object_version"])
    result["object_version"] = desired if _version(desired) > _version(old_version) else bump_patch(old_version)
    _rebind_relations(result, previous, desired)
    edge = {
        "contract": LINEAGE_CONTRACT,
        "snapshot_id": str(snapshot_id),
        "object_id": str(previous["object_id"]),
        "previous_object_version": old_version,
        "previous_canonical_object_hash": compute_canonical_object_hash(previous),
        "previous_lineage": "strict" if lineage_evidence(previous) else "legacy_unverified",
        "actor": str(actor),
        "reason": str(reason),
    }
    result.setdefault("metadata", {})[LINEAGE_KEY] = edge
    provenance = result.setdefault("provenance", {})
    provenance["previous_object_version"] = old_version
    provenance["revision_reason"] = str(reason)
    provenance["revision_patch_hash"] = stable_hash(edge)
    reset_review_state(result)
    return stamp_canonical_hashes(result)


def reset_review_state(result):
    """Withdraw current first/second-review mirrors; never grant authority.

    Revision preparation and saved source corrections share this existing
    owner's rule. Callers still own authorization, exact binding invalidation
    and the atomic native commit.
    """
    governance = result.setdefault("governance", {})
    governance.update(validation_status="needs_review", validated_by=None,
                      validation_date=None, review_snapshot_hash=None, publication_status="unpublished")
    required = bool((result.get("risk") or {}).get("requires_second_review"))
    governance["second_review"] = {"required": required, "status": "pending" if required else "not_required",
                                   "reviewer": None, "review_date": None, "snapshot_hash": None}


def _unchanged_revision(previous, proposed):
    """A governance-only decision retains its exact canonical tuple."""
    result = deepcopy(proposed)
    result["object_version"] = previous["object_version"]
    result["provenance"] = deepcopy(previous["provenance"])
    metadata = result.setdefault("metadata", {})
    if lineage_evidence(previous) is not None:
        metadata[LINEAGE_KEY] = deepcopy(lineage_evidence(previous))
    else:
        metadata.pop(LINEAGE_KEY, None)
    return stamp_canonical_hashes(result)


def current_revisions(rows, *, snapshot_id=None):
    """One append-order projection for file and PostgreSQL; no semver guessing.

    Legacy rows retain their historical selection rule. Strict edges must refer
    to the exact immediately preceding stored revision in this WorkingRevision.
    """
    from src.integrity_kernel import compute_canonical_object_hash
    from src.review.revision_window_v1 import RevisionWindow
    if isinstance(rows, RevisionWindow) and snapshot_id is not None and rows.snapshot_id != snapshot_id:
        raise ValueError('revision_scope_mismatch')
    current = {}
    seen = set()
    strict_identities = set()
    for row in rows:
        oid, version = row["object_id"], row["object_version"]
        identity = (oid, version)
        edge = lineage_evidence(row)
        if identity in seen and (edge is not None or identity in strict_identities):
            raise ValueError("revision_identity_duplicate")
        seen.add(identity)
        if edge is not None:
            strict_identities.add(identity)
        if edge is None and oid in current and lineage_evidence(current[oid]) is not None:
            raise ValueError("revision_lineage_downgrade")
        anchor = edge is not None and isinstance(rows, RevisionWindow) and oid not in current and rows.is_anchor(row)
        if anchor and (row.get('provenance') or {}).get('canonical_object_hash') != compute_canonical_object_hash(row):
            raise ValueError('revision_evidence_invalid')
        if edge is not None and not anchor:
            previous = current.get(oid)
            if not isinstance(edge, dict) or edge.get("contract") != LINEAGE_CONTRACT:
                raise ValueError("revision_lineage_contract_invalid")
            if previous is None:
                raise ValueError("revision_predecessor_missing")
            provenance = row.get("provenance") or {}
            if (edge.get("object_id") != oid
                    or edge.get("previous_object_version") != previous["object_version"]
                    or provenance.get("previous_object_version") != previous["object_version"]
                    or edge.get("previous_canonical_object_hash") != compute_canonical_object_hash(previous)):
                raise ValueError("revision_predecessor_mismatch")
            if _version(version) <= _version(previous["object_version"]):
                raise ValueError("revision_version_not_increasing")
            if (not edge.get("snapshot_id") or snapshot_id is not None and edge["snapshot_id"] != snapshot_id
                    or row.get("document_id") != previous.get("document_id")
                    or row.get("source") != previous.get("source")):
                raise ValueError("revision_scope_mismatch")
            if (edge.get("previous_lineage") != ("strict" if lineage_evidence(previous) else "legacy_unverified")
                    or not edge.get("reason") or not edge.get("actor")
                    or provenance.get("revision_reason") != edge["reason"]
                    or provenance.get("revision_patch_hash") != stable_hash(edge)
                    or provenance.get("canonical_object_hash") != compute_canonical_object_hash(row)):
                raise ValueError("revision_evidence_invalid")
        current[oid] = row
    return list(current.values())



def with_current_revision(rows, revision):
    """Replace only the final occurrence, or append a genuinely new version."""
    from src.review.revision_window_v1 import RevisionWindow
    result = rows.copy() if isinstance(rows, RevisionWindow) else list(rows)
    identity = (revision["object_id"], revision["object_version"])
    for position in range(len(result) - 1, -1, -1):
        if (result[position]["object_id"], result[position]["object_version"]) == identity:
            result[position] = revision
            return result
    result.append(revision)
    return result


def validate_revision_write(previous, submitted, *, snapshot_id):
    """Called under the existing file lock / PostgreSQL row lock and CAS."""
    from src.integrity_kernel import compute_canonical_object_hash
    old_current = {row["object_id"]: row for row in current_revisions(previous, snapshot_id=snapshot_id)}
    new_current = {row["object_id"]: row for row in current_revisions(submitted, snapshot_id=snapshot_id)}
    old = {(row["object_id"], row["object_version"]): row for row in previous}
    new = {(row["object_id"], row["object_version"]): row for row in submitted}
    protected_ids = {row["object_id"] for row in previous + submitted if knowledge_revision(row)}
    from src.review.revision_window_v1 import RevisionWindow
    for window in (previous, submitted):
        if isinstance(window, RevisionWindow):
            protected_ids.update(oid for oid, prefix in window.frontiers.items() if prefix['historical_has_knowledge'])
    # Keep occurrence order/multiplicity: old writers could repeat a legacy version.
    # A dict keyed only by identity would erase those immutable historical rows.
    for oid in protected_ids:
        prior_rows = [row for row in previous if row["object_id"] == oid]
        retained_rows = [row for row in submitted if row["object_id"] == oid
                         and (oid, row["object_version"]) in old]
        if ([row["object_version"] for row in retained_rows]
                != [row["object_version"] for row in prior_rows]):
            raise ValueError("revision_history_reordered")
        for position, (before, after) in enumerate(zip(prior_rows, retained_rows)):
            if compute_canonical_object_hash(before) != compute_canonical_object_hash(after):
                raise ValueError("revision_content_changed_in_place")
            if (position != len(prior_rows) - 1
                    or new_current[oid]["object_version"] != before["object_version"]) and after != before:
                raise ValueError("revision_history_changed")
    # Duplicate identities may only be retained from legacy history, never created.
    new_identities = [(row["object_id"], row["object_version"]) for row in submitted
                      if (row["object_id"], row["object_version"]) not in old
                      and row["object_id"] in protected_ids]
    if len(new_identities) != len(set(new_identities)):
        raise ValueError("revision_identity_duplicate")
    write_current = dict(old_current)
    for identity, after in new.items():
        if identity in old:
            continue
        before = write_current.get(identity[0])
        if before is not None and (knowledge_revision(before) or knowledge_revision(after)):
            if not lineage_evidence(after):
                raise ValueError("revision_predecessor_required")
        write_current[identity[0]] = after
    # No stale command can add an alternative successor to the now-current row.
    appended = [row for row in submitted if (row["object_id"], row["object_version"]) not in old]
    if appended:
        current_revisions(previous + appended, snapshot_id=snapshot_id)
    return list(new_current.values())

if __name__=='__main__': raise SystemExit(main())


def reprocessed_history(previous, generated, *, snapshot_id, actor):
    """Retain knowledge history through same-source preparation/recovery.

    New identities remain initial candidates; this never matches text or sources.
    Removed knowledge candidates become terminal without erasing their history.
    """
    from src.integrity_kernel import compute_canonical_object_hash
    prior = {row["object_id"]: row for row in current_revisions(previous, snapshot_id=snapshot_id)}
    retained_ids = {row["object_id"] for row in previous + generated if knowledge_revision(row)}
    retained = [deepcopy(row) for row in previous if row["object_id"] in retained_ids]
    new_ids = {row["object_id"] for row in generated}
    for oid, row in prior.items():
        if knowledge_revision(row) and oid not in new_ids:
            if (row.get("governance") or {}).get("validation_status") == "superseded":
                continue
            retired = revise_object(row, row, snapshot_id=snapshot_id, actor=actor,
                                    reason="same-source candidate retirement", force=True)
            retired["governance"]["validation_status"] = "superseded"
            retained.append(retired)
    for row in generated:
        old = prior.get(row["object_id"])
        if old is None or not (knowledge_revision(old) or knowledge_revision(row)):
            retained.append(deepcopy(row))
            continue
        if compute_canonical_object_hash(old) == compute_canonical_object_hash(row):
            continue
        updated = revise_object(old, row, snapshot_id=snapshot_id,
                                reason="same-source re-extraction/recovery", actor=actor,
                                force=(old.get("governance") or {}).get("validation_status") == "superseded")
        if updated["object_version"] == old["object_version"]:
            continue
        retained.append(updated)
    order = {}
    for row in previous + generated:
        order.setdefault(row["object_id"], len(order))
    return sorted(retained, key=lambda row: order[row["object_id"]])


def apply_annotation_revisions(generated, basis, *, snapshot_id, fragments, context):
    """Apply materialised source to explicit original annotations, never match text.

    The materialiser owns its raw output. This existing revision owner alone
    retains an already activated canonical identity and makes its successor.
    ``basis`` is immutable sealed input, validated against actual stored rows by
    FormationEvidence and native activation. It is never a browser object patch.
    """
    from src.vorming.human_annotation_projection_v1 import context_record
    from src.vorming.admission_gate_v1 import apply_admission_gate
    from src.vorming.passage_register_v1 import apply_passage_register
    if (set(basis) != {'version', 'proof_id', 'actor_id', 'objects'}
            or basis.get('version') != 'human-annotation-revision-v1'):
        raise ValueError('annotation_revision_contract_invalid')
    previous = basis['objects']
    by_id = {row['object_id']: row for row in previous}
    by_annotation = {}
    prior_ids = {row['object_id'] for row in previous}
    for row in previous:
        ref = (row.get('metadata') or {}).get('human_annotation')
        if ref:
            if ref['annotation_id'] in by_annotation:
                raise ValueError('annotation_identity_conflict')
            by_annotation[ref['annotation_id']] = row
    seen, result, unchanged = set(), [], {}
    # #1067: the kind each annotation-backed object has after this build, for relation endpoint checks.
    from src.review.review_cockpit_v1 import confirmable_proposed_type
    next_kinds = {}
    for raw in generated:
        ref = (raw.get('metadata') or {}).get('human_annotation')
        old = by_annotation.get(ref['annotation_id']) if ref else None
        kind = confirmable_proposed_type(raw) if old is not None else ''
        if kind and kind != old.get('confirmed_object_type'):
            next_kinds[old['object_id']] = kind
    producer_metadata = ('semantic_passage', 'human_annotation', 'source_bound_fields',
        'source_bound_context', 'source_accountability', 'recommendation_semantics_evidence')
    for raw in generated:
        ref = (raw.get('metadata') or {}).get('human_annotation')
        old = by_annotation.get(ref['annotation_id']) if ref else None
        if old is None:
            if ref and raw['object_id'] in prior_ids:
                raise ValueError('annotation_identity_conflict')
            prior = by_id.get(raw['object_id']) if not ref else None
            # Unchanged source/structure is still reviewer-owned work. A full
            # set build must not erase its exact source-role confirmations.
            same_source = prior and all(prior.get(key) == raw.get(key) for key in ('content', 'source'))
            same_producer = same_source and all((prior.get('metadata') or {}).get(key) ==
                (raw.get('metadata') or {}).get(key) for key in producer_metadata)
            if same_producer:
                unchanged[prior['object_id']] = prior
                result.append(deepcopy(prior))
            else:
                result.append(deepcopy(raw))
            continue
        seen.add(ref['annotation_id'])
        if ref == old['metadata']['human_annotation']:
            unchanged[old['object_id']] = old
            result.append(deepcopy(old))
            continue
        proposed = deepcopy(old)
        for field in ('content', 'source', 'provenance', 'proposed_object_type', 'proposed_recommendation_semantics'):
            if field in raw:
                proposed[field] = deepcopy(raw[field])
            else:
                proposed.pop(field, None)
        for field in producer_metadata:
            if field in raw['metadata']:
                proposed['metadata'][field] = deepcopy(raw['metadata'][field])
            else:
                proposed['metadata'].pop(field, None)
        # A prior final assessment is evidence for its old tuple. Confirmed
        # classification/relations/semantics remain reviewer-owned choices.
        _drop_confirmation_of_another_kind(proposed, raw, peers=by_id, next_kinds=next_kinds)
        proposed['metadata'].pop('review_passage', None)
        proposed['metadata'].pop('passage_register', None)
        bound = proposed['metadata'].get('source_bound_context')
        if bound:
            proposed['metadata']['source_bound_context'] = context_record(bound['entries'], obj=proposed)
        revised = revise_object(old, proposed, snapshot_id=snapshot_id,
            actor=basis['actor_id'], reason='human annotation correction')
        if bound:
            revised['metadata']['source_bound_context'] = context_record(bound['entries'], obj=revised)
        stamp_canonical_hashes(revised)
        result.append(revised)
    if set(by_annotation) - seen:
        raise ValueError('annotation_replacement_required')
    if len({row['object_id'] for row in result}) != len(result):
        raise ValueError('annotation_identity_conflict')
    _retarget_relations_to_rebuilt(result, {row['object_id']: row for row in previous}, unchanged,
                                   snapshot_id=snapshot_id, actor=basis['actor_id'])
    result = apply_admission_gate(result, klasse=context['class'], fragments=fragments,
        document_version=context['version'], source_hash=context['sha256'])
    return [deepcopy(unchanged[row['object_id']]) if row['object_id'] in unchanged else row
            for row in apply_passage_register(result)]

def _legacy_mirror(rows, *, keep, moved=(), confirmed):
    """Keep a legacy relation mirror equal to its new-format authority (``legacy_relation_mirror_matches``)."""
    kept = [row for row in rows if keep(row)]
    for relation in moved:
        kept.append({'relation_type': relation['relation_type'], 'target_object_id': relation['target_object_id'],
                     'target_object_version': relation['target_object_version'], 'confirmed': confirmed})
    return kept


def _retarget_relations_to_rebuilt(result, previous_by_id, unchanged, *, snapshot_id, actor):
    """#1067, besluit William 2026-11-14: a relation to a target rebuilt in this build is confirmed again.

    A confirmed relation names the exact target version its reviewer saw. When that target gets a new version,
    the confirmation lapses and the relation is proposed again, pointing at the new version, so the reviewer can
    confirm it. An approved source usually holds only the confirmed relation; that becomes the proposal. A source
    that did not change itself becomes a new version too, because its approval covered the old target text. That
    can move other targets, so this repeats until nothing changes. Legacy mirrors follow the authority. Edits
    ``result`` in place.
    """
    from src.knowledge_relations_v1 import build_knowledge_relation, relation_sort_key
    for _ in range(len(result) + 1):
        current = {row['object_id']: str(row['object_version']) for row in result}
        rebuilt = {object_id for object_id, version in current.items()
                   if object_id in previous_by_id and str(previous_by_id[object_id]['object_version']) != version}

        def stale(relation):
            target = relation.get('target_object_id')
            return target in rebuilt and str(relation.get('target_object_version')) != current[target]
        moved = False
        for index, row in enumerate(result):
            confirmed = row.get('confirmed_knowledge_relations') or []
            proposed = row.get('proposed_knowledge_relations') or []
            if not any(stale(relation) for relation in [*confirmed, *proposed]):
                continue
            new, remap = deepcopy(row), {}

            def repropose(relation):
                return build_knowledge_relation(
                    source_object_id=row['object_id'], source_object_version=str(row['object_version']),
                    relation_type=relation['relation_type'], target_object_id=relation['target_object_id'],
                    target_object_version=current[relation['target_object_id']])
            proposals = {}
            for relation in proposed:
                if stale(relation):
                    fresh = repropose(relation)
                    remap[relation['relation_id']] = fresh['relation_id']
                    relation = fresh
                proposals[relation['relation_id']] = relation
            # A lapsed confirmation is offered again as a proposal for the new target version.
            lapsed = [relation for relation in confirmed if stale(relation)]
            for relation in lapsed:
                fresh = repropose(relation)
                remap.setdefault(relation['relation_id'], fresh['relation_id'])
                proposals.setdefault(fresh['relation_id'], fresh)
            if 'confirmed_knowledge_relations' in new:
                new['confirmed_knowledge_relations'] = [r for r in confirmed if not stale(r)]
            new['proposed_knowledge_relations'] = sorted(proposals.values(), key=relation_sort_key)
            fresh_rows = [r for r in new['proposed_knowledge_relations'] if r['relation_id'] in remap.values()]
            if new.get('confirmed_relations'):
                new['confirmed_relations'] = _legacy_mirror(new['confirmed_relations'], confirmed=True,
                    keep=lambda r: not stale(r))
            if new.get('relations'):
                new['relations'] = _legacy_mirror(new['relations'], confirmed=False, moved=[
                    r for r in fresh_rows if not any(
                        (old.get('relation_type'), old.get('target_object_id'), str(old.get('target_object_version')))
                        == (r['relation_type'], r['target_object_id'], r['target_object_version'])
                        for old in new['relations'] if not stale(old))],
                    keep=lambda r: not stale(r))
            metadata = new.get('metadata') or {}
            evidence = metadata.get('knowledge_relation_evidence')
            if isinstance(evidence, dict):
                for item in evidence.get('relations') or []:
                    if item.get('relation_id') in remap:
                        item['relation_id'] = remap[item['relation_id']]
            review = metadata.get('knowledge_relation_review')
            if isinstance(review, dict) and 'confirmed_relation_ids' in review:
                review['confirmed_relation_ids'] = [r['relation_id'] for r in new.get('confirmed_knowledge_relations') or []]
            previous = previous_by_id.get(row['object_id'])
            if previous is not None and str(previous['object_version']) == str(row['object_version']):
                unchanged.pop(row['object_id'], None)
                new = revise_object(previous, new, snapshot_id=snapshot_id, actor=actor,
                                    reason='relation target rebuilt')
            stamp_canonical_hashes(new)
            result[index] = new
            moved = True
        if not moved:
            return
    raise ValueError('annotation_relation_retarget_unstable')


def _drop_confirmation_of_another_kind(proposed, raw, *, peers=None, next_kinds=None):
    """#1067: a kind corrected in the annotation card is not overridden by the old version's confirmation.

    A confirmation is about the kind it confirmed. When the corrected annotation now carries another kind,
    that confirmation, and the direction/strength that only a recommendation has, no longer apply: the new
    version shows the corrected kind as proposed and its reviewer confirms it. A confirmed relation whose
    endpoint contract the corrected kind no longer meets goes too, so the correction can be approved; the
    reviewer confirms relations again. The same kind keeps everything.
    """
    from src.review.review_cockpit_v1 import confirmable_proposed_type
    from src.vorming.knowledge_relation_proposal_v1 import relation_endpoint_compatible
    from src.knowledge_relations_v1 import serving_relation_type
    confirmed = proposed.get('confirmed_object_type')
    corrected = confirmable_proposed_type(raw)
    if not confirmed or not corrected or corrected == confirmed:
        return
    for field in ('confirmed_object_type', 'confirmed_recommendation_semantics', 'confirmed_recommendation_strength'):
        proposed.pop(field, None)
    peers, next_kinds = peers or {}, next_kinds or {}

    def fits(relation):
        # A target corrected in the same build is judged by its new kind, never its old one.
        peer = peers.get(relation.get('target_object_id')) or {}
        target = str(next_kinds.get(relation.get('target_object_id')) or peer.get('confirmed_object_type')
                     or peer.get('proposed_object_type') or peer.get('object_type') or '')
        return relation_endpoint_compatible(relation.get('relation_type'), source_type=corrected, target_type=target)
    # Proposals the corrected kind cannot carry go too; otherwise admission refuses the corrected object.
    for field, legacy in (('confirmed_knowledge_relations', 'confirmed_relations'),
                          ('proposed_knowledge_relations', 'relations')):
        if field in proposed:
            proposed[field] = [relation for relation in proposed[field] if fits(relation)]
        if proposed.get(legacy):
            # Legacy rows may carry an older relation name; judge them by their served name, like the mirror check.
            proposed[legacy] = [row for row in proposed[legacy]
                                if fits({**row, 'relation_type': serving_relation_type(row.get('relation_type'))})]


def _rebind_relations(result, previous, staged_version):
    """Rebuild IDs for the new source endpoint, never infer a new target."""
    from src.knowledge_relations_v1 import (build_knowledge_relation,
        validate_knowledge_relation_set, relation_sort_key)
    remap = {}
    for field in ("proposed_knowledge_relations", "confirmed_knowledge_relations"):
        if field not in result:
            continue
        relations = result[field]
        # Accept the caller's freshly prepared set or the predecessor's exact set.
        if (validate_knowledge_relation_set(relations, source_object_id=result["object_id"],
                source_object_version=staged_version)
                and validate_knowledge_relation_set(relations, source_object_id=result["object_id"],
                source_object_version=previous["object_version"])):
            raise ValueError("revision_relation_evidence_invalid")
        rebuilt = []
        for relation in relations:
            new = build_knowledge_relation(source_object_id=result["object_id"],
                source_object_version=result["object_version"], relation_type=relation["relation_type"],
                target_object_id=relation["target_object_id"], target_object_version=relation["target_object_version"])
            remap[relation["relation_id"]] = new["relation_id"]
            rebuilt.append(new)
        result[field] = sorted(rebuilt, key=relation_sort_key)
    metadata = result.get("metadata") or {}
    # Source spans/evidence are preserved; only the exact source-endpoint IDs change.
    evidence = metadata.get("knowledge_relation_evidence")
    if isinstance(evidence, dict):
        for row in evidence.get("relations") or []:
            if row.get("relation_id") in remap:
                row["relation_id"] = remap[row["relation_id"]]
    review = metadata.get("knowledge_relation_review")
    if isinstance(review, dict):
        if review == (previous.get("metadata") or {}).get("knowledge_relation_review"):
            # Historical confirmation lives on the predecessor, not on a fresh review.
            metadata.pop("knowledge_relation_review", None)
        else:
            review["source_object_version_after"] = result["object_version"]
            review["confirmed_relation_ids"] = [r["relation_id"] for r in result.get("confirmed_knowledge_relations", [])]
